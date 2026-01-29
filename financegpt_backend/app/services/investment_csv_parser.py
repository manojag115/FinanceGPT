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
                
                # Extract basic holding data
                holding_data = {
                    "symbol": row.symbol.strip(),
                    "description": row.description.strip(),
                    "quantity": row.quantity,
                    "cost_basis": row.cost_basis_total,
                    "average_cost_basis": row.average_cost_basis,
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
    async def parse_minimal_csv(
        csv_content: str | bytes,
        account_id: UUID,
    ) -> list[InvestmentHoldingCreate]:
        """
        Parse minimal CSV with just Symbol, Quantity, Cost Basis, Average Cost.
        
        Args:
            csv_content: CSV with columns: Symbol, Quantity, Cost Basis Total, Average Cost Basis
            account_id: UUID of the account these holdings belong to
            
        Returns:
            List of InvestmentHoldingCreate objects ready to be enriched
        """
        # Handle bytes
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode('utf-8')
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        
        holdings = []
        for row in reader:
            try:
                symbol = row["Symbol"].strip().upper()
                quantity = Decimal(row["Quantity"])
                cost_basis = Decimal(row.get("Cost Basis Total", row.get("Cost Basis", 0)))
                average_cost = Decimal(row.get("Average Cost Basis", row.get("Average Cost", 0)))
                
                holding = InvestmentHoldingCreate(
                    account_id=account_id,
                    symbol=symbol,
                    quantity=quantity,
                    cost_basis=cost_basis,
                    average_cost_basis=average_cost if average_cost > 0 else None,
                )
                holdings.append(holding)
                
            except (KeyError, ValueError, Decimal.InvalidOperation) as e:
                print(f"Warning: Skipped row due to error: {e}")
                continue
        
        return holdings
