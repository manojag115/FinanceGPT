"""
Base indexer for Plaid-powered bank connectors.

All bank-specific connectors (Chase, Fidelity, etc.) inherit from this base class.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, SearchSourceConnector
from app.parsers.base_financial_parser import BankTransaction, TransactionType
from app.services.llm_service import get_user_long_context_llm
from app.services.plaid_service import PlaidService
from app.utils.document_converters import (
    create_document_chunks,
    generate_document_summary,
)

logger = logging.getLogger(__name__)


def get_current_timestamp() -> datetime:
    """Get the current timestamp with timezone for updated_at field."""
    return datetime.now(UTC)

logger = logging.getLogger(__name__)


class PlaidBaseIndexer:
    """
    Base class for all Plaid-powered bank connectors.

    Subclasses should define:
    - connector_name: Human-readable name (e.g., "Chase Bank")
    - institution_id: Plaid institution ID (e.g., "ins_3" for Chase)
    """

    connector_name: str = "Bank"
    institution_id: str | None = None  # Plaid institution ID

    def __init__(self):
        """Initialize Plaid service."""
        self.plaid_service = PlaidService()

    async def index_transactions(
        self,
        session: AsyncSession,
        connector: SearchSourceConnector,
        user_id: str,
        days_back: int = 90,
    ) -> dict[str, Any]:
        """
        Fetch and index transactions from Plaid.

        Args:
            session: Database session
            connector: Search source connector with Plaid access token
            user_id: User ID
            days_back: Number of days to fetch (default 90)

        Returns:
            Indexing result with transaction count
        """
        try:
            # Get access token from connector config
            access_token = connector.config.get("access_token")
            if not access_token:
                raise ValueError(f"No access token found for {self.connector_name}")

            # Fetch transactions from Plaid
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            transactions = await self.plaid_service.get_transactions(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
            )

            if not transactions:
                logger.info(f"No transactions found for {self.connector_name}")
                return {"transaction_count": 0, "documents_created": 0}

            # Get accounts to enrich transaction data
            accounts = await self.plaid_service.get_accounts(access_token)
            account_map = {acc["account_id"]: acc for acc in accounts}

            # Group transactions by month for better organization
            transactions_by_month = self._group_by_month(transactions)

            documents_created = 0

            for month_key, month_transactions in transactions_by_month.items():
                # Convert Plaid transactions to BankTransaction format
                bank_transactions = []
                for txn in month_transactions:
                    account = account_map.get(txn["account_id"], {})
                    bank_transactions.append(
                        self._convert_plaid_transaction(txn, account)
                    )

                # Create document for this month's transactions
                doc_created = await self._create_transaction_document(
                    session=session,
                    transactions=bank_transactions,
                    month_key=month_key,
                    search_space_id=connector.search_space_id,
                    user_id=user_id,
                    connector_id=connector.id,
                )

                if doc_created:
                    documents_created += 1

            return {
                "transaction_count": len(transactions),
                "documents_created": documents_created,
            }

        except Exception as e:
            logger.error(f"Error indexing {self.connector_name} transactions: {e}")
            raise

    def _group_by_month(
        self, transactions: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group transactions by month (YYYY-MM)."""
        grouped = {}
        for txn in transactions:
            date_str = str(txn["date"])  # Format: YYYY-MM-DD
            month_key = date_str[:7]  # Get YYYY-MM
            if month_key not in grouped:
                grouped[month_key] = []
            grouped[month_key].append(txn)
        return grouped

    def _convert_plaid_transaction(
        self, plaid_txn: dict[str, Any], account: dict[str, Any]
    ) -> BankTransaction:
        """Convert Plaid transaction format to BankTransaction."""
        # Plaid amounts are positive for outflows (expenses), negative for inflows (income)
        # We'll keep that convention
        amount = float(plaid_txn["amount"])

        # Determine transaction type from category
        if amount > 0:
            trans_type = TransactionType.PURCHASE
        elif amount < 0:
            trans_type = TransactionType.DEPOSIT
        else:
            trans_type = TransactionType.OTHER

        # Parse date
        txn_date = datetime.fromisoformat(str(plaid_txn["date"]))

        return BankTransaction(
            date=txn_date,
            description=plaid_txn["name"],
            amount=amount,
            transaction_type=trans_type,
            category=plaid_txn.get("category", []),
            balance=None,  # Plaid doesn't provide running balance in transactions
            raw_data={
                "plaid_transaction_id": plaid_txn["transaction_id"],
                "account_id": plaid_txn["account_id"],
                "account_name": account.get("name"),
                "merchant_name": plaid_txn.get("merchant_name"),
                "pending": plaid_txn.get("pending", False),
                "payment_channel": plaid_txn.get("payment_channel"),
            },
        )

    async def _create_transaction_document(
        self,
        session: AsyncSession,
        transactions: list[BankTransaction],
        month_key: str,
        search_space_id: int,
        user_id: str,
        connector_id: int,
    ) -> bool:
        """
        Create a document from transactions.

        Args:
            session: Database session
            transactions: List of BankTransaction objects
            month_key: Month identifier (YYYY-MM)
            search_space_id: Search space ID
            user_id: User ID
            connector_id: Connector ID

        Returns:
            True if document was created
        """
        # Build markdown content
        markdown_parts = []
        markdown_parts.append(
            f"# {self.connector_name} - Transactions for {month_key}\n\n"
        )
        markdown_parts.append(f"**Total Transactions:** {len(transactions)}\n\n")

        # Calculate totals
        total_spent = sum(t.amount for t in transactions if t.amount > 0)
        total_received = sum(abs(t.amount) for t in transactions if t.amount < 0)

        markdown_parts.append(f"**Total Spent:** ${total_spent:.2f}\n")
        markdown_parts.append(f"**Total Received:** ${total_received:.2f}\n\n")

        # Add transactions
        markdown_parts.append("## Transactions\n\n")
        for txn in sorted(transactions, key=lambda t: t.date):
            date_str = txn.date.strftime("%Y-%m-%d")
            amount_str = f"${abs(txn.amount):.2f}"
            if txn.amount > 0:
                amount_str = f"-{amount_str}"  # Expense
            else:
                amount_str = f"+{amount_str}"  # Income

            category_str = (
                " | ".join(txn.category) if txn.category else txn.transaction_type
            )
            markdown_parts.append(
                f"- **{date_str}** - {txn.description}: {amount_str} ({category_str})\n"
            )

        markdown_content = "".join(markdown_parts)

        # Check for duplicate
        from hashlib import sha256

        content_hash = sha256(markdown_content.encode()).hexdigest()

        stmt = select(Document).where(Document.content_hash == content_hash)
        result = await session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            logger.info(
                f"Document for {self.connector_name} {month_key} already exists"
            )
            return False

        # Get LLM for embeddings
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

        # Generate summary and embedding
        summary, summary_embedding = await generate_document_summary(
            markdown_content,
            user_llm,
            {
                "connector": self.connector_name,
                "month": month_key,
                "transaction_count": len(transactions),
            },
        )

        # Create chunks
        chunks = await create_document_chunks(content=markdown_content)

        # Create document
        doc = Document(
            search_space_id=search_space_id,
            title=f"{self.connector_name} - {month_key}",
            document_type=DocumentType.FILE,  # Use FILE type so it's searchable
            document_metadata={
                "connector_id": connector_id,
                "connector_name": self.connector_name,
                "month": month_key,
                "transaction_count": len(transactions),
                "total_spent": total_spent,
                "total_received": total_received,
                "is_plaid_document": True,
            },
            content=markdown_content,
            content_hash=content_hash,
            unique_identifier_hash=content_hash,  # Use content hash as unique ID
            embedding=summary_embedding,
            chunks=chunks,
            updated_at=get_current_timestamp(),
        )

        session.add(doc)
        await session.commit()

        logger.info(
            f"Created document for {self.connector_name} {month_key} with {len(chunks)} chunks"
        )
        return True
