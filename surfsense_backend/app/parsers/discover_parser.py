"""
Discover Credit Card CSV parser.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Any

from app.parsers.base_financial_parser import (
    BankTransaction,
    BaseFinancialParser,
    TransactionType,
)

logger = logging.getLogger(__name__)


class DiscoverParser(BaseFinancialParser):
    """Parser for Discover credit card statements."""

    def __init__(self):
        """Initialize Discover parser."""
        super().__init__("Discover")

    async def parse_file(
        self, file_content: bytes, filename: str
    ) -> dict[str, Any]:
        """
        Parse Discover CSV file.

        Discover CSV format:
        Trans. Date,Post Date,Description,Amount,Category
        
        Args:
            file_content: CSV file bytes
            filename: Original filename

        Returns:
            Parsed transactions and metadata
        """
        try:
            # Decode CSV
            text_content = file_content.decode("utf-8-sig")  # Handle BOM
            csv_reader = csv.DictReader(io.StringIO(text_content))

            fieldnames = csv_reader.fieldnames
            if not fieldnames:
                msg = "Empty CSV file"
                raise ValueError(msg)

            transactions = await self._parse_transactions(csv_reader)

            return {
                "transactions": transactions,
                "holdings": [],
                "balances": [],
                "metadata": {
                    "institution": self.institution_name,
                    "format": "credit_card",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "transaction_count": len(transactions),
                },
            }

        except Exception as e:
            logger.error(f"Error parsing Discover CSV: {e}", exc_info=True)
            raise

    async def _parse_transactions(
        self, csv_reader: csv.DictReader
    ) -> list[BankTransaction]:
        """
        Parse Discover transaction CSV.

        Format: Trans. Date,Post Date,Description,Amount,Category
        """
        transactions = []

        for row in csv_reader:
            try:
                # Skip header or empty rows
                if not row.get("Description") or row.get("Description") == "Description":
                    continue

                # Parse date (prefer Trans. Date, fall back to Post Date)
                date_str = row.get("Trans. Date") or row.get("Post Date", "")
                if not date_str:
                    continue
                date = self._parse_date(date_str)

                # Parse amount (negative for purchases, positive for payments/credits)
                amount_str = row.get("Amount", "0")
                amount = self._parse_amount(amount_str)

                # Description
                description = row.get("Description", "").strip()

                # Category (Discover provides this)
                category = row.get("Category", "").strip() or None

                # Determine transaction type
                # Negative amounts are purchases, positive are payments/credits
                if amount < 0:
                    trans_type = TransactionType.PURCHASE
                elif "payment" in description.lower():
                    trans_type = TransactionType.PAYMENT
                elif "cashback" in description.lower() or "reward" in description.lower():
                    trans_type = TransactionType.CREDIT
                else:
                    trans_type = TransactionType.CREDIT

                transaction = BankTransaction(
                    date=date,
                    description=description,
                    amount=amount,
                    transaction_type=trans_type,
                    category=category,
                    raw_data=dict(row),
                )

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Discover row: {e}, row: {row}")
                continue

        return transactions
