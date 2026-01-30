"""CSV parser for Fidelity investment holdings."""
import csv
import io
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.schemas.investments import (
    AccountTaxType,
    FidelityHoldingCSVRow,
    InvestmentAccountCreate,
    InvestmentHoldingCreate,
    SourceType,
)
from app.services.yahoo_finance_enrichment import YahooFinanceEnrichmentService


class FidelityCSVParser:
    """Parser for Fidelity investment account CSV files."""
    
    @staticmethod
    async def parse_csv(
        csv_content: str | bytes,
        account_tax_type: AccountTaxType = AccountTaxType.TAXABLE,
    ) -> dict[str, Any]:
        """
        Parse Fidelity CSV and return account + holdings data.
        
        Args:
            csv_content: CSV file content as string or bytes
            account_tax_type: Tax type for the account (must be specified by user)
            
        Returns:
            Dict with account_data and holdings
        """
        # Handle bytes
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode('utf-8')
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        if not rows:
            raise ValueError("CSV file is empty")
        
        # Extract account info from first row
        first_row = rows[0]
        account_number = first_row.get("Account Number", "").strip()
        account_name = first_row.get("Account Name", "").strip() or f"Account {account_number}"
        
        # Detect account type from holdings
        account_type = FidelityCSVParser._detect_account_type(rows)
        
        # Parse each holding
        holdings_data = []
        for row_data in rows:
            try:
                # Validate row using Pydantic
                row = FidelityHoldingCSVRow(**row_data)
                
                # Get market value (try both field names)
                market_value = row.market_value if row.market_value is not None else row.current_value
                
                # Calculate cost basis if not directly provided
                cost_basis = row.cost_basis_total
                if cost_basis is None and row.cost_basis_gain_loss is not None and market_value is not None:
                    # cost_basis = market_value - gain_loss
                    cost_basis = market_value - row.cost_basis_gain_loss
                
                # Calculate average cost basis if not provided
                average_cost_basis = row.average_cost_basis
                if average_cost_basis is None and cost_basis is not None and row.quantity and row.quantity > 0:
                    average_cost_basis = cost_basis / row.quantity
                
                # Extract basic holding data
                holding_data = {
                    "symbol": row.symbol.strip(),
                    "description": row.description.strip(),
                    "quantity": row.quantity,
                    "cost_basis": cost_basis,
                    "average_cost_basis": average_cost_basis,
                }
                holdings_data.append(holding_data)
                
            except Exception as e:
                # Skip invalid rows but continue parsing
                print(f"Warning: Skipped row due to error: {e}")
                continue
        
        if not holdings_data:
            raise ValueError("No valid holdings found in CSV")
        
        return {
            "account_data": {
                "account_number": account_number,
                "account_name": account_name,
                "account_type": account_type,
                "account_tax_type": account_tax_type,
                "institution": "Fidelity",
            },
            "holdings": holdings_data,
        }
    
    @staticmethod
    def _detect_account_type(rows: list[dict[str, Any]]) -> str:
        """Detect account type based on holdings."""
        # Look for common patterns
        has_mutual_funds = any("fund" in row.get("Type", "").lower() for row in rows)
        has_stocks = any("stock" in row.get("Type", "").lower() for row in rows)
        
        if has_mutual_funds and not has_stocks:
            return "401k"  # Likely retirement account
        return "brokerage"
    
    @staticmethod
    async def parse_and_enrich_csv(
        csv_content: str | bytes,
        account_tax_type: AccountTaxType = AccountTaxType.TAXABLE,
        enrich_with_yahoo: bool = True,
    ) -> dict[str, Any]:
        """
        Parse CSV and optionally enrich with Yahoo Finance data.
        
        Args:
            csv_content: CSV file content
            account_tax_type: Tax type for the account
            enrich_with_yahoo: Whether to enrich with real-time Yahoo Finance data
            
        Returns:
            Dict with account and enriched holdings
        """
        # Parse CSV
        parsed_data = await FidelityCSVParser.parse_csv(csv_content, account_tax_type)
        
        # Enrich if requested
        if enrich_with_yahoo:
            holdings_to_enrich = [
                (
                    h["symbol"],
                    h["quantity"],
                    h["cost_basis"],
                    h.get("average_cost_basis"),
                )
                for h in parsed_data["holdings"]
            ]
            
            enriched_holdings = await YahooFinanceEnrichmentService.batch_enrich_holdings(
                holdings_to_enrich
            )
            
            # Convert to dict format
            parsed_data["enriched_holdings"] = [
                h.model_dump() for h in enriched_holdings
            ]
        
        return parsed_data


