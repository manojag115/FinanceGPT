"""
Fidelity Investments CSV parser.

Fidelity provides CSV exports for:
- Portfolio positions (holdings)
- Transaction history
- Account balances
"""

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.parsers.base_financial_parser import (
    AccountType,
    BaseFinancialParser,
    InvestmentHolding,
    InvestmentTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)


class FidelityParser(BaseFinancialParser):
    """Parser for Fidelity investment statements."""

    def __init__(self):
        """Initialize Fidelity parser."""
        super().__init__("Fidelity")

    async def parse_file(
        self, file_content: bytes, filename: str
    ) -> dict[str, Any]:
        """
        Parse Fidelity CSV file.

        Fidelity CSV formats:
        
        Positions/Holdings:
        Account Number,Account Name,Symbol,Description,Quantity,Last Price,Current Value,
        Cost Basis Total,Gain/Loss Dollar,Gain/Loss Percent,...
        
        Transactions:
        Run Date,Action,Symbol,Security Description,Security Type,Quantity,Price,
        Commission,Fees,Accrued Interest,Amount,Settlement Date
        
        OR:
        Date,Transaction Description,Amount,Balance
        
        Args:
            file_content: CSV file bytes
            filename: Original filename

        Returns:
            Parsed holdings, transactions, and metadata
        """
        try:
            # Decode CSV
            text_content = file_content.decode("utf-8-sig")  # Handle BOM
            csv_reader = csv.DictReader(io.StringIO(text_content))

            fieldnames = csv_reader.fieldnames
            if not fieldnames:
                msg = "Empty CSV file"
                raise ValueError(msg)

            # Detect format
            is_positions = "Symbol" in fieldnames and "Quantity" in fieldnames
            is_transactions = (
                "Action" in fieldnames or "Transaction Description" in fieldnames
            )

            holdings = []
            transactions = []
            balances = []

            if is_positions:
                holdings = await self._parse_positions(csv_reader)
            elif is_transactions:
                transactions = await self._parse_transactions(csv_reader)
            else:
                msg = f"Unknown Fidelity CSV format. Headers: {fieldnames}"
                raise ValueError(msg)

            return {
                "transactions": transactions,
                "holdings": holdings,
                "balances": balances,
                "metadata": {
                    "institution": self.institution_name,
                    "format": "positions" if is_positions else "transactions",
                    "document_subtype": "investment_holdings" if is_positions else "investment_transactions",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "holding_count": len(holdings),
                    "transaction_count": len(transactions),
                },
            }

        except Exception as e:
            logger.error(f"Error parsing Fidelity CSV: {e}", exc_info=True)
            raise

    def _fuzzy_match_column(self, row: dict, possible_names: list[str]) -> str:
        """
        Find a value using fuzzy column name matching.
        
        Tries in order:
        1. Exact match (case-insensitive)
        2. Substring match (case-insensitive)
        
        Args:
            row: CSV row dict
            possible_names: List of possible column names to search for
            
        Returns:
            Value from matched column or empty string if not found
        """
        columns_lower = {k.lower(): k for k in row.keys()}
        
        # Try exact match first
        for name in possible_names:
            if name.lower() in columns_lower:
                return row[columns_lower[name.lower()]]
        
        # Try substring match
        for name in possible_names:
            name_lower = name.lower()
            for col_lower, col_original in columns_lower.items():
                if name_lower in col_lower:
                    return row[col_original]
        
        return ""

    async def _parse_positions(
        self, csv_reader: csv.DictReader
    ) -> list[InvestmentHolding]:
        """
        Parse Fidelity positions/holdings CSV.
        Uses fuzzy column matching to handle different CSV formats.

        Format includes: Symbol, Description, Quantity, Last Price, Current Value,
        Cost Basis Total, Gain/Loss Dollar, Gain/Loss Percent
        """
        holdings = []

        for row in csv_reader:
            try:
                # Skip empty or header rows
                symbol = self._fuzzy_match_column(row, ["Symbol", "Ticker"]).strip()
                if not symbol or symbol == "Symbol":
                    continue

                # Parse basic info
                description = self._fuzzy_match_column(row, ["Description", "Security Description"]).strip()
                quantity_str = self._fuzzy_match_column(row, ["Quantity", "Shares", "Qty"])
                quantity = self._parse_amount(quantity_str or "0")
                
                price_str = self._fuzzy_match_column(row, ["Last Price", "Price", "Current Price"])
                price = self._parse_amount(price_str or "0")
                
                value_str = self._fuzzy_match_column(row, ["Current Value", "Market Value", "Value", "Total Value"])
                value = self._parse_amount(value_str or "0")

                # Parse cost basis and gains
                cost_basis_str = self._fuzzy_match_column(row, ["Cost Basis Total", "Cost Basis", "Total Cost", "Original Cost"])
                cost_basis = (
                    self._parse_amount(cost_basis_str) if cost_basis_str else None
                )

                # Try to get gain/loss
                gain_loss_str = self._fuzzy_match_column(row, [
                    "Total Gain/Loss Dollar", "Gain/Loss Dollar", "Cost Basis Gain/Loss", 
                    "Gain/Loss", "Total Gain/Loss"
                ])
                gain_loss = self._parse_amount(gain_loss_str) if gain_loss_str else None
                
                # Calculate cost basis if not directly provided but we have value and gain/loss
                if cost_basis is None and value and gain_loss is not None:
                    cost_basis = value - gain_loss

                # Try to get gain/loss percent
                gain_loss_pct_str = self._fuzzy_match_column(row, [
                    "Total Gain/Loss Percent", "Gain/Loss Percent", "Gain/Loss %"
                ])
                gain_loss_percent = None
                if gain_loss_pct_str:
                    # Remove % sign and parse
                    pct_cleaned = gain_loss_pct_str.replace("%", "").strip()
                    if pct_cleaned:
                        gain_loss_percent = self._parse_amount(pct_cleaned)

                # Determine account type from Account Name if available
                account_name = self._fuzzy_match_column(row, ["Account Name", "Account"]).upper()
                account_type = self._determine_account_type(account_name)

                # Determine asset type
                asset_type_str = self._fuzzy_match_column(row, ["Security Type", "Type", "Asset Type"]).lower()
                asset_type = asset_type_str if asset_type_str else None
                if not asset_type:
                    # Guess from symbol
                    if len(symbol) <= 5:
                        asset_type = "stock"
                    else:
                        asset_type = "mutual_fund"

                holding = InvestmentHolding(
                    symbol=symbol,
                    description=description,
                    quantity=quantity,
                    price=price,
                    value=value,
                    cost_basis=cost_basis,
                    gain_loss=gain_loss,
                    gain_loss_percent=gain_loss_percent,
                    account_type=account_type,
                    asset_type=asset_type,
                    raw_data=dict(row),
                )

                holdings.append(holding)

            except Exception as e:
                logger.warning(f"Error parsing Fidelity position row: {e}, row: {row}")
                continue

        return holdings

    async def _parse_transactions(
        self, csv_reader: csv.DictReader
    ) -> list[InvestmentTransaction]:
        """
        Parse Fidelity transaction history CSV.

        Format: Run Date, Action, Symbol, Security Description, Quantity, Price, Amount
        """
        transactions = []

        for row in csv_reader:
            try:
                # Check if it's detailed transaction format or simple format
                if "Action" in row:
                    transaction = await self._parse_detailed_transaction(row)
                else:
                    # Simple transaction format (Date, Description, Amount)
                    transaction = await self._parse_simple_transaction(row)

                if transaction:
                    transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Fidelity transaction row: {e}, row: {row}")
                continue

        return transactions

    async def _parse_detailed_transaction(
        self, row: dict
    ) -> InvestmentTransaction | None:
        """Parse detailed Fidelity transaction with Action, Symbol, etc."""
        # Parse date
        date_str = row.get("Run Date") or row.get("Date", "")
        if not date_str:
            return None
        date = self._parse_date(date_str)

        # Action (BUY, SELL, DIVIDEND, etc.)
        action = row.get("Action", "").upper()
        symbol = row.get("Symbol", "").strip()
        description = row.get("Security Description", "").strip()

        # Quantity and price
        quantity = self._parse_amount(row.get("Quantity", "0"))
        price = self._parse_amount(row.get("Price", "0"))
        amount = self._parse_amount(row.get("Amount", "0"))

        # Fees
        commission = self._parse_amount(row.get("Commission", "0"))
        fees_field = self._parse_amount(row.get("Fees", "0"))
        total_fees = commission + fees_field

        # Map Fidelity action to TransactionType
        trans_type = self._map_fidelity_action(action)

        return InvestmentTransaction(
            date=date,
            symbol=symbol,
            description=description,
            transaction_type=trans_type,
            quantity=quantity,
            price=price,
            amount=amount,
            fees=total_fees,
            raw_data=dict(row),
        )

    async def _parse_simple_transaction(self, row: dict) -> InvestmentTransaction | None:
        """Parse simple Fidelity transaction (Date, Description, Amount)."""
        date_str = row.get("Date", "")
        if not date_str:
            return None
        date = self._parse_date(date_str)

        description = row.get("Transaction Description", "").strip()
        amount = self._parse_amount(row.get("Amount", "0"))

        # Try to extract symbol from description
        symbol = ""
        desc_upper = description.upper()
        # Common patterns: "YOU BOUGHT AAPL" or "DIVIDEND MSFT"
        words = desc_upper.split()
        for word in words:
            if len(word) <= 5 and word.isalpha():
                symbol = word
                break

        # Determine type from description
        trans_type = self._determine_transaction_type(amount, description)

        # Estimate quantity if possible (amount / price, but we don't have price)
        quantity = Decimal("0")
        if "bought" in desc_upper or "sold" in desc_upper:
            quantity = Decimal("1")  # Placeholder

        return InvestmentTransaction(
            date=date,
            symbol=symbol,
            description=description,
            transaction_type=trans_type,
            quantity=quantity,
            price=Decimal("0"),
            amount=amount,
            raw_data=dict(row),
        )

    def _map_fidelity_action(self, action: str) -> TransactionType:
        """Map Fidelity action code to TransactionType."""
        action_map = {
            "BUY": TransactionType.BUY,
            "BOUGHT": TransactionType.BUY,
            "SELL": TransactionType.SELL,
            "SOLD": TransactionType.SELL,
            "DIVIDEND": TransactionType.DIVIDEND,
            "DIV": TransactionType.DIVIDEND,
            "REINVEST": TransactionType.REINVEST,
            "REINVESTMENT": TransactionType.REINVEST,
            "INTEREST": TransactionType.INTEREST,
            "FEE": TransactionType.FEE,
            "SPLIT": TransactionType.SPLIT,
        }

        return action_map.get(action, TransactionType.BUY)

    def _determine_account_type(self, account_name: str) -> AccountType:
        """Determine account type from Fidelity account name."""
        name_upper = account_name.upper()

        if "ROTH" in name_upper:
            return AccountType.ROTH_IRA
        if "IRA" in name_upper and "ROTH" not in name_upper:
            return AccountType.TRADITIONAL_IRA
        if "401" in name_upper or "401K" in name_upper:
            return AccountType.K401
        if "BROKERAGE" in name_upper or "INDIVIDUAL" in name_upper:
            return AccountType.BROKERAGE

        return AccountType.BROKERAGE  # Default
