"""
LLM-based CSV parser for unknown formats.
Uses LLM to intelligently extract holdings from any CSV structure.
"""

import csv
import io
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.parsers.base_financial_parser import (
    BaseFinancialParser,
    InvestmentHolding,
)

logger = logging.getLogger(__name__)


class LLMCSVParser(BaseFinancialParser):
    """Parser that uses LLM to understand and extract data from any CSV format."""

    def __init__(self):
        """Initialize LLM CSV parser."""
        super().__init__("LLM CSV Parser")

    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Parse any CSV using LLM to understand the structure.

        Args:
            file_content: CSV file bytes
            filename: Original filename
            session: Optional database session for LLM access
            user_id: Optional user ID for user-specific LLM config
            search_space_id: Optional search space ID for LLM config

        Returns:
            Parsed holdings and metadata
        """
        try:
            # Decode CSV
            text_content = file_content.decode("utf-8-sig")
            csv_reader = csv.DictReader(io.StringIO(text_content))
            
            # Get headers and first few rows for LLM analysis
            rows = list(csv_reader)
            if not rows:
                raise ValueError("CSV file is empty")
            
            headers = list(rows[0].keys())

            # Use LLM to extract holdings
            holdings = await self._extract_holdings_with_llm(
                headers, rows, filename, session, user_id, search_space_id
            )

            return {
                "transactions": [],
                "holdings": holdings,
                "balances": [],
                "metadata": {
                    "institution": "Unknown",
                    "format": "llm_extracted",
                    "document_subtype": "investment_holdings",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "holding_count": len(holdings),
                    "transaction_count": 0,
                },
            }

        except Exception as e:
            logger.error("Error in LLM CSV parsing: %s", e, exc_info=True)
            raise

    async def _extract_holdings_with_llm(
        self,
        headers: list[str],
        rows: list[dict],
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> list[InvestmentHolding]:
        """
        Use LLM to intelligently extract holdings from CSV.
        
        Args:
            headers: CSV column headers
            rows: All CSV rows as dicts
            filename: Original filename for context
            session: Optional database session for LLM access
            user_id: Optional user ID for user-specific LLM config
            search_space_id: Optional search space ID for LLM config
            
        Returns:
            List of InvestmentHolding objects
        """
        # Try to get user's configured LLM
        llm = None
        if session and user_id and search_space_id:
            try:
                from app.services.llm_service import get_user_long_context_llm
                
                llm = await get_user_long_context_llm(session, user_id, search_space_id)
                if llm:
                    logger.info("Using user's configured LLM for CSV parsing")
            except Exception as e:
                logger.warning(
                    "Failed to get user LLM config, will use fallback parsing: %s", e
                )
        
        # If no LLM available, use fallback
        if not llm:
            logger.info(
                "No LLM available for CSV parsing, using fallback heuristic approach"
            )
            return await self._fallback_basic_parse(rows)
        
        # Build prompt for LLM - first detect file type
        sample_data = json.dumps(rows[:5], indent=2, default=str)
        
        prompt = f"""You are parsing a financial CSV file. First, determine the file type, then extract the data.

CSV Headers: {headers}

Sample rows:
{sample_data}

STEP 1: Determine file type
- If headers contain "Transaction Type", "Bought", "Sold", or similar transaction keywords → This is a TRANSACTION HISTORY file
- If headers contain "Current Value", "Market Value", "Shares" without transaction types → This is a HOLDINGS/POSITIONS file

STEP 2: Extract appropriate data based on file type

If TRANSACTION HISTORY file, this parser cannot handle it properly. Return an empty array [].

If HOLDINGS/POSITIONS file, extract for EACH row:
- symbol: Stock/fund ticker symbol (required)
- quantity: Number of shares (required, must be > 0)
- cost_basis: Total cost paid for position (optional)
- market_value: Current market value (optional)
- price: Current price per share (optional)

Calculation rules for HOLDINGS files:
1. If cost_basis not directly available but "Market Value" and "Gain/Loss" exist: cost_basis = market_value - gain_loss
2. If average_cost_basis available with quantity: cost_basis = average_cost_basis * quantity
3. Only include rows with valid symbol and quantity > 0
4. Skip header rows, total rows, or summary rows