class GenericHoldingsParser:
    """Parser for generic holdings CSV (Symbol, Quantity, Cost Basis, Average Cost)."""
    
    @staticmethod
    def _fuzzy_match_column(columns: list[str], possible_names: list[str]) -> str | None:
        """
        Find a column name using fuzzy matching.
        
        Tries in order:
        1. Exact match (case-insensitive)
        2. Substring match (case-insensitive)
        
        Args:
            columns: List of actual column names from CSV
            possible_names: List of possible column names to search for
            
        Returns:
            Matched column name or None if not found
        """
        columns_lower = {col.lower(): col for col in columns}
        
        # Try exact match first
        for name in possible_names:
            if name.lower() in columns_lower:
                return columns_lower[name.lower()]
        
        # Try substring match
        for name in possible_names:
            name_lower = name.lower()
            for col_lower, col_original in columns_lower.items():
                if name_lower in col_lower:
                    return col_original
        
        return None
    
    @staticmethod
    async def parse_minimal_csv(
        csv_content: str | bytes,
        account_id: UUID,
    ) -> list[InvestmentHoldingCreate]:
        """
        Parse minimal CSV with just Symbol, Quantity, Cost Basis, Average Cost.
        Uses fuzzy column matching to handle different CSV formats.
        
        Args:
            csv_content: CSV with columns for symbol, quantity, cost basis, etc.
            account_id: UUID of the account these holdings belong to
            
        Returns:
            List of InvestmentHoldingCreate objects ready to be enriched
        """
        # Handle bytes
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode('utf-8')
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        if not rows:
            raise ValueError("CSV file is empty")
        
        # Get column names and find matches
        columns = list(rows[0].keys())
        
        # Define possible column names for each field (in order of preference)
        symbol_col = GenericHoldingsParser._fuzzy_match_column(
            columns, ["Symbol", "Ticker", "Stock Symbol"]
        )
        quantity_col = GenericHoldingsParser._fuzzy_match_column(
            columns, ["Quantity", "Shares", "Qty", "Units"]
        )
        value_col = GenericHoldingsParser._fuzzy_match_column(
            columns, ["Current Value", "Market Value", "Value", "Total Value"]
        )
        cost_basis_col = GenericHoldingsParser._fuzzy_match_column(
            columns, ["Cost Basis Total", "Cost Basis", "Total Cost", "Original Cost"]
        )
        gain_loss_col = GenericHoldingsParser._fuzzy_match_column(
            columns, ["Cost Basis Gain/Loss", "Gain/Loss", "Total Gain/Loss Dollar", "Total Gain/Loss"]
        )
        avg_cost_col = GenericHoldingsParser._fuzzy_match_column(
            columns, ["Average Cost Basis", "Average Cost", "Avg Cost", "Cost Per Share"]
        )
        
        # Require symbol and quantity at minimum
        if not symbol_col:
            raise ValueError("Could not find Symbol column in CSV")
        if not quantity_col:
            raise ValueError("Could not find Quantity column in CSV")
        
        holdings = []
        for row in rows:
            try:
                symbol = row[symbol_col].strip().upper()
                if not symbol:
                    continue
                    
                quantity = Decimal(row[quantity_col] or 0)
                if quantity <= 0:
                    continue
                
                # Get market value if available
                market_value = None
                if value_col and row.get(value_col):
                    market_value = Decimal(row[value_col])
                
                # Calculate cost basis
                cost_basis = None
                if cost_basis_col and row.get(cost_basis_col):
                    cost_basis = Decimal(row[cost_basis_col])
                elif gain_loss_col and value_col and row.get(gain_loss_col) and row.get(value_col):
                    # Calculate: cost_basis = market_value - gain_loss
                    market_value = Decimal(row[value_col])
                    gain_loss = Decimal(row[gain_loss_col])
                    cost_basis = market_value - gain_loss
                
                # Get average cost basis
                average_cost = None
                if avg_cost_col and row.get(avg_cost_col):
                    average_cost = Decimal(row[avg_cost_col])
                elif cost_basis and quantity > 0:
                    average_cost = cost_basis / quantity
                
                holding = InvestmentHoldingCreate(
                    account_id=account_id,
                    symbol=symbol,
                    quantity=quantity,
                    cost_basis=cost_basis if cost_basis and cost_basis > 0 else None,
                    average_cost_basis=average_cost if average_cost and average_cost > 0 else None,
                )
                holdings.append(holding)
                
            except (ValueError, Decimal.InvalidOperation) as e:
                print(f"Warning: Skipped row due to error: {e}")
                continue
        
        if not holdings:
            raise ValueError("No valid holdings found in CSV")
        
        return holdings
