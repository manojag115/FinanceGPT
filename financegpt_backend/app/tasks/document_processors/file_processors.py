"""
File document processors for different ETL services (Unstructured, LlamaCloud, Docling).
"""

import asyncio
import contextlib
import logging
import ssl
import warnings
from logging import ERROR, getLogger

import httpx
from fastapi import HTTPException
from langchain_core.documents import Document as LangChainDocument
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import Document, DocumentType, Log, Notification
from app.services.llm_service import get_user_long_context_llm
from app.services.notification_service import NotificationService
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    convert_document_to_markdown,
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    check_duplicate_document,
    get_current_timestamp,
)
from .markdown_processor import add_received_markdown_file_document

# Logger
logger = logging.getLogger(__name__)

# Constants for LlamaCloud retry configuration
LLAMACLOUD_MAX_RETRIES = 3
LLAMACLOUD_BASE_DELAY = 5  # Base delay in seconds for exponential backoff
LLAMACLOUD_RETRYABLE_EXCEPTIONS = (
    ssl.SSLError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    ConnectionError,
    TimeoutError,
)


async def _process_tax_form_if_applicable(
    session: AsyncSession,
    document: Document,
    filename: str,
    user_id: str,
    search_space_id: int,
) -> None:
    """
    Check if uploaded document is a tax form and trigger parsing if so.
    
    Detects tax forms based on filename patterns (w2, 1099) and content.
    If detected, extracts structured data and saves to tax_forms tables.
    
    Args:
        session: Database session
        document: The uploaded document
        filename: Original filename
        user_id: User ID
        search_space_id: Search space ID
    """
    from uuid import UUID
    from app.db import TaxForm
    from app.parsers.tax_form_parser import TaxFormParser
    from app.utils.pii_masking import prepare_tax_form_for_storage
    from app.schemas.tax_forms import (
        W2FormCreate,
        Form1099MiscCreate,
        Form1099IntCreate,
        Form1099DivCreate,
        Form1099BCreate,
    )
    import re
    
    try:
        # Only process PDFs
        if not filename.lower().endswith('.pdf'):
            return
        
        # Detect tax form type from filename
        filename_lower = filename.lower()
        form_type = None
        tax_year = None
        
        # Extract year from filename (e.g., "w2_2024.pdf", "2024_w2.pdf")
        year_match = re.search(r'(20\d{2})', filename)
        if year_match:
            tax_year = int(year_match.group(1))
        
        # Detect form type
        if 'w2' in filename_lower or 'w-2' in filename_lower:
            form_type = 'W2'
            if not tax_year:
                tax_year = 2024  # Default to current tax year
        elif '1099' in filename_lower:
            if 'misc' in filename_lower:
                form_type = '1099-MISC'
            elif 'int' in filename_lower:
                form_type = '1099-INT'
            elif 'div' in filename_lower:
                form_type = '1099-DIV'
            elif 'b' in filename_lower:
                form_type = '1099-B'
            else:
                # Generic 1099, try to detect from content later
                form_type = '1099-MISC'  # Default
            
            if not tax_year:
                tax_year = 2024
        
        # If not a tax form, return early
        if not form_type:
            return
        
        logger.info(f"Detected tax form: {form_type} for year {tax_year} in file {filename}")
        
        # Create tax_form record
        tax_form = TaxForm(
            user_id=UUID(user_id),
            search_space_id=search_space_id,
            form_type=form_type,
            tax_year=tax_year,
            document_id=document.id,
            processing_status='pending',
        )
        session.add(tax_form)
        await session.commit()
        await session.refresh(tax_form)
        
        logger.info(f"Created tax form record with ID {tax_form.id}, starting parsing...")
        
        # TODO: Trigger async parsing task
        # For now, log that parsing would happen
        # In production, this would be a Celery task
        logger.info(
            f"Tax form parsing would be triggered here for {form_type} (tax_form_id={tax_form.id}). "
            f"Parser integration pending."
        )
        
        # Update status to show it's queued for processing
        tax_form.processing_status = 'processing'
        await session.commit()
        
    except Exception as e:
        logger.error(f"Error processing tax form for {filename}: {e}")
        # Don't fail the document upload if tax parsing fails
        await session.rollback()


async def _save_investment_holdings(
    session: AsyncSession,
    user_id: str,
    holdings_data: list,
    metadata: dict,
    filename: str,
) -> None:
    """
    Save investment holdings to structured database table.
    
    Args:
        session: Database session
        user_id: User ID
        holdings_data: List of holdings from parser
        metadata: Metadata from parser (institution, account info, etc.)
        filename: Original filename
    """
    from uuid import UUID
    from app.db import InvestmentAccount, InvestmentHolding
    import uuid
    
    try:
        # Create or get investment account
        account = InvestmentAccount(
            user_id=UUID(user_id),
            account_number=metadata.get("account_number", f"FILE-{uuid.uuid4().hex[:8]}"),
            account_name=metadata.get("account_name", filename),
            account_type=metadata.get("account_type", "brokerage"),
            account_tax_type=metadata.get("account_tax_type", "taxable"),
            institution=metadata.get("institution", "Unknown"),
            total_value=0.0,  # Will be calculated from holdings
            source_type="document",  # Uploaded from file
        )
        session.add(account)
        await session.flush()  # Get account ID
        
        # Process each holding
        total_value = 0.0
        for holding_data in holdings_data:
            symbol = holding_data.symbol if hasattr(holding_data, 'symbol') else holding_data.get('symbol', '')
            
            # Handle None values from CSV parsing
            quantity_raw = holding_data.quantity if hasattr(holding_data, 'quantity') else holding_data.get('quantity')
            cost_basis_raw = holding_data.cost_basis if hasattr(holding_data, 'cost_basis') else holding_data.get('cost_basis')
            current_value_raw = holding_data.value if hasattr(holding_data, 'value') else holding_data.get('value')
            
            quantity = float(quantity_raw or 0)
            cost_basis = float(cost_basis_raw or 0)
            current_value = float(current_value_raw or 0)
            
            if not symbol or quantity == 0:
                continue
            
            # Calculate average cost basis
            average_cost_basis = cost_basis / quantity if quantity > 0 and cost_basis > 0 else 0
            
            # Save holding with basic data only (no enrichment during upload)
            # Prices will be fetched on-demand when user queries their portfolio
            holding = InvestmentHolding(
                account_id=account.id,
                symbol=symbol,
                quantity=quantity,
                cost_basis=cost_basis,
                average_cost_basis=average_cost_basis,
                market_value=current_value,  # Use current_value from CSV as fallback
            )
            
            total_value += current_value
            session.add(holding)
        
        # Update account total value
        account.total_value = total_value
        await session.flush()
        
        logger.info(f"Saved {len(holdings_data)} investment holdings for user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to save investment holdings: {e}")
        # Don't fail the entire document upload if holdings save fails
        # The document will still be searchable, just won't have structured data


