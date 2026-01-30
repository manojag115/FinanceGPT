"""
PDF bank statement parser.

Extracts transactions from PDF bank statements (Chase, Discover, etc.)
"""

import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any

from app.parsers.base_financial_parser import (
    BankTransaction,
    BaseFinancialParser,
)

logger = logging.getLogger(__name__)


class PDFStatementParser(BaseFinancialParser):
    """Parser for PDF bank statements."""

    def __init__(self):
        """Initialize PDF statement parser."""
        super().__init__("PDF Statement")

    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Parse PDF bank statement.

        Args:
            file_content: PDF file bytes
            filename: Original filename

        Returns:
            Parsed transactions and metadata
        """
        try:
            # Extract text from PDF
            text = await self._extract_pdf_text(file_content)

            # Detect institution
            institution = self._detect_institution(text)

            # Parse transactions based on institution
            if "chase" in institution.lower():
                transactions = await self._parse_chase_pdf(text)
            elif "discover" in institution.lower():
                transactions = await self._parse_discover_pdf(text)
            elif "bank of america" in institution.lower() or "boa" in institution.lower():
                transactions = await self._parse_generic_pdf(text)
            else:
                # Generic parsing
                transactions = await self._parse_generic_pdf(text)

            return {
                "transactions": transactions,
                "holdings": [],
                "balances": [],
                "metadata": {
                    "institution": institution,
                    "format": "pdf",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "transaction_count": len(transactions),
                },
            }

        except Exception as e:
            logger.error(f"Error parsing PDF statement: {e}", exc_info=True)
            raise

    async def _extract_pdf_text(self, pdf_content: bytes) -> str:
        """Extract text from PDF."""
        try:
            # Try pypdf first (lightweight)
            from pypdf import PdfReader
            import io

            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)

            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text

        except Exception as e:
            logger.warning(f"pypdf failed, trying pdfplumber: {e}")

            try:
                # Fallback to pdfplumber (more robust)
                import pdfplumber
                import io

                pdf_file = io.BytesIO(pdf_content)
                text = ""

                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                return text

            except ImportError:
                msg = "Neither pypdf nor pdfplumber is installed. Install with: pip install pypdf pdfplumber"
                raise ImportError(msg) from None
            except Exception as e2:
                raise Exception(f"Failed to extract PDF text: {e2}") from e2

    def _detect_institution(self, text: str) -> str:
        """Detect financial institution from PDF text."""
        text_lower = text.lower()

        if "fidelity" in text_lower:
            return "Fidelity"
        elif "chase" in text_lower or "jpmorgan" in text_lower:
            return "Chase"
        elif "discover" in text_lower:
            return "Discover"
        elif "bank of america" in text_lower or "boa" in text_lower:
            return "Bank of America"
        elif "wells fargo" in text_lower:
            return "Wells Fargo"
        elif "capital one" in text_lower:
            return "Capital One"
        elif "american express" in text_lower or "amex" in text_lower:
            return "American Express"
        elif "citi" in text_lower or "citibank" in text_lower:
            return "Citibank"
        else:
            return "Unknown Bank"

    async def _parse_chase_pdf(self, text: str) -> list[BankTransaction]:
        """Parse Chase PDF statement."""
        transactions = []

        # Chase PDF format typically has lines like:
        # 01/15 WHOLE FOODS MARKET -125.50
        # 01/16 PAYCHECK DIRECT DEP 3,500.00

        # Pattern: MM/DD Description Amount
        pattern = r"(\d{2}/\d{2})\s+(.+?)\s+([-$,\d.]+)"

        for match in re.finditer(pattern, text):
            try:
                date_str = match.group(1)
                description = match.group(2).strip()
                amount_str = match.group(3)

                # Skip header lines
                if any(word in description.upper() for word in ["DATE", "DESCRIPTION", "AMOUNT", "BALANCE"]):
                    continue

                # Parse date (add current year)
                current_year = datetime.now().year
                date = datetime.strptime(f"{date_str}/{current_year}", "%m/%d/%Y")

                # Parse amount
                amount = self._parse_amount(amount_str)

                # Determine transaction type
                trans_type = self._determine_transaction_type(amount, description)

                transaction = BankTransaction(
                    date=date,
                    description=description,
                    amount=amount,
                    transaction_type=trans_type,
                    raw_data={"source": "pdf", "line": match.group(0)},
                )

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Chase PDF line: {e}, line: {match.group(0)}")
                continue

        return transactions

    async def _parse_discover_pdf(self, text: str) -> list[BankTransaction]:
        """Parse Discover PDF statement."""
        transactions = []

        # Discover format: Trans Date Post Date Description Amount
        # 01/15/24 01/16/24 TARGET STORE -89.99

        pattern = r"(\d{2}/\d{2}/\d{2,4})\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([-$,\d.]+)"

        for match in re.finditer(pattern, text):
            try:
                trans_date_str = match.group(1)
                description = match.group(3).strip()
                amount_str = match.group(4)

                # Parse date
                date = self._parse_date(trans_date_str)

                # Parse amount
                amount = self._parse_amount(amount_str)

                # Determine transaction type
                trans_type = self._determine_transaction_type(amount, description)

                transaction = BankTransaction(
                    date=date,
                    description=description,
                    amount=amount,
                    transaction_type=trans_type,
                    raw_data={"source": "pdf", "line": match.group(0)},
                )

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Discover PDF line: {e}")
                continue

        return transactions

    async def _parse_generic_pdf(self, text: str) -> list[BankTransaction]:
        """Generic PDF statement parser."""
        transactions = []

        # Try multiple common patterns
        patterns = [
            r"(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+([-$,\d.]+)",  # Date Description Amount
            r"(\d{2}/\d{2})\s+(.+?)\s+([-$,\d.]+)",  # MM/DD Description Amount
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount_str = match.group(3)

                    # Skip header lines
                    if any(word in description.upper() for word in ["DATE", "DESCRIPTION", "AMOUNT"]):
                        continue

                    # Skip if description is too short (likely not a transaction)
                    if len(description) < 3:
                        continue

                    # Parse date
                    try:
                        date = self._parse_date(date_str)
                    except ValueError:
                        continue

                    # Parse amount
                    amount = self._parse_amount(amount_str)

                    # Skip zero amounts
                    if amount == 0:
                        continue

                    # Determine transaction type
                    trans_type = self._determine_transaction_type(amount, description)

                    transaction = BankTransaction(
                        date=date,
                        description=description,
                        amount=amount,
                        transaction_type=trans_type,
                        raw_data={"source": "pdf", "line": match.group(0)},
                    )

                    transactions.append(transaction)

                except Exception as e:
                    logger.debug(f"Error parsing generic PDF line: {e}")
                    continue

        # Remove duplicates (same date + description + amount)
        seen = set()
        unique_transactions = []
        for trans in transactions:
            key = (trans.date, trans.description, trans.amount)
            if key not in seen:
                seen.add(key)
                unique_transactions.append(trans)

        return unique_transactions
