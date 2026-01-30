"""
Parser factory for selecting the appropriate financial parser.
"""

import logging
from typing import Any

from app.db import SearchSourceConnectorType
from app.parsers.base_financial_parser import BaseFinancialParser
from app.parsers.chase_parser import ChaseBankParser, ChaseCreditParser, ChaseParser
from app.parsers.discover_parser import DiscoverParser
from app.parsers.fidelity_parser import FidelityParser
from app.parsers.llm_csv_parser import LLMCSVParser
from app.parsers.ofx_parser import OFXParser
from app.parsers.pdf_statement_parser import PDFStatementParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """Factory for creating financial statement parsers."""

    @staticmethod
    def get_parser(
        connector_type: SearchSourceConnectorType,
    ) -> BaseFinancialParser:
        """
        Get appropriate parser for connector type.

        Args:
            connector_type: Type of financial connector

        Returns:
            Parser instance

        Raises:
            ValueError: If connector type not supported
        """
        parser_map = {
            SearchSourceConnectorType.CHASE_BANK: ChaseBankParser(),
            SearchSourceConnectorType.CHASE_CREDIT: ChaseCreditParser(),
            SearchSourceConnectorType.FIDELITY_INVESTMENTS: FidelityParser(),
            SearchSourceConnectorType.DISCOVER_CREDIT: DiscoverParser(),
            SearchSourceConnectorType.OFX_UPLOAD: OFXParser(),
            # Generic parsers
            SearchSourceConnectorType.GENERIC_BANK_CSV: ChaseParser(),  # Use Chase format as default
            SearchSourceConnectorType.GENERIC_INVESTMENT_CSV: LLMCSVParser(),  # Use LLM for unknown investment CSVs
        }

        parser = parser_map.get(connector_type)
        if not parser:
            msg = f"No parser available for connector type: {connector_type}"
            raise ValueError(msg)

        return parser

    @staticmethod
    async def parse_pdf_statement(file_content: bytes, filename: str) -> dict[str, Any]:
        """
        Parse PDF bank statement.

        Args:
            file_content: PDF file bytes
            filename: Original filename

        Returns:
            Parsed financial data or None if not a financial statement
        """
        parser = PDFStatementParser()
        return await parser.parse_file(file_content, filename)

    @staticmethod
    def detect_format(file_content: bytes, filename: str) -> SearchSourceConnectorType | None:
        """
        Auto-detect file format from content and filename.

        Args:
            file_content: File bytes
            filename: Original filename

        Returns:
            Detected connector type, or None if not a financial file
        """
        filename_lower = filename.lower()

        # Check file extension first
        if filename_lower.endswith(".pdf"):
            # PDFs need text extraction to detect if they're financial statements
            return None  # Will be handled specially

        if filename_lower.endswith((".ofx", ".qfx")):
            return SearchSourceConnectorType.OFX_UPLOAD

        # For CSV, try to detect from content
        if filename_lower.endswith(".csv"):
            try:
                # Decode first few lines
                text_preview = file_content[:1000].decode("utf-8-sig")

                # Check for institution-specific headers
                if "Chase" in text_preview or "Transaction Date,Post Date" in text_preview:
                    if "Transaction Date" in text_preview:
                        return SearchSourceConnectorType.CHASE_CREDIT
                    return SearchSourceConnectorType.CHASE_BANK

                if "Fidelity" in text_preview or "Symbol,Description,Quantity" in text_preview:
                    return SearchSourceConnectorType.FIDELITY_INVESTMENTS

                if "Discover" in text_preview or "Trans. Date,Post Date" in text_preview:
                    return SearchSourceConnectorType.DISCOVER_CREDIT

                # Check if it looks like investment holdings (has Symbol/Ticker + Quantity columns)
                headers_lower = text_preview.lower()
                has_symbol = any(word in headers_lower for word in ["symbol", "ticker"])
                has_quantity = any(word in headers_lower for word in ["quantity", "shares", "qty"])
                
                if has_symbol and has_quantity:
                    # Unknown investment CSV - use LLM parser
                    return SearchSourceConnectorType.GENERIC_INVESTMENT_CSV
                
                # Check if it looks like transactions (has Date + Amount/Description)
                has_date = any(word in headers_lower for word in ["date", "transaction date", "trans. date"])
                has_amount = any(word in headers_lower for word in ["amount", "price", "$"])
                
                if has_date and has_amount:
                    # Unknown transaction CSV - use generic bank parser
                    return SearchSourceConnectorType.GENERIC_BANK_CSV

                # Default: try LLM parser for any CSV
                return SearchSourceConnectorType.GENERIC_INVESTMENT_CSV

            except Exception as e:
                logger.warning("Error detecting CSV format: %s", e)
                # Fallback to LLM parser
                return SearchSourceConnectorType.GENERIC_INVESTMENT_CSV

        # Not a recognized financial file format
        return None

    @staticmethod
    async def parse_auto(
        file_content: bytes, filename: str
    ) -> tuple[SearchSourceConnectorType, dict[str, Any]]:
        """
        Auto-detect format and parse file.

        Args:
            file_content: File bytes
            filename: Original filename

        Returns:
            Tuple of (detected connector type, parsed data)
        """
        connector_type = ParserFactory.detect_format(file_content, filename)
        parser = ParserFactory.get_parser(connector_type)
        parsed_data = await parser.parse_file(file_content, filename)

        return connector_type, parsed_data
