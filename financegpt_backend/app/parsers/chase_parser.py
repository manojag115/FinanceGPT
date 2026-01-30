"""
Chase Bank and Chase Credit Card CSV parser.

Chase provides different CSV formats for:
- Checking/Savings accounts
- Credit cards
"""

import csv
import io
import logging
from datetime import datetime
from typing import Any

from app.parsers.base_financial_parser import (
    AccountBalance,
    AccountType,
    BankTransaction,
    BaseFinancialParser,
    TransactionType,
)

logger = logging.getLogger(__name__)


class ChaseParser(BaseFinancialParser):
    """Parser for Chase bank statements (checking/savings and credit cards)."""

    def __init__(self):
        """Initialize Chase parser."""
        super().__init__("Chase")

    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Parse Chase CSV file.

        Chase CSV formats:
        
        Checking/Savings:
        Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
        
        Credit Card:
        Transaction Date,Post Date,Description,Category,Type,Amount,Memo
        
        OR newer format:
        Details,Posting Date,Description,Amount,Balance,Check or Slip #
        
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

            # Detect format based on headers
            fieldnames = csv_reader.fieldnames
            if not fieldnames:
                msg = "Empty CSV file"
                raise ValueError(msg)

            is_credit_card = "Transaction Date" in fieldnames
            is_checking = "Posting Date" in fieldnames and "Balance" in fieldnames

            transactions = []
            balances = []

            if is_credit_card:
                transactions = await self._parse_credit_card(csv_reader)
            elif is_checking:
                transactions, balances = await self._parse_checking(csv_reader)
            else:
                msg = f"Unknown Chase CSV format. Headers: {fieldnames}"
                raise ValueError(msg)

            return {
                "transactions": transactions,
                "holdings": [],
                "balances": balances,
                "metadata": {
                    "institution": self.institution_name,
                    "format": "credit_card" if is_credit_card else "checking",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "transaction_count": len(transactions),
                },
            }

        except Exception as e:
            logger.error(f"Error parsing Chase CSV: {e}", exc_info=True)
            raise

    async def _parse_checking(
        self, csv_reader: csv.DictReader
    ) -> tuple[list[BankTransaction], list[AccountBalance]]:
        """
        Parse Chase checking/savings CSV.

        Format: Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
        OR: Details,Posting Date,Description,Amount,Balance,Check or Slip #
        """
        transactions = []
        balances = []

        for row in csv_reader:
            try:
                # Skip header rows or empty rows
                if not row.get("Description") or row.get("Description") == "Description":
                    continue

                # Parse date
                date_str = row.get("Posting Date", "")
                if not date_str:
                    continue
                date = self._parse_date(date_str)

                # Parse amount
                amount_str = row.get("Amount", "0")
                amount = self._parse_amount(amount_str)

                # Description
                description = row.get("Description", "").strip()

                # Type from Chase (DEBIT, CREDIT, CHECK, ACH_DEBIT, etc.)
                chase_type = row.get("Type", "").upper()

                # Determine transaction type
                if chase_type in ["DEBIT", "ACH_DEBIT", "ATM", "DSLIP"]:
                    trans_type = TransactionType.DEBIT
                elif chase_type in ["CREDIT", "ACH_CREDIT", "DEP"]:
                    trans_type = TransactionType.CREDIT
                elif chase_type == "CHECK":
                    trans_type = TransactionType.DEBIT
                else:
                    trans_type = self._determine_transaction_type(amount, description)

                # Balance
                balance_str = row.get("Balance", "")
                balance = self._parse_amount(balance_str) if balance_str else None

                # Check number
                check_number = row.get("Check or Slip #", "").strip() or None

                # Details/memo
                details = row.get("Details", "").strip() or None

                transaction = BankTransaction(
                    date=date,
                    description=description,
                    amount=amount,
                    transaction_type=trans_type,
                    balance=balance,
                    check_number=check_number,
                    memo=details,
                    raw_data=dict(row),
                )

                transactions.append(transaction)

                # Add balance snapshot if available
                if balance is not None:
                    account_balance = AccountBalance(
                        date=date,
                        account_type=AccountType.CHECKING,
                        account_name="Chase Checking",
                        balance=balance,
                        institution=self.institution_name,
                        raw_data=dict(row),
                    )
                    balances.append(account_balance)

            except Exception as e:
                logger.warning(f"Error parsing Chase checking row: {e}, row: {row}")
                continue

        return transactions, balances

    async def _parse_credit_card(
        self, csv_reader: csv.DictReader
    ) -> list[BankTransaction]:
        """
        Parse Chase credit card CSV.

        Format: Transaction Date,Post Date,Description,Category,Type,Amount,Memo
        """
        transactions = []

        for row in csv_reader:
            try:
                # Skip header or empty rows
                if not row.get("Description") or row.get("Description") == "Description":
                    continue

                # Parse date (use Transaction Date, fall back to Post Date)
                date_str = row.get("Transaction Date") or row.get("Post Date", "")
                if not date_str:
                    continue
                date = self._parse_date(date_str)

                # Parse amount (negative for charges, positive for payments/credits)
                amount_str = row.get("Amount", "0")
                amount = self._parse_amount(amount_str)

                # Description
                description = row.get("Description", "").strip()

                # Category (Chase provides this)
                category = row.get("Category", "").strip() or None

                # Type from Chase (Sale, Return, Payment, etc.)
                chase_type = row.get("Type", "").upper()

                # Determine transaction type
                if chase_type == "PAYMENT":
                    trans_type = TransactionType.PAYMENT
                elif chase_type in ["SALE", "PURCHASE"]:
                    trans_type = TransactionType.PURCHASE
                elif chase_type == "RETURN":
                    trans_type = TransactionType.CREDIT
                elif chase_type == "FEE":
                    trans_type = TransactionType.FEE
                else:
                    # For credit cards, negative amounts are charges
                    trans_type = (
                        TransactionType.PURCHASE
                        if amount < 0
                        else TransactionType.PAYMENT
                    )

                # Memo
                memo = row.get("Memo", "").strip() or None

                transaction = BankTransaction(
                    date=date,
                    description=description,
                    amount=amount,
                    transaction_type=trans_type,
                    category=category,
                    memo=memo,
                    raw_data=dict(row),
                )

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Chase credit card row: {e}, row: {row}")
                continue

        return transactions


class ChaseCreditParser(ChaseParser):
    """Specialized parser for Chase Credit Cards."""

    def __init__(self):
        """Initialize Chase Credit parser."""
        super().__init__()
        self.institution_name = "Chase Credit Card"


class ChaseBankParser(ChaseParser):
    """Specialized parser for Chase Bank accounts."""

    def __init__(self):
        """Initialize Chase Bank parser."""
        super().__init__()
        self.institution_name = "Chase Bank"