Return ONLY a JSON array, no other text.

Example for holdings:
[
  {{"symbol": "AAPL", "quantity": 100, "cost_basis": 15000, "market_value": 18000, "price": 180}},
  {{"symbol": "MSFT", "quantity": 50, "cost_basis": 12000, "market_value": 21000, "price": 420}}
]

Example for transaction history (wrong file type):
[]
"""

        try:
            # Call LLM
            response = await llm.ainvoke(prompt)
            
            # Extract JSON from response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Find JSON array in response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("LLM response doesn't contain JSON array: %s", response_text)
                raise ValueError("LLM failed to return valid JSON")
            
            json_str = response_text[start_idx:end_idx]
            holdings_data = json.loads(json_str)
            
            # Check if LLM returned empty array (indicates transaction file)
            if not holdings_data:
                logger.warning(
                    "LLM detected this is a transaction history file, not a holdings file. "
                    "Transaction history files are not yet supported by this parser. "
                    "Filename: %s", filename
                )
            
            # Convert to InvestmentHolding objects
            holdings = []
            for data in holdings_data:
                try:
                    symbol = data.get("symbol", "").strip().upper()
                    quantity = Decimal(str(data.get("quantity", 0)))
                    
                    if not symbol or quantity <= 0:
                        continue
                    
                    # Extract optional fields
                    cost_basis = None
                    if "cost_basis" in data and data["cost_basis"] is not None:
                        cost_basis = Decimal(str(data["cost_basis"]))
                    
                    market_value = None
                    if "market_value" in data and data["market_value"] is not None:
                        market_value = Decimal(str(data["market_value"]))
                    
                    price = None
                    if "price" in data and data["price"] is not None:
                        price = Decimal(str(data["price"]))
                    
                    holding = InvestmentHolding(
                        symbol=symbol,
                        description=data.get("description", ""),
                        quantity=quantity,
                        price=price,
                        value=market_value,
                        cost_basis=cost_basis,
                        gain_loss=None,
                        gain_loss_percent=None,
                        account_type=None,
                        asset_type="stock" if len(symbol) <= 5 else "mutual_fund",
                        raw_data=data,
                    )
                    
                    holdings.append(holding)
                    
                except (ValueError, TypeError) as e:
                    logger.warning("Skipping invalid holding data: %s, error: %s", data, e)
                    continue
            
            logger.info("LLM extracted %d holdings from %s", len(holdings), filename)
            return holdings
            
        except Exception as e:
            logger.error("LLM extraction failed: %s", e, exc_info=True)
            # Fallback: try basic parsing
            return await self._fallback_basic_parse(rows)

    async def _fallback_basic_parse(self, rows: list[dict]) -> list[InvestmentHolding]:
        """
        Fallback parser if LLM fails - uses simple heuristics.
        
        Args:
            rows: CSV rows as dicts
            
        Returns:
            List of InvestmentHolding objects
        """
        logger.info("Using fallback basic parsing")
        holdings = []
        
        for row in rows:
            # Try to find symbol column (common names)
            symbol = None
            for key in ["Symbol", "Ticker", "Stock Symbol", "Security"]:
                value = row.get(key)
                if value:
                    symbol = value.strip().upper()
                    break
            
            if not symbol:
                continue
            
            # Try to find quantity
            quantity = None
            for key in ["Quantity", "Shares", "Qty", "Units"]:
                value = row.get(key)
                if value:
                    try:
                        quantity = Decimal(str(value).replace(",", ""))
                        break
                    except (ValueError, TypeError):
                        continue
            
            if not quantity or quantity <= 0:
                continue
            
            # Basic holding with just symbol and quantity
            holding = InvestmentHolding(
                symbol=symbol,
                description="",
                quantity=quantity,
                price=None,
                value=None,
                cost_basis=None,
                gain_loss=None,
                gain_loss_percent=None,
                account_type=None,
                asset_type="stock",
                raw_data=dict(row),
            )
            
            holdings.append(holding)
        
        logger.info("Fallback parser extracted %d holdings", len(holdings))
        return holdings
