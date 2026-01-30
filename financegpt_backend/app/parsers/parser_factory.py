"""
Parser factory for selecting the appropriate financial parser.
"""

import logging
from typing import Any

from app.db import SearchSourceConnectorType
from app.parsers.base_financial_parser import BaseFinancialParser
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
            SearchSourceConnectorType.OFX_UPLOAD: OFXParser(),
            # LLM parser handles ALL CSV formats (holdings and transactions)
            SearchSourceConnectorType.GENERIC_INVESTMENT_CSV: LLMCSVParser(),
            SearchSourceConnectorType.GENERIC_BANK_CSV: LLMCSVParser(),
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

        # Use LLM parser for ALL CSV files (privacy-first universal parser)
        if filename_lower.endswith(".csv"):
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
