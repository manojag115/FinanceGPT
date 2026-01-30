"""
Base classes for financial statement parsing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class TransactionType(str, Enum):
    """Type of financial transaction."""

    DEBIT = "debit"  # Money out
    CREDIT = "credit"  # Money in
    PAYMENT = "payment"  # Payment made
    PURCHASE = "purchase"  # Purchase
    TRANSFER = "transfer"  # Transfer between accounts
    FEE = "fee"  # Bank/service fee
    INTEREST = "interest"  # Interest earned/paid
    DIVIDEND = "dividend"  # Dividend payment
    WITHDRAWAL = "withdrawal"  # ATM/cash withdrawal
    DEPOSIT = "deposit"  # Deposit
    # Investment specific
    BUY = "buy"  # Buy security
    SELL = "sell"  # Sell security
    REINVEST = "reinvest"  # Reinvest dividends
    SPLIT = "split"  # Stock split
    MERGER = "merger"  # Merger/acquisition


class AccountType(str, Enum):
    """Type of financial account."""

    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    BROKERAGE = "brokerage"
    IRA = "ira"
    ROTH_IRA = "roth_ira"
    TRADITIONAL_IRA = "traditional_ira"
    K401 = "401k"
    MORTGAGE = "mortgage"
    LOAN = "loan"
    OTHER = "other"


@dataclass
class BankTransaction:
    """Represents a single bank transaction."""

    date: datetime
    description: str
    amount: Decimal
    transaction_type: TransactionType
    balance: Decimal | None = None
    category: str | None = None
    merchant: str | None = None
    account_last_4: str | None = None
    check_number: str | None = None
    memo: str | None = None
    raw_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "date": self.date.isoformat(),
            "description": self.description,
            "amount": str(self.amount),
            "transaction_type": self.transaction_type.value,
            "balance": str(self.balance) if self.balance else None,
            "category": self.category,
            "merchant": self.merchant,
            "account_last_4": self.account_last_4,
            "check_number": self.check_number,
            "memo": self.memo,
            "raw_data": self.raw_data,
        }


@dataclass
class InvestmentHolding:
    """Represents an investment holding/position."""

    symbol: str
    description: str
    quantity: Decimal
    price: Decimal
    value: Decimal
    cost_basis: Decimal | None = None
    gain_loss: Decimal | None = None
    gain_loss_percent: Decimal | None = None
    account_type: AccountType | None = None
    asset_type: str | None = None  # stock, bond, etf, mutual_fund, etc.
    raw_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "symbol": self.symbol,
            "description": self.description,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "value": str(self.value),
            "cost_basis": str(self.cost_basis) if self.cost_basis else None,
            "gain_loss": str(self.gain_loss) if self.gain_loss else None,
            "gain_loss_percent": str(self.gain_loss_percent)
            if self.gain_loss_percent
            else None,
            "account_type": self.account_type.value if self.account_type else None,
            "asset_type": self.asset_type,
            "raw_data": self.raw_data,
        }


@dataclass
class InvestmentTransaction:
    """Represents an investment transaction (buy/sell)."""

    date: datetime
    symbol: str
    description: str
    transaction_type: TransactionType
    quantity: Decimal
    price: Decimal
    amount: Decimal
    fees: Decimal = Decimal("0")
    account_type: AccountType | None = None
    raw_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "date": self.date.isoformat(),
            "symbol": self.symbol,
            "description": self.description,
            "transaction_type": self.transaction_type.value,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "amount": str(self.amount),
            "fees": str(self.fees),
            "account_type": self.account_type.value if self.account_type else None,
            "raw_data": self.raw_data,
        }


@dataclass
class AccountBalance:
    """Represents an account balance snapshot."""

    date: datetime
    account_type: AccountType
    account_name: str
    balance: Decimal
    available_balance: Decimal | None = None
    account_last_4: str | None = None
    institution: str | None = None
    raw_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "date": self.date.isoformat(),
            "account_type": self.account_type.value,
            "account_name": self.account_name,
            "balance": str(self.balance),
            "available_balance": str(self.available_balance)
            if self.available_balance
            else None,
            "account_last_4": self.account_last_4,
            "institution": self.institution,
            "raw_data": self.raw_data,
        }


class BaseFinancialParser(ABC):
    """Base class for financial statement parsers."""

    def __init__(self, institution_name: str):
        """
        Initialize parser.

        Args:
            institution_name: Name of the financial institution (e.g., "Chase", "Fidelity")
        """
        self.institution_name = institution_name

    @abstractmethod
    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Parse a financial statement file.

        Args:
            file_content: Raw file bytes
            filename: Original filename (used to detect format)
            session: Optional database session for LLM access
            user_id: Optional user ID for user-specific LLM config
            search_space_id: Optional search space ID for LLM config

        Returns:
            Dictionary containing:
                - transactions: List[BankTransaction] or List[InvestmentTransaction]
                - holdings: List[InvestmentHolding] (for investment accounts)
                - balances: List[AccountBalance]
                - metadata: dict with parsing info
        """
        pass

    def _determine_transaction_type(
        self, amount: Decimal, description: str
    ) -> TransactionType:
        """
        Determine transaction type from amount and description.

        Args:
            amount: Transaction amount (negative for debits)
            description: Transaction description

        Returns:
            TransactionType
        """
        desc_lower = description.lower()

        # Check description keywords first
        if any(
            word in desc_lower
            for word in ["dividend", "div", "reinvest div", "dividend reinvestment"]
        ):
            return TransactionType.DIVIDEND
        if any(word in desc_lower for word in ["buy", "purchase", "bought"]):
            return TransactionType.BUY
        if any(word in desc_lower for word in ["sell", "sold"]):
            return TransactionType.SELL
        if any(word in desc_lower for word in ["fee", "charge", "service charge"]):
            return TransactionType.FEE
        if any(word in desc_lower for word in ["interest", "int earned"]):
            return TransactionType.INTEREST
        if any(
            word in desc_lower for word in ["withdrawal", "withdraw", "atm", "cash"]
        ):
            return TransactionType.WITHDRAWAL
        if any(word in desc_lower for word in ["deposit", "direct deposit"]):
            return TransactionType.DEPOSIT
        if any(word in desc_lower for word in ["transfer", "xfer"]):
            return TransactionType.TRANSFER
        if any(word in desc_lower for word in ["payment", "autopay"]):
            return TransactionType.PAYMENT

        # Fall back to amount-based determination
        if amount < 0:
            return TransactionType.DEBIT
        return TransactionType.CREDIT

    def _parse_amount(self, amount_str: str) -> Decimal:
        """
        Parse amount string to Decimal, handling various formats.

        Args:
            amount_str: Amount as string (e.g., "$1,234.56", "-100.00", "(50.00)")

        Returns:
            Decimal value
        """
        if not amount_str or amount_str.strip() == "":
            return Decimal("0")

        # Remove currency symbols, spaces, and commas
        cleaned = amount_str.strip().replace("$", "").replace(",", "").replace(" ", "")

        # Handle parentheses as negative (accounting format)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    def _parse_date(self, date_str: str, formats: list[str] | None = None) -> datetime:
        """
        Parse date string to datetime.

        Args:
            date_str: Date as string
            formats: List of strftime format strings to try

        Returns:
            datetime object
        """
        if formats is None:
            # Common date formats used by financial institutions
            formats = [
                "%m/%d/%Y",  # 01/31/2024
                "%m/%d/%y",  # 01/31/24
                "%Y-%m-%d",  # 2024-01-31
                "%m-%d-%Y",  # 01-31-2024
                "%d/%m/%Y",  # 31/01/2024 (international)
                "%Y/%m/%d",  # 2024/01/31
                "%b %d, %Y",  # Jan 31, 2024
                "%B %d, %Y",  # January 31, 2024
            ]

        date_str = date_str.strip()

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        msg = f"Could not parse date: {date_str}"
        raise ValueError(msg)
