"""
OFX/QFX (Open Financial Exchange) file parser.

OFX is a universal format supported by most banks and financial institutions.
This provides broad compatibility without needing institution-specific parsers.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.parsers.base_financial_parser import (
    AccountBalance,
    AccountType,
    BankTransaction,
    BaseFinancialParser,
    InvestmentHolding,
    InvestmentTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)


class OFXParser(BaseFinancialParser):
    """Parser for OFX/QFX files (universal banking format)."""

    def __init__(self):
        """Initialize OFX parser."""
        super().__init__("OFX")

    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Parse OFX/QFX file.

        OFX is an XML-based format. We'll use the ofxparse library.
        
        Args:
            file_content: OFX file bytes
            filename: Original filename

        Returns:
            Parsed transactions, holdings, and metadata
        """
        try:
            # Try to import ofxparse
            try:
                from ofxparse import OfxParser
            except ImportError:
                msg = "ofxparse library not installed. Install with: pip install ofxparse"
                raise ImportError(msg) from None

            # Parse OFX
            ofx = OfxParser.parse(file_content)

            transactions = []
            holdings = []
            balances = []

            # Parse bank accounts
            if hasattr(ofx, "accounts") and ofx.accounts:
                for account in ofx.accounts:
                    account_trans, account_bal = await self._parse_bank_account(account)
                    transactions.extend(account_trans)
                    if account_bal:
                        balances.append(account_bal)

            # Parse investment accounts
            investments = getattr(ofx, "investments", [])
            if investments:
                for investment in investments:
                    inv_trans, inv_holdings = await self._parse_investment_account(
                        investment
                    )
                    transactions.extend(inv_trans)
                    holdings.extend(inv_holdings)

            # Parse credit card accounts
            credit_cards = getattr(ofx, "credit_cards", [])
            if credit_cards:
                for cc_account in credit_cards:
                    cc_trans, cc_bal = await self._parse_bank_account(
                        cc_account, is_credit_card=True
                    )
                    transactions.extend(cc_trans)
                    if cc_bal:
                        balances.append(cc_bal)

            return {
                "transactions": transactions,
                "holdings": holdings,
                "balances": balances,
                "metadata": {
                    "institution": getattr(ofx, "institution", "Unknown"),
                    "format": "ofx",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "transaction_count": len(transactions),
                    "holding_count": len(holdings),
                },
            }

        except Exception as e:
            logger.error("Error parsing OFX file: %s", e, exc_info=True)
            raise

    async def _parse_bank_account(
        self, account: Any, is_credit_card: bool = False
    ) -> tuple[list[BankTransaction], AccountBalance | None]:
        """Parse OFX bank account."""
        transactions = []
        balance_obj = None

        # Get account info
        account_type = AccountType.CREDIT_CARD if is_credit_card else AccountType.CHECKING
        account_name = getattr(account, "account_id", "Unknown")

        # Parse transactions
        if hasattr(account, "statement") and account.statement:
            stmt = account.statement

            # Get balance
            if hasattr(stmt, "balance"):
                balance_obj = AccountBalance(
                    date=datetime.now(),
                    account_type=account_type,
                    account_name=account_name,
                    balance=Decimal(str(stmt.balance)),
                    available_balance=Decimal(str(stmt.available_balance))
                    if hasattr(stmt, "available_balance")
                    else None,
                    institution=self.institution_name,
                )

            # Parse transactions
            if hasattr(stmt, "transactions"):
                for ofx_trans in stmt.transactions:
                    try:
                        # Parse amount
                        amount = Decimal(str(ofx_trans.amount))

                        # Determine type
                        trans_type_str = getattr(ofx_trans, "type", "").upper()
                        trans_type = self._map_ofx_type(trans_type_str, amount)

                        transaction = BankTransaction(
                            date=ofx_trans.date,
                            description=getattr(ofx_trans, "memo", "")
                            or getattr(ofx_trans, "payee", ""),
                            amount=amount,
                            transaction_type=trans_type,
                            check_number=getattr(ofx_trans, "checknum", None),
                            memo=getattr(ofx_trans, "memo", None),
                            raw_data={
                                "id": getattr(ofx_trans, "id", ""),
                                "type": trans_type_str,
                            },
                        )
                        transactions.append(transaction)
                    except Exception as e:
                        logger.warning("Error parsing OFX transaction: %s", e)
                        continue

        return transactions, balance_obj

    async def _parse_investment_account(
        self, investment: Any
    ) -> tuple[list[InvestmentTransaction], list[InvestmentHolding]]:
        """Parse OFX investment account."""
        transactions = []
        holdings = []

        # Parse positions/holdings
        if hasattr(investment, "positions"):
            for position in investment.positions:
                try:
                    holding = InvestmentHolding(
                        symbol=getattr(position, "security", ""),
                        description=getattr(position, "memo", ""),
                        quantity=Decimal(str(getattr(position, "units", 0))),
                        price=Decimal(str(getattr(position, "unit_price", 0))),
                        value=Decimal(str(getattr(position, "market_value", 0))),
                        raw_data={"security_id": getattr(position, "security_id", "")},
                    )
                    holdings.append(holding)
                except Exception as e:
                    logger.warning("Error parsing OFX position: %s", e)
                    continue

        # Parse investment transactions
        if hasattr(investment, "transactions"):
            for ofx_trans in investment.transactions:
                try:
                    # Map OFX investment transaction type
                    trans_type_str = getattr(ofx_trans, "type", "").upper()
                    trans_type = self._map_investment_type(trans_type_str)

                    transaction = InvestmentTransaction(
                        date=getattr(ofx_trans, "trade_date", datetime.now()),
                        symbol=getattr(ofx_trans, "security", ""),
                        description=getattr(ofx_trans, "memo", ""),
                        transaction_type=trans_type,
                        quantity=Decimal(str(getattr(ofx_trans, "units", 0))),
                        price=Decimal(str(getattr(ofx_trans, "unit_price", 0))),
                        amount=Decimal(str(getattr(ofx_trans, "total", 0))),
                        fees=Decimal(str(getattr(ofx_trans, "commission", 0))),
                        raw_data={"type": trans_type_str},
                    )
                    transactions.append(transaction)
                except Exception as e:
                    logger.warning("Error parsing OFX investment transaction: %s", e)
                    continue

        return transactions, holdings

    def _map_ofx_type(self, ofx_type: str, amount: Decimal) -> TransactionType:
        """Map OFX transaction type to our TransactionType."""
        type_map = {
            "DEBIT": TransactionType.DEBIT,
            "CREDIT": TransactionType.CREDIT,
            "INT": TransactionType.INTEREST,
            "DIV": TransactionType.DIVIDEND,
            "FEE": TransactionType.FEE,
            "SRVCHG": TransactionType.FEE,
            "DEP": TransactionType.DEPOSIT,
            "ATM": TransactionType.WITHDRAWAL,
            "POS": TransactionType.PURCHASE,
            "CHECK": TransactionType.DEBIT,
            "PAYMENT": TransactionType.PAYMENT,
            "CASH": TransactionType.WITHDRAWAL,
            "DIRECTDEP": TransactionType.DEPOSIT,
            "DIRECTDEBIT": TransactionType.DEBIT,
            "REPEATPMT": TransactionType.PAYMENT,
            "XFER": TransactionType.TRANSFER,
        }

        trans_type = type_map.get(ofx_type)
        if trans_type:
            return trans_type

        # Fall back to amount-based determination
        return TransactionType.DEBIT if amount < 0 else TransactionType.CREDIT

    def _map_investment_type(self, ofx_type: str) -> TransactionType:
        """Map OFX investment transaction type."""
        type_map = {
            "BUYSTOCK": TransactionType.BUY,
            "SELLSTOCK": TransactionType.SELL,
            "INCOME": TransactionType.DIVIDEND,
            "REINVEST": TransactionType.REINVEST,
            "SPLIT": TransactionType.SPLIT,
        }

        return type_map.get(ofx_type, TransactionType.BUY)