def get_google_drive_unique_identifier(
    connector: dict | None,
    filename: str,
    search_space_id: int,
) -> tuple[str, str | None]:
    """
    Get unique identifier hash for a file, with special handling for Google Drive.

    For Google Drive files, uses file_id as the unique identifier (doesn't change on rename).
    For other files, uses filename.

    Args:
        connector: Optional connector info dict with type and metadata
        filename: The filename (used for non-Google Drive files or as fallback)
        search_space_id: The search space ID

    Returns:
        Tuple of (primary_hash, legacy_hash or None)
        - For Google Drive: (file_id_based_hash, filename_based_hash for migration)
        - For other sources: (filename_based_hash, None)
    """
    if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
        metadata = connector.get("metadata", {})
        file_id = metadata.get("google_drive_file_id")

        if file_id:
            # New method: use file_id as unique identifier (doesn't change on rename)
            primary_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_DRIVE_FILE, file_id, search_space_id
            )
            # Legacy method: for backward compatibility with existing documents
            # that were indexed with filename-based hash
            legacy_hash = generate_unique_identifier_hash(
                DocumentType.GOOGLE_DRIVE_FILE, filename, search_space_id
            )
            return primary_hash, legacy_hash

    # For non-Google Drive files, use filename as before
    primary_hash = generate_unique_identifier_hash(
        DocumentType.FILE, filename, search_space_id
    )
    return primary_hash, None


async def handle_existing_document_update(
    session: AsyncSession,
    existing_document: Document,
    content_hash: str,
    connector: dict | None,
    filename: str,
    primary_hash: str,
) -> tuple[bool, Document | None]:
    """
    Handle update logic for an existing document.

    Args:
        session: Database session
        existing_document: The existing document found in database
        content_hash: Hash of the new content
        connector: Optional connector info
        filename: Current filename
        primary_hash: The primary hash (file_id based for Google Drive)

    Returns:
        Tuple of (should_skip_processing, document_to_return)
        - (True, document): Content unchanged, just return existing document
        - (False, None): Content changed, need to re-process
    """
    # Check if this document needs hash migration (found via legacy hash)
    if existing_document.unique_identifier_hash != primary_hash:
        existing_document.unique_identifier_hash = primary_hash
        logging.info(f"Migrated document to file_id-based identifier: {filename}")

    # Check if content has changed
    if existing_document.content_hash == content_hash:
        # Content unchanged - check if we need to update metadata (e.g., filename changed)
        if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
            connector_metadata = connector.get("metadata", {})
            new_name = connector_metadata.get("google_drive_file_name")
            # Check both possible keys for old name (FILE_NAME is used in stored documents)
            doc_metadata = existing_document.document_metadata or {}
            old_name = doc_metadata.get("FILE_NAME") or doc_metadata.get(
                "google_drive_file_name"
            )

            if new_name and old_name and old_name != new_name:
                # File was renamed - update title and metadata, skip expensive processing
                from sqlalchemy.orm.attributes import flag_modified

                existing_document.title = new_name
                if not existing_document.document_metadata:
                    existing_document.document_metadata = {}
                existing_document.document_metadata["FILE_NAME"] = new_name
                existing_document.document_metadata["google_drive_file_name"] = new_name
                flag_modified(existing_document, "document_metadata")
                await session.commit()
                logging.info(
                    f"File renamed in Google Drive: '{old_name}' → '{new_name}' (no re-processing needed)"
                )

        logging.info(f"Document for file {filename} unchanged. Skipping.")
        return True, existing_document
    else:
        # Content has changed - need to re-process
        logging.info(f"Content changed for file {filename}. Updating document.")
        return False, None


async def find_existing_document_with_migration(
    session: AsyncSession,
    primary_hash: str,
    legacy_hash: str | None,
    content_hash: str | None = None,
) -> Document | None:
    """
    Find existing document, checking both new hash and legacy hash for migration,
    with fallback to content_hash for cross-source deduplication.

    Args:
        session: Database session
        primary_hash: The primary hash (file_id based for Google Drive)
        legacy_hash: The legacy hash (filename based) for migration, or None
        content_hash: The content hash for fallback deduplication, or None

    Returns:
        Existing document if found, None otherwise
    """
    # First check with primary hash (new method)
    existing_document = await check_document_by_unique_identifier(session, primary_hash)

    # If not found and we have a legacy hash, check with that (migration path)
    if not existing_document and legacy_hash:
        existing_document = await check_document_by_unique_identifier(
            session, legacy_hash
        )
        if existing_document:
            logging.info(
                "Found legacy document (filename-based hash), will migrate to file_id-based hash"
            )

    # Fallback: check by content_hash to catch duplicates from different sources
    # This prevents unique constraint violations when the same content exists
    # under a different unique_identifier (e.g., manual upload vs Google Drive)
    if not existing_document and content_hash:
        existing_document = await check_duplicate_document(session, content_hash)
        if existing_document:
            logging.info(
                f"Found duplicate content from different source (content_hash match). "
                f"Original document ID: {existing_document.id}, type: {existing_document.document_type}"
            )

    return existing_document


async def parse_with_llamacloud_retry(
    file_path: str,
    estimated_pages: int,
    task_logger: TaskLoggingService | None = None,
    log_entry: Log | None = None,
):
    """
    Parse a file with LlamaCloud with retry logic for transient SSL/connection errors.

    Args:
        file_path: Path to the file to parse
        estimated_pages: Estimated number of pages for timeout calculation
        task_logger: Optional task logger for progress updates
        log_entry: Optional log entry for progress updates

    Returns:
        LlamaParse result object

    Raises:
        Exception: If all retries fail
    """
    from llama_cloud_services import LlamaParse
    from llama_cloud_services.parse.utils import ResultType

    # Calculate timeouts based on estimated pages
    # Base timeout of 300 seconds + 30 seconds per page for large documents
    base_timeout = 300
    per_page_timeout = 30
    job_timeout = base_timeout + (estimated_pages * per_page_timeout)

    # Create custom httpx client with larger timeouts for file uploads
    # The SSL error often occurs during large file uploads, so we need generous timeouts
    custom_timeout = httpx.Timeout(
        connect=60.0,  # 60 seconds to establish connection
        read=300.0,  # 5 minutes to read response
        write=300.0,  # 5 minutes to write/upload (important for large files)
        pool=60.0,  # 60 seconds to acquire connection from pool
    )

    last_exception = None

    for attempt in range(1, LLAMACLOUD_MAX_RETRIES + 1):
        try:
            # Create a fresh httpx client for each attempt
            async with httpx.AsyncClient(timeout=custom_timeout) as custom_client:
                # Create LlamaParse parser instance with optimized settings
                parser = LlamaParse(
                    api_key=app_config.LLAMA_CLOUD_API_KEY,
                    num_workers=1,  # Use single worker for file processing
                    verbose=True,
                    language="en",
                    result_type=ResultType.MD,
                    # Timeout settings for large files
                    max_timeout=max(2000, job_timeout),  # Overall max timeout
                    job_timeout_in_seconds=job_timeout,
                    job_timeout_extra_time_per_page_in_seconds=per_page_timeout,
                    # Use our custom client with larger timeouts
                    custom_client=custom_client,
                )

                # Parse the file asynchronously
                result = await parser.aparse(file_path)
                return result

        except LLAMACLOUD_RETRYABLE_EXCEPTIONS as e:
            last_exception = e
            error_type = type(e).__name__

            if attempt < LLAMACLOUD_MAX_RETRIES:
                # Calculate exponential backoff delay
                delay = LLAMACLOUD_BASE_DELAY * (2 ** (attempt - 1))

                if task_logger and log_entry:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"LlamaCloud upload failed (attempt {attempt}/{LLAMACLOUD_MAX_RETRIES}), retrying in {delay}s",
                        {
                            "error_type": error_type,
                            "error_message": str(e)[:200],
                            "attempt": attempt,
                            "retry_delay": delay,
                        },
                    )
                else:
                    logging.warning(
                        f"LlamaCloud upload failed (attempt {attempt}/{LLAMACLOUD_MAX_RETRIES}): {error_type}. "
                        f"Retrying in {delay}s..."
                    )

                await asyncio.sleep(delay)
            else:
                logging.error(
                    f"LlamaCloud upload failed after {LLAMACLOUD_MAX_RETRIES} attempts: {error_type} - {e}"
                )

        except Exception:
            # Non-retryable exception, raise immediately
            raise

    # All retries exhausted
    raise last_exception or RuntimeError("LlamaCloud parsing failed after all retries")


async def add_received_file_document_using_unstructured(
    session: AsyncSession,
    file_name: str,
    unstructured_processed_elements: list[LangChainDocument],
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
) -> Document | None:
    """
    Process and store a file document using Unstructured service.

    Args:
        session: Database session
        file_name: Name of the processed file
        unstructured_processed_elements: Processed elements from Unstructured
        search_space_id: ID of the search space
        user_id: ID of the user
        connector: Optional connector info for Google Drive files

    Returns:
        Document object if successful, None if failed
    """
    try:
        file_in_markdown = await convert_document_to_markdown(
            unstructured_processed_elements
        )

        # Generate unique identifier hash (uses file_id for Google Drive, filename for others)
        primary_hash, legacy_hash = get_google_drive_unique_identifier(
            connector, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document exists (with migration support for Google Drive and content_hash fallback)
        existing_document = await find_existing_document_with_migration(
            session, primary_hash, legacy_hash, content_hash
        )

        if existing_document:
            # Handle existing document (rename detection, content change check)
            should_skip, doc = await handle_existing_document_update(
                session,
                existing_document,
                content_hash,
                connector,
                file_name,
                primary_hash,
            )
            if should_skip:
                return doc
            # Content changed - continue to update

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary with metadata
        document_metadata = {
            "file_name": file_name,
            "etl_service": "UNSTRUCTURED",
            "document_type": "File Document",
        }
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm, document_metadata
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        from app.utils.blocknote_converter import convert_markdown_to_blocknote

        # Convert markdown to BlockNote JSON
        blocknote_json = await convert_markdown_to_blocknote(file_in_markdown)
        if not blocknote_json:
            logging.warning(
                f"Failed to convert {file_name} to BlockNote JSON, document will not be editable"
            )

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
                "ETL_SERVICE": "UNSTRUCTURED",
            }
            existing_document.chunks = chunks
            existing_document.blocknote_document = blocknote_json
            existing_document.content_needs_reindexing = False
            existing_document.updated_at = get_current_timestamp()

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            # Determine document type based on connector
            doc_type = DocumentType.FILE
            if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
                doc_type = DocumentType.GOOGLE_DRIVE_FILE

            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=doc_type,
                document_metadata={
                    "FILE_NAME": file_name,
                    "ETL_SERVICE": "UNSTRUCTURED",
                },
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=primary_hash,
                blocknote_document=blocknote_json,
                content_needs_reindexing=False,
                updated_at=get_current_timestamp(),
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        # After successful document creation, check if this is a tax form
        await _process_tax_form_if_applicable(
            session, document, file_name, user_id, search_space_id
        )

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(f"Failed to process file document: {e!s}") from e


async def add_received_file_document_using_llamacloud(
    session: AsyncSession,
    file_name: str,
    llamacloud_markdown_document: str,
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
) -> Document | None:
    """
    Process and store document content parsed by LlamaCloud.

    Args:
        session: Database session
        file_name: Name of the processed file
        llamacloud_markdown_document: Markdown content from LlamaCloud parsing
        search_space_id: ID of the search space
        user_id: ID of the user
        connector: Optional connector info for Google Drive files

    Returns:
        Document object if successful, None if failed
    """
    try:
        # Combine all markdown documents into one
        file_in_markdown = llamacloud_markdown_document

        # Generate unique identifier hash (uses file_id for Google Drive, filename for others)
        primary_hash, legacy_hash = get_google_drive_unique_identifier(
            connector, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document exists (with migration support for Google Drive and content_hash fallback)
        existing_document = await find_existing_document_with_migration(
            session, primary_hash, legacy_hash, content_hash
        )

        if existing_document:
            # Handle existing document (rename detection, content change check)
            should_skip, doc = await handle_existing_document_update(
                session,
                existing_document,
                content_hash,
                connector,
                file_name,
                primary_hash,
            )
            if should_skip:
                return doc
            # Content changed - continue to update

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary with metadata
        document_metadata = {
            "file_name": file_name,
            "etl_service": "LLAMACLOUD",
            "document_type": "File Document",
        }
        summary_content, summary_embedding = await generate_document_summary(
            file_in_markdown, user_llm, document_metadata
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        from app.utils.blocknote_converter import convert_markdown_to_blocknote

        # Convert markdown to BlockNote JSON
        blocknote_json = await convert_markdown_to_blocknote(file_in_markdown)
        if not blocknote_json:
            logging.warning(
                f"Failed to convert {file_name} to BlockNote JSON, document will not be editable"
            )

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
                "ETL_SERVICE": "LLAMACLOUD",
            }
            existing_document.chunks = chunks
            existing_document.blocknote_document = blocknote_json
            existing_document.content_needs_reindexing = False
            existing_document.updated_at = get_current_timestamp()

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            # Determine document type based on connector
            doc_type = DocumentType.FILE
            if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
                doc_type = DocumentType.GOOGLE_DRIVE_FILE

            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=doc_type,
                document_metadata={
                    "FILE_NAME": file_name,
                    "ETL_SERVICE": "LLAMACLOUD",
                },
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=primary_hash,
                blocknote_document=blocknote_json,
                content_needs_reindexing=False,
                updated_at=get_current_timestamp(),
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        # After successful document creation, check if this is a tax form
        await _process_tax_form_if_applicable(
            session, document, file_name, user_id, search_space_id
        )

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(
            f"Failed to process file document using LlamaCloud: {e!s}"
        ) from e


async def add_received_file_document_using_docling(
    session: AsyncSession,
    file_name: str,
    docling_markdown_document: str,
    search_space_id: int,
    user_id: str,
    connector: dict | None = None,
) -> Document | None:
    """
    Process and store document content parsed by Docling.

    Args:
        session: Database session
        file_name: Name of the processed file
        docling_markdown_document: Markdown content from Docling parsing
        search_space_id: ID of the search space
        user_id: ID of the user
        connector: Optional connector info for Google Drive files

    Returns:
        Document object if successful, None if failed
    """
    try:
        file_in_markdown = docling_markdown_document

        # Generate unique identifier hash (uses file_id for Google Drive, filename for others)
        primary_hash, legacy_hash = get_google_drive_unique_identifier(
            connector, file_name, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(file_in_markdown, search_space_id)

        # Check if document exists (with migration support for Google Drive and content_hash fallback)
        existing_document = await find_existing_document_with_migration(
            session, primary_hash, legacy_hash, content_hash
        )

        if existing_document:
            # Handle existing document (rename detection, content change check)
            should_skip, doc = await handle_existing_document_update(
                session,
                existing_document,
                content_hash,
                connector,
                file_name,
                primary_hash,
            )
            if should_skip:
                return doc
            # Content changed - continue to update

        # Get user's long context LLM (needed for both create and update)
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search_space {search_space_id}"
            )

        # Generate summary using chunked processing for large documents
        from app.services.docling_service import create_docling_service

        docling_service = create_docling_service()

        summary_content = await docling_service.process_large_document_summary(
            content=file_in_markdown, llm=user_llm, document_title=file_name
        )

        # Enhance summary with metadata
        document_metadata = {
            "file_name": file_name,
            "etl_service": "DOCLING",
            "document_type": "File Document",
        }
        metadata_parts = []
        metadata_parts.append("# DOCUMENT METADATA")

        for key, value in document_metadata.items():
            if value:  # Only include non-empty values
                formatted_key = key.replace("_", " ").title()
                metadata_parts.append(f"**{formatted_key}:** {value}")

        metadata_section = "\n".join(metadata_parts)
        enhanced_summary_content = (
            f"{metadata_section}\n\n# DOCUMENT SUMMARY\n\n{summary_content}"
        )

        from app.config import config

        summary_embedding = config.embedding_model_instance.embed(
            enhanced_summary_content
        )

        # Process chunks
        chunks = await create_document_chunks(file_in_markdown)

        from app.utils.blocknote_converter import convert_markdown_to_blocknote

        # Convert markdown to BlockNote JSON
        blocknote_json = await convert_markdown_to_blocknote(file_in_markdown)
        if not blocknote_json:
            logging.warning(
                f"Failed to convert {file_name} to BlockNote JSON, document will not be editable"
            )

        # Update or create document
        if existing_document:
            # Update existing document
            existing_document.title = file_name
            existing_document.content = enhanced_summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "FILE_NAME": file_name,
                "ETL_SERVICE": "DOCLING",
            }
            existing_document.chunks = chunks
            existing_document.blocknote_document = blocknote_json
            existing_document.content_needs_reindexing = False
            existing_document.updated_at = get_current_timestamp()

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            # Determine document type based on connector
            doc_type = DocumentType.FILE
            if connector and connector.get("type") == DocumentType.GOOGLE_DRIVE_FILE:
                doc_type = DocumentType.GOOGLE_DRIVE_FILE

            document = Document(
                search_space_id=search_space_id,
                title=file_name,
                document_type=doc_type,
                document_metadata={
                    "FILE_NAME": file_name,
                    "ETL_SERVICE": "DOCLING",
                },
                content=enhanced_summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=primary_hash,
                blocknote_document=blocknote_json,
                content_needs_reindexing=False,
                updated_at=get_current_timestamp(),
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        raise db_error
    except Exception as e:
        await session.rollback()
        raise RuntimeError(
            f"Failed to process file document using Docling: {e!s}"
        ) from e


async def _update_document_from_connector(
    document: Document | None, connector: dict | None, session: AsyncSession
) -> None:
    """Helper to update document type and metadata from connector info."""
    if document and connector:
        if "type" in connector:
            document.document_type = connector["type"]
        if "metadata" in connector:
            # Merge with existing document_metadata (the actual column name)
            if not document.document_metadata:
                document.document_metadata = connector["metadata"]
            else:
                # Expand existing metadata with connector metadata
                merged = {**document.document_metadata, **connector["metadata"]}
                document.document_metadata = merged
        await session.commit()


async def _process_financial_data(
    session: AsyncSession,
    filename: str,
    financial_data: dict,
    search_space_id: int,
    user_id: str,
    file_path: str,
    task_logger: TaskLoggingService,
    log_entry: Log,
) -> Document:
    """Process parsed financial data and create document."""
    import json
    
    # Build markdown content from financial data
    markdown_parts = []
    metadata = financial_data.get("metadata", {})
    
    markdown_parts.append(f"# Financial Statement: {filename}\n")
    markdown_parts.append(f"**Institution:** {metadata.get('institution', 'Unknown')}\n")
    markdown_parts.append(f"**Format:** {metadata.get('format', 'Unknown')}\n")
    markdown_parts.append(f"**Parsed:** {metadata.get('parsed_at', '')}\n\n")
    
    # Add transactions
    transactions = financial_data.get("transactions", [])
    if transactions:
        markdown_parts.append(f"## Transactions ({len(transactions)} total)\n\n")
        for trans in transactions:
            date = trans.date.strftime("%Y-%m-%d") if hasattr(trans, 'date') else str(trans.get('date', ''))
            description = trans.description if hasattr(trans, 'description') else trans.get('description', '')
            amount = trans.amount if hasattr(trans, 'amount') else trans.get('amount', 0)
            trans_type = trans.transaction_type if hasattr(trans, 'transaction_type') else trans.get('transaction_type', '')
            
            markdown_parts.append(f"- **{date}** - {description}: ${amount:.2f} ({trans_type})\n")
    
    # Add holdings
    holdings = financial_data.get("holdings", [])
    if holdings:
        markdown_parts.append(f"\n## Investment Holdings ({len(holdings)} total)\n\n")
        for holding in holdings:
            symbol = holding.symbol if hasattr(holding, 'symbol') else holding.get('symbol', '')
            quantity = holding.quantity if hasattr(holding, 'quantity') else holding.get('quantity', 0)
            value = holding.value if hasattr(holding, 'value') else holding.get('value', 0)
            cost_basis = holding.cost_basis if hasattr(holding, 'cost_basis') else holding.get('cost_basis')
            gain_loss = holding.gain_loss if hasattr(holding, 'gain_loss') else holding.get('gain_loss')
            gain_loss_pct = holding.gain_loss_percent if hasattr(holding, 'gain_loss_percent') else holding.get('gain_loss_percent')
            
            # Handle None values for formatting
            value = value if value is not None else 0
            quantity = quantity if quantity is not None else 0
            
            # Basic info
            markdown_parts.append(f"- **{symbol}**: {quantity} shares @ ${value:.2f}")
            
            # Add cost basis and gains if available
            if cost_basis is not None and gain_loss is not None:
                sign = "+" if gain_loss >= 0 else ""
                markdown_parts.append(f" | Cost Basis: ${cost_basis:.2f} | Gain/Loss: {sign}${gain_loss:.2f}")
                if gain_loss_pct is not None:
                    markdown_parts.append(f" ({sign}{gain_loss_pct:.2f}%)")
            
            markdown_parts.append("\n")
    
    # Add balances
    balances = financial_data.get("balances", [])
    if balances:
        markdown_parts.append("\n## Account Balances\n\n")
        for balance in balances:
            account_type = balance.account_type if hasattr(balance, 'account_type') else balance.get('account_type', '')
            amount = balance.amount if hasattr(balance, 'amount') else balance.get('amount', 0)
            
            markdown_parts.append(f"- **{account_type}**: ${amount:.2f}\n")
    
    markdown_content = "".join(markdown_parts)
    
    # Store raw financial data as JSON metadata
    raw_financial_json = json.dumps({
        "transactions": [
            {
                "date": t.date.isoformat() if hasattr(t, 'date') else str(t.get('date', '')),
                "description": t.description if hasattr(t, 'description') else t.get('description', ''),
                "amount": float(t.amount) if hasattr(t, 'amount') else float(t.get('amount', 0)),
                "transaction_type": str(t.transaction_type) if hasattr(t, 'transaction_type') else str(t.get('transaction_type', '')),
                "balance": float(t.balance) if hasattr(t, 'balance') and t.balance else None,
                "category": t.category if hasattr(t, 'category') else t.get('category'),
                "merchant": t.merchant if hasattr(t, 'merchant') else t.get('merchant'),
            }
            for t in transactions
        ],
        "holdings": [
            {
                "symbol": h.symbol if hasattr(h, 'symbol') else h.get('symbol', ''),
                "quantity": float(h.quantity) if (hasattr(h, 'quantity') and h.quantity is not None) else 0.0,
                "value": float(h.value) if (hasattr(h, 'value') and h.value is not None) else 0.0,
                "cost_basis": float(h.cost_basis) if (hasattr(h, 'cost_basis') and h.cost_basis is not None) else None,
                "gain_loss": float(h.gain_loss) if (hasattr(h, 'gain_loss') and h.gain_loss is not None) else None,
                "gain_loss_percent": float(h.gain_loss_percent) if (hasattr(h, 'gain_loss_percent') and h.gain_loss_percent is not None) else None,
            }
            for h in holdings
        ],
        "metadata": metadata,
    }, indent=2)
    
    # Generate content hash from the markdown content
    content_hash = generate_content_hash(markdown_content, search_space_id)
    
    # For financial documents, use content_hash as unique identifier
    # This means: same transactions = same document (no duplicates)
    # but different statements = different documents
    unique_identifier_hash = generate_unique_identifier_hash(
        DocumentType.BANK_TRANSACTION, content_hash, search_space_id
    )
    
    # Check for duplicates based on content
    existing_doc = await check_duplicate_document(session, content_hash)
    
    if existing_doc:
        # Document with same content already exists - this is truly a duplicate
        await task_logger.log_task_success(
            log_entry,
            f"Financial document with same transactions already exists: {filename}",
            {"duplicate_detected": True, "document_id": existing_doc.id, "existing_filename": existing_doc.file_name},
        )
        return existing_doc
    
    # Create new document with embeddings and chunks for search
    
    # Save investment holdings to structured table if this is an investment file
    if holdings:
        await _save_investment_holdings(
            session=session,
            user_id=user_id,
            holdings_data=holdings,
            metadata=metadata,
            filename=filename,
        )
    
    # Get user's LLM for summary generation
    user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
    
    # Generate summary embedding for the document
    _, summary_embedding = await generate_document_summary(
        markdown_content,
        user_llm,
        {
            "institution": metadata.get("institution"),
            "transaction_count": len(transactions),
            "format": metadata.get("format"),
        }
    )
    
    # Create chunks for retrieval
    chunks = await create_document_chunks(markdown_content)
    
    new_doc = Document(
        search_space_id=search_space_id,
        title=filename,
        document_type=DocumentType.FILE,  # Use FILE type so it's searchable via knowledge base
        document_metadata={
            "FILE_NAME": filename,
            "financial_data": raw_financial_json,
            "institution": metadata.get("institution"),
            "format": metadata.get("format"),
            "document_subtype": metadata.get("document_subtype"),  # Add to top level for tools
            "transaction_count": len(transactions),
            "holdings_count": len(holdings),
            "is_financial_document": True,  # Flag to identify as financial data
        },
        content=markdown_content,
        content_hash=content_hash,
        unique_identifier_hash=unique_identifier_hash,
        embedding=summary_embedding,
        chunks=chunks,
        updated_at=get_current_timestamp(),
    )
    
    session.add(new_doc)
    await session.commit()
    await session.refresh(new_doc)
    
    await task_logger.log_task_success(
        log_entry,
        f"Successfully processed financial document: {filename}",
        {
            "document_id": new_doc.id,
            "transaction_count": len(transactions),
            "holdings_count": len(holdings),
        },
    )
    
    return new_doc


async def process_file_in_background(
    file_path: str,
    filename: str,
    search_space_id: int,
    user_id: str,
    session: AsyncSession,
    task_logger: TaskLoggingService,
    log_entry: Log,
    connector: dict
    | None = None,  # Optional: {"type": "GOOGLE_DRIVE_FILE", "metadata": {...}}
    notification: Notification
    | None = None,  # Optional notification for progress updates
) -> Document | None:
    try:
        # Check if the file is a financial statement (CSV, OFX)
        # Note: PDFs are checked separately and fall through to normal processing if not financial
        if filename.lower().endswith((".csv", ".ofx", ".qfx")):
            from app.parsers.parser_factory import ParserFactory
            
            # Read file content
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # Try to detect if this is a financial file
            detected_format = ParserFactory.detect_format(file_content, filename)
            
            # Handle CSV/OFX financial files
            if detected_format:
                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing financial file: {filename} ({detected_format})",
                    {"file_type": "financial", "format": str(detected_format)},
                )
                
                try:
                    parser = ParserFactory.get_parser(detected_format)
                    # Pass session context to parser for LLM access
                    financial_data = await parser.parse_file(
                        file_content, filename, session, user_id, search_space_id
                    )
                    
                    result = await _process_financial_data(
                        session, filename, financial_data, search_space_id, user_id, file_path, task_logger, log_entry
                    )
                    
                    # Clean up temp file
                    import os
                    with contextlib.suppress(Exception):
                        os.unlink(file_path)
                    
                    return result
                except Exception as e:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"Error parsing financial file: {filename}",
                        str(e),
                        {"file_type": "financial", "error": str(e)},
                    )
                    raise
        
        # Check if the file is a markdown or text file
        if filename.lower().endswith((".md", ".markdown", ".txt")):
            # Update notification: parsing stage
            if notification:
                await (
                    NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="parsing",
                        stage_message="Reading file",
                    )
                )

            await task_logger.log_task_progress(
                log_entry,
                f"Processing markdown/text file: {filename}",
                {"file_type": "markdown", "processing_stage": "reading_file"},
            )

            # For markdown files, read the content directly
            with open(file_path, encoding="utf-8") as f:
                markdown_content = f.read()

            # Clean up the temp file
            import os

            try:
                os.unlink(file_path)
            except Exception as e:
                print("Error deleting temp file", e)
                pass

            # Update notification: chunking stage
            if notification:
                await (
                    NotificationService.document_processing.notify_processing_progress(
                        session, notification, stage="chunking"
                    )
                )

            await task_logger.log_task_progress(
                log_entry,
                f"Creating document from markdown content: {filename}",
                {
                    "processing_stage": "creating_document",
                    "content_length": len(markdown_content),
                },
            )

            # Process markdown directly through specialized function
            result = await add_received_markdown_file_document(
                session, filename, markdown_content, search_space_id, user_id, connector
            )

            if connector:
                await _update_document_from_connector(result, connector, session)

            if result:
                await task_logger.log_task_success(
                    log_entry,
                    f"Successfully processed markdown file: {filename}",
                    {
                        "document_id": result.id,
                        "content_hash": result.content_hash,
                        "file_type": "markdown",
                    },
                )
                return result
            else:
                await task_logger.log_task_success(
                    log_entry,
                    f"Markdown file already exists (duplicate): {filename}",
                    {"duplicate_detected": True, "file_type": "markdown"},
                )
                return None

        else:
            # Import page limit service
            from app.services.page_limit_service import (
                PageLimitExceededError,
                PageLimitService,
            )

            # Initialize page limit service
            page_limit_service = PageLimitService(session)

            # CRITICAL: Estimate page count BEFORE making expensive ETL API calls
            # This prevents users from incurring costs on files that would exceed their limit
            try:
                estimated_pages_before = (
                    page_limit_service.estimate_pages_before_processing(file_path)
                )
            except Exception:
                # If estimation fails, use a conservative estimate based on file size
                import os

                file_size = os.path.getsize(file_path)
                estimated_pages_before = max(
                    1, file_size // (80 * 1024)
                )  # ~80KB per page

            await task_logger.log_task_progress(
                log_entry,
                f"Estimated {estimated_pages_before} pages for file: {filename}",
                {
                    "estimated_pages": estimated_pages_before,
                    "file_type": "document",
                },
            )

            # Check page limit BEFORE calling ETL service to avoid unnecessary costs
            try:
                await page_limit_service.check_page_limit(
                    user_id, estimated_pages_before
                )
            except PageLimitExceededError as e:
                await task_logger.log_task_failure(
                    log_entry,
                    f"Page limit exceeded before processing: {filename}",
                    str(e),
                    {
                        "error_type": "PageLimitExceeded",
                        "pages_used": e.pages_used,
                        "pages_limit": e.pages_limit,
                        "estimated_pages": estimated_pages_before,
                    },
                )
                # Clean up the temp file
                import os

                with contextlib.suppress(Exception):
                    os.unlink(file_path)

                raise HTTPException(
                    status_code=403,
                    detail=str(e),
                ) from e

            if app_config.ETL_SERVICE == "UNSTRUCTURED":
                # Update notification: parsing stage
                if notification:
                    await NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="parsing",
                        stage_message="Extracting content",
                    )

                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing file with Unstructured ETL: {filename}",
                    {
                        "file_type": "document",
                        "etl_service": "UNSTRUCTURED",
                        "processing_stage": "loading",
                    },
                )

                from langchain_unstructured import UnstructuredLoader

                # Process the file
                loader = UnstructuredLoader(
                    file_path,
                    mode="elements",
                    post_processors=[],
                    languages=["eng"],
                    include_orig_elements=False,
                    include_metadata=False,
                    strategy="auto",
                )

                docs = await loader.aload()

                # Update notification: chunking stage
                if notification:
                    await NotificationService.document_processing.notify_processing_progress(
                        session, notification, stage="chunking", chunks_count=len(docs)
                    )

                await task_logger.log_task_progress(
                    log_entry,
                    f"Unstructured ETL completed, creating document: {filename}",
                    {"processing_stage": "etl_complete", "elements_count": len(docs)},
                )

                # Verify actual page count from parsed documents
                actual_pages = page_limit_service.estimate_pages_from_elements(docs)

                # Use the higher of the two estimates for safety (in case pre-estimate was too low)
                final_page_count = max(estimated_pages_before, actual_pages)

                # If actual is significantly higher than estimate, log a warning
                if actual_pages > estimated_pages_before * 1.5:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"Actual page count higher than estimate: {filename}",
                        {
                            "estimated_before": estimated_pages_before,
                            "actual_pages": actual_pages,
                            "using_count": final_page_count,
                        },
                    )

                # Clean up the temp file
                import os

                try:
                    os.unlink(file_path)
                except Exception as e:
                    print("Error deleting temp file", e)
                    pass

                # Pass the documents to the existing background task
                result = await add_received_file_document_using_unstructured(
                    session, filename, docs, search_space_id, user_id, connector
                )

                if connector:
                    await _update_document_from_connector(result, connector, session)

                if result:
                    # Update page usage after successful processing
                    # allow_exceed=True because document was already created after passing initial check
                    await page_limit_service.update_page_usage(
                        user_id, final_page_count, allow_exceed=True
                    )

                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with Unstructured: {filename}",
                        {
                            "document_id": result.id,
                            "content_hash": result.content_hash,
                            "file_type": "document",
                            "etl_service": "UNSTRUCTURED",
                            "pages_processed": final_page_count,
                        },
                    )
                    return result
                else:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "UNSTRUCTURED",
                        },
                    )
                    return None

            elif app_config.ETL_SERVICE == "LLAMACLOUD":
                # Update notification: parsing stage
                if notification:
                    await NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="parsing",
                        stage_message="Extracting content",
                    )

                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing file with LlamaCloud ETL: {filename}",
                    {
                        "file_type": "document",
                        "etl_service": "LLAMACLOUD",
                        "processing_stage": "parsing",
                        "estimated_pages": estimated_pages_before,
                    },
                )

                # Parse file with retry logic for SSL/connection errors (common with large files)
                result = await parse_with_llamacloud_retry(
                    file_path=file_path,
                    estimated_pages=estimated_pages_before,
                    task_logger=task_logger,
                    log_entry=log_entry,
                )

                # Clean up the temp file
                import os

                try:
                    os.unlink(file_path)
                except Exception as e:
                    print("Error deleting temp file", e)
                    pass

                # Get markdown documents from the result
                markdown_documents = await result.aget_markdown_documents(
                    split_by_page=False
                )

                # Update notification: chunking stage
                if notification:
                    await NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="chunking",
                        chunks_count=len(markdown_documents),
                    )

                await task_logger.log_task_progress(
                    log_entry,
                    f"LlamaCloud parsing completed, creating documents: {filename}",
                    {
                        "processing_stage": "parsing_complete",
                        "documents_count": len(markdown_documents),
                    },
                )

                # Check if LlamaCloud returned any documents
                if not markdown_documents or len(markdown_documents) == 0:
                    await task_logger.log_task_failure(
                        log_entry,
                        f"LlamaCloud parsing returned no documents: {filename}",
                        "ETL service returned empty document list",
                        {
                            "error_type": "EmptyDocumentList",
                            "etl_service": "LLAMACLOUD",
                        },
                    )
                    raise ValueError(
                        f"LlamaCloud parsing returned no documents for {filename}"
                    )

                # Verify actual page count from parsed markdown documents
                actual_pages = page_limit_service.estimate_pages_from_markdown(
                    markdown_documents
                )

                # Use the higher of the two estimates for safety (in case pre-estimate was too low)
                final_page_count = max(estimated_pages_before, actual_pages)

                # If actual is significantly higher than estimate, log a warning
                if actual_pages > estimated_pages_before * 1.5:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"Actual page count higher than estimate: {filename}",
                        {
                            "estimated_before": estimated_pages_before,
                            "actual_pages": actual_pages,
                            "using_count": final_page_count,
                        },
                    )

                # Track if any document was successfully created (not a duplicate)
                any_doc_created = False
                last_created_doc = None

                for doc in markdown_documents:
                    # Extract text content from the markdown documents
                    markdown_content = doc.text

                    # Process the documents using our LlamaCloud background task
                    doc_result = await add_received_file_document_using_llamacloud(
                        session,
                        filename,
                        llamacloud_markdown_document=markdown_content,
                        search_space_id=search_space_id,
                        user_id=user_id,
                        connector=connector,
                    )

                    # Track if this document was successfully created
                    if doc_result:
                        any_doc_created = True
                        last_created_doc = doc_result

                # Update page usage once after processing all documents
                # Only update if at least one document was created (not all duplicates)
                if any_doc_created:
                    # Update page usage after successful processing
                    # allow_exceed=True because document was already created after passing initial check
                    await page_limit_service.update_page_usage(
                        user_id, final_page_count, allow_exceed=True
                    )

                    if connector:
                        await _update_document_from_connector(
                            last_created_doc, connector, session
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with LlamaCloud: {filename}",
                        {
                            "document_id": last_created_doc.id,
                            "content_hash": last_created_doc.content_hash,
                            "file_type": "document",
                            "etl_service": "LLAMACLOUD",
                            "pages_processed": final_page_count,
                            "documents_count": len(markdown_documents),
                        },
                    )
                    return last_created_doc
                else:
                    # All documents were duplicates (markdown_documents was not empty, but all returned None)
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "LLAMACLOUD",
                            "documents_count": len(markdown_documents),
                        },
                    )
                    return None

            elif app_config.ETL_SERVICE == "DOCLING":
                # Update notification: parsing stage
                if notification:
                    await NotificationService.document_processing.notify_processing_progress(
                        session,
                        notification,
                        stage="parsing",
                        stage_message="Extracting content",
                    )

                await task_logger.log_task_progress(
                    log_entry,
                    f"Processing file with Docling ETL: {filename}",
                    {
                        "file_type": "document",
                        "etl_service": "DOCLING",
                        "processing_stage": "parsing",
                    },
                )

                # Use Docling service for document processing
                from app.services.docling_service import create_docling_service

                # Create Docling service
                docling_service = create_docling_service()

                # Suppress pdfminer warnings that can cause processing to hang
                # These warnings are harmless but can spam logs and potentially halt processing
                # Suppress both Python warnings and logging warnings from pdfminer
                pdfminer_logger = getLogger("pdfminer")
                original_level = pdfminer_logger.level

                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", category=UserWarning, module="pdfminer"
                    )
                    warnings.filterwarnings(
                        "ignore",
                        message=".*Cannot set gray non-stroke color.*",
                    )
                    warnings.filterwarnings("ignore", message=".*invalid float value.*")

                    # Temporarily suppress pdfminer logging warnings
                    pdfminer_logger.setLevel(ERROR)

                    try:
                        # Process the document
                        result = await docling_service.process_document(
                            file_path, filename
                        )
                    finally:
                        # Restore original logging level
                        pdfminer_logger.setLevel(original_level)

                # Clean up the temp file
                import os

                try:
                    os.unlink(file_path)
                except Exception as e:
                    print("Error deleting temp file", e)
                    pass

                await task_logger.log_task_progress(
                    log_entry,
                    f"Docling parsing completed, creating document: {filename}",
                    {
                        "processing_stage": "parsing_complete",
                        "content_length": len(result["content"]),
                    },
                )

                # Verify actual page count from content length
                actual_pages = page_limit_service.estimate_pages_from_content_length(
                    len(result["content"])
                )

                # Use the higher of the two estimates for safety (in case pre-estimate was too low)
                final_page_count = max(estimated_pages_before, actual_pages)

                # If actual is significantly higher than estimate, log a warning
                if actual_pages > estimated_pages_before * 1.5:
                    await task_logger.log_task_progress(
                        log_entry,
                        f"Actual page count higher than estimate: {filename}",
                        {
                            "estimated_before": estimated_pages_before,
                            "actual_pages": actual_pages,
                            "using_count": final_page_count,
                        },
                    )

                # Update notification: chunking stage
                if notification:
                    await NotificationService.document_processing.notify_processing_progress(
                        session, notification, stage="chunking"
                    )

                # Process the document using our Docling background task
                doc_result = await add_received_file_document_using_docling(
                    session,
                    filename,
                    docling_markdown_document=result["content"],
                    search_space_id=search_space_id,
                    user_id=user_id,
                    connector=connector,
                )

                if doc_result:
                    # Update page usage after successful processing
                    # allow_exceed=True because document was already created after passing initial check
                    await page_limit_service.update_page_usage(
                        user_id, final_page_count, allow_exceed=True
                    )

                    if connector:
                        await _update_document_from_connector(
                            doc_result, connector, session
                        )

                    await task_logger.log_task_success(
                        log_entry,
                        f"Successfully processed file with Docling: {filename}",
                        {
                            "document_id": doc_result.id,
                            "content_hash": doc_result.content_hash,
                            "file_type": "document",
                            "etl_service": "DOCLING",
                            "pages_processed": final_page_count,
                        },
                    )
                    return doc_result
                else:
                    await task_logger.log_task_success(
                        log_entry,
                        f"Document already exists (duplicate): {filename}",
                        {
                            "duplicate_detected": True,
                            "file_type": "document",
                            "etl_service": "DOCLING",
                        },
                    )
                    return None
    except Exception as e:
        await session.rollback()

        # For page limit errors, use the detailed message from the exception
        from app.services.page_limit_service import PageLimitExceededError

        if isinstance(e, PageLimitExceededError):
            error_message = str(e)
        elif isinstance(e, HTTPException) and "page limit" in str(e.detail).lower():
            error_message = str(e.detail)
        else:
            error_message = f"Failed to process file: {filename}"

        await task_logger.log_task_failure(
            log_entry,
            error_message,
            str(e),
            {"error_type": type(e).__name__, "filename": filename},
        )
        import logging

        logging.error(f"Error processing file in background: {error_message}")
        raise  # Re-raise so the wrapper can also handle it
