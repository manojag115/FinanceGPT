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
    BankTransaction,
    InvestmentHolding,
    TransactionType,
)

logger = logging.getLogger(__name__)


class LLMCSVParser(BaseFinancialParser):
    """Parser that uses LLM to understand and extract data from any CSV format.
    
    Privacy-first approach: Sends only sanitized samples to LLM for schema detection,
    then applies schema locally to extract actual data without exposing it to LLM.
    """

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

            # Use LLM to extract data
            holdings, transactions = await self._extract_data_with_llm(
                headers, rows, filename, session, user_id, search_space_id
            )

            return {
                "transactions": transactions,
                "holdings": holdings,
                "balances": [],
                "metadata": {
                    "institution": "Unknown",
                    "format": "llm_extracted",
                    "document_subtype": "investment_holdings" if holdings else "bank_transactions",
                    "filename": filename,
                    "parsed_at": datetime.now().isoformat(),
                    "holding_count": len(holdings),
                    "transaction_count": len(transactions),
                },
            }

        except Exception as e:
            logger.error("Error in LLM CSV parsing: %s", e, exc_info=True)
            raise

    async def _extract_data_with_llm(
        self,
        headers: list[str],
        rows: list[dict],
        filename: str,
        session=None,
        user_id: str | None = None,
        search_space_id: int | None = None,
    ) -> tuple[list[InvestmentHolding], list[BankTransaction]]:
        """
        Use LLM to intelligently extract holdings OR transactions from CSV.
        
        Args:
            headers: CSV column headers
            rows: All CSV rows as dicts
            filename: Original filename for context
            session: Optional database session for LLM access
            user_id: Optional user ID for user-specific LLM config
            search_space_id: Optional search space ID for LLM config
            
        Returns:
            Tuple of (holdings list, transactions list)
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
        
        # PRIVACY-FIRST: Only send sanitized samples to LLM for schema detection
        # Real data is extracted locally without exposing it to the LLM
        num_rows = len(rows)
        num_samples = min(3, num_rows)
        
        # Sanitize sample rows - replace real values with type indicators
        sanitized_samples = [
            {col: self._sanitize_value(row[col]) for col in row}
            for row in rows[:num_samples]
        ]
        
        sample_data = json.dumps(sanitized_samples, indent=2, default=str)
        logger.info(f"Sending {num_samples} sanitized samples to LLM for schema detection (protecting {num_rows} rows of real data)")
        
        prompt = f"""You are analyzing a financial CSV file structure. Your job is to determine the file type and create a SCHEMA MAPPING, NOT extract actual data.

PRIVACY NOTE: You are receiving sanitized sample data. Real values are masked with type indicators like [DECIMAL], [TEXT], [DATE:format], [SYMBOL].

CSV Headers: {headers}

Sanitized Sample Rows (real data is protected):
{sample_data}

STEP 1: Determine file type
- If headers contain "Transaction Type", "Bought", "Sold", "Payment", "Purchase", or transaction descriptions → This is a TRANSACTION HISTORY file
- If headers contain "Current Value", "Market Value", "Shares", "Position" without transaction types → This is a HOLDINGS/POSITIONS file

STEP 2: Create a SCHEMA MAPPING (not data extraction)

For TRANSACTION HISTORY files, provide mapping for:
- date: {{"column": "<column_name>", "format": "<detected_date_format>"}}
- description: {{"column": "<column_name>"}}
- amount: {{"column": "<column_name>", "sign_convention": "negative_for_debits|positive_for_debits"}}
- transaction_type: {{"column": "<column_name_if_exists>", "default": "DEBIT"}}
- category: {{"column": "<column_name_if_exists>"}}
- merchant: {{"column": "<column_name_if_exists>"}}

For HOLDINGS/POSITIONS files, provide mapping for:
- symbol: {{"column": "<column_name>"}}
- quantity: {{"column": "<column_name>"}}
- price: {{"column": "<column_name_if_exists>"}}
- market_value: {{"column": "<column_name_if_exists>"}}
- cost_basis: {{"column": "<column_name_if_exists>", "calculation": "<if_needs_calculation>"}}
- gain_loss: {{"column": "<column_name_if_exists>"}}

Return ONLY the schema mapping as JSON:

Example for holdings:
{{"file_type": "holdings", "schema": {{
  "symbol": {{"column": "Symbol"}},
  "quantity": {{"column": "Quantity"}},
  "price": {{"column": "Last Price"}},
  "market_value": {{"column": "Current Value"}},
  "cost_basis": {{"calculation": "market_value - gain_loss", "uses_columns": ["Current Value", "Total Gain/Loss Dollar"]}}
}}}}

Example for transactions:
{{"file_type": "transactions", "schema": {{
  "date": {{"column": "Transaction Date", "format": "MM/DD/YYYY"}},
  "description": {{"column": "Description"}},
  "amount": {{"column": "Amount", "sign_convention": "negative_for_debits"}},
  "transaction_type": {{"default": "DEBIT"}}
}}}}"""

        try:
            # Call LLM
            response = await llm.ainvoke(prompt)
            
            # Extract JSON from response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Find JSON object in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("LLM response doesn't contain JSON object: %s", response_text)
                raise ValueError("LLM failed to return valid JSON")
            
            json_str = response_text[start_idx:end_idx]
            parsed_response = json.loads(json_str)
            
            file_type = parsed_response.get("file_type", "unknown")
            schema = parsed_response.get("schema", {})
            
            logger.info(f"LLM detected file type: {file_type}, applying schema to {num_rows} rows locally (privacy-preserving)")
            
            # Apply schema locally to ALL rows without sending to LLM
            if file_type == "holdings":
                holdings = self._apply_holdings_schema_locally(schema, rows)
                return holdings, []
            elif file_type == "transactions":
                transactions = self._apply_transactions_schema_locally(schema, rows)
                return [], transactions
            else:
                logger.warning(f"Unknown file type '{file_type}', attempting fallback")
                return await self._fallback_basic_parse(rows)
            
        except Exception as e:
            logger.error("LLM extraction failed: %s", e, exc_info=True)
            # Fallback: try basic parsing
            return await self._fallback_basic_parse(rows)

    def _sanitize_value(self, value: Any) -> str:
        """
        Sanitize a CSV value to protect privacy while preserving type information.
        
        Args:
            value: Raw value from CSV
            
        Returns:
            Sanitized type indicator (e.g., "[DECIMAL]", "[TEXT]", "[DATE:MM/DD/YYYY]")
        """
        if value is None or value == "":
            return "[EMPTY]"
        
        value_str = str(value).strip()
        
        # Check for decimal/currency
        clean_val = value_str.replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
        try:
            float(clean_val)
            if "." in clean_val:
                return "[DECIMAL]"
            return "[INTEGER]"
        except ValueError:
            pass
        
        # Check for date patterns
        import re
        date_patterns = [
            (r'^\d{1,2}/\d{1,2}/\d{4}$', '[DATE:MM/DD/YYYY]'),
            (r'^\d{4}-\d{2}-\d{2}$', '[DATE:YYYY-MM-DD]'),
            (r'^\d{1,2}-\d{1,2}-\d{4}$', '[DATE:MM-DD-YYYY]'),
            (r'^[A-Za-z]{3} \d{1,2}, \d{4}$', '[DATE:Mon DD, YYYY]'),
        ]
        for pattern, indicator in date_patterns:
            if re.match(pattern, value_str):
                return indicator
        
        # Check for stock symbols (2-5 uppercase letters)
        if re.match(r'^[A-Z]{2,5}$', value_str):
            return "[SYMBOL]"
        
        # Default to text
        return "[TEXT]"

    def _apply_holdings_schema_locally(self, schema: dict, rows: list[dict]) -> list[InvestmentHolding]:
        """
        Apply LLM-generated schema to extract holdings data locally without LLM.
        
        Args:
            schema: Schema mapping from LLM
            rows: All CSV rows
            
        Returns:
            List of InvestmentHolding objects extracted locally
        """
        holdings = []
        
        for row in rows:
            try:
                # Extract symbol
                symbol_col = schema.get("symbol", {}).get("column")
                if not symbol_col or symbol_col not in row:
                    continue
                symbol = str(row[symbol_col]).strip().upper()
                if not symbol or symbol in ["", "N/A", "Total", "TOTAL"]:
                    continue
                
                # Extract quantity
                quantity_col = schema.get("quantity", {}).get("column")
                if not quantity_col or quantity_col not in row:
                    continue
                quantity_str = str(row[quantity_col]).replace(",", "").strip()
                if not quantity_str:
                    continue
                quantity = Decimal(quantity_str)
                if quantity <= 0:
                    continue
                
                # Extract optional fields
                price = None
                price_col = schema.get("price", {}).get("column")
                if price_col and price_col in row and row[price_col]:
                    price = Decimal(str(row[price_col]).replace("$", "").replace(",", "").strip())
                
                market_value = None
                mv_col = schema.get("market_value", {}).get("column")
                if mv_col and mv_col in row and row[mv_col]:
                    market_value = Decimal(str(row[mv_col]).replace("$", "").replace(",", "").strip())
                
                # Handle cost_basis - might need calculation
                cost_basis = None
                cb_config = schema.get("cost_basis", {})
                if "column" in cb_config:
                    cb_col = cb_config["column"]
                    if cb_col in row and row[cb_col]:
                        cost_basis = Decimal(str(row[cb_col]).replace("$", "").replace(",", "").strip())
                elif "calculation" in cb_config:
                    # Handle calculated cost_basis (e.g., market_value - gain_loss)
                    calc = cb_config["calculation"]
                    if "market_value - gain_loss" in calc:
                        uses_cols = cb_config.get("uses_columns", [])
                        if len(uses_cols) >= 2 and all(c in row for c in uses_cols):
                            mv = Decimal(str(row[uses_cols[0]]).replace("$", "").replace(",", "").strip())
                            gl_str = str(row[uses_cols[1]]).replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
                            gl = Decimal(gl_str)
                            cost_basis = mv - gl
                
                holding = InvestmentHolding(
                    symbol=symbol,
                    description=row.get(schema.get("description", {}).get("column", ""), ""),
                    quantity=quantity,
                    price=price,
                    value=market_value,
                    cost_basis=cost_basis,
                    gain_loss=None,
                    gain_loss_percent=None,
                    account_type=None,
                    asset_type="stock" if len(symbol) <= 5 else "mutual_fund",
                    raw_data=dict(row),
                )
                
                holdings.append(holding)
                
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Skipping row in holdings extraction: {e}")
                continue
        
        logger.info(f"Extracted {len(holdings)} holdings locally (privacy-preserving)")
        return holdings

    def _apply_transactions_schema_locally(self, schema: dict, rows: list[dict]) -> list[BankTransaction]:
        """
        Apply LLM-generated schema to extract transactions data locally without LLM.
        
        Args:
            schema: Schema mapping from LLM
            rows: All CSV rows
            
        Returns:
            List of BankTransaction objects extracted locally
        """
        transactions = []
        
        for row in rows:
            try:
                # Extract date
                date_col = schema.get("date", {}).get("column")
                if not date_col or date_col not in row or not row[date_col]:
                    continue
                
                date_str = str(row[date_col]).strip()
                date_format = schema.get("date", {}).get("format", "MM/DD/YYYY")
                
                # Parse date based on detected format
                from datetime import datetime
                format_map = {
                    "MM/DD/YYYY": "%m/%d/%Y",
                    "YYYY-MM-DD": "%Y-%m-%d",
                    "MM-DD-YYYY": "%m-%d-%Y",
                    "DD/MM/YYYY": "%d/%m/%Y",
                }
                python_format = format_map.get(date_format, "%m/%d/%Y")
                date = datetime.strptime(date_str, python_format).date()
                
                # Extract description
                desc_col = schema.get("description", {}).get("column")
                if not desc_col or desc_col not in row:
                    continue
                description = str(row[desc_col]).strip()
                if not description:
                    continue
                
                # Extract amount
                amount_col = schema.get("amount", {}).get("column")
                if not amount_col or amount_col not in row or not row[amount_col]:
                    continue
                
                amount_str = str(row[amount_col]).replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
                amount = Decimal(amount_str)
                
                # Determine transaction type
                sign_convention = schema.get("amount", {}).get("sign_convention", "negative_for_debits")
                txn_type_col = schema.get("transaction_type", {}).get("column")
                
                if txn_type_col and txn_type_col in row and row[txn_type_col]:
                    txn_type_str = str(row[txn_type_col]).upper().strip()
                    try:
                        txn_type = TransactionType[txn_type_str]
                    except KeyError:
                        # Try to map common transaction types
                        type_mapping = {
                            "SALE": TransactionType.PURCHASE,
                            "ACH": TransactionType.TRANSFER,
                            "WITHDRAWAL": TransactionType.WITHDRAWAL,
                            "DEPOSIT": TransactionType.DEPOSIT,
                        }
                        txn_type = type_mapping.get(txn_type_str, 
                                                    TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT)
                else:
                    # Use default or infer from amount
                    txn_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT
                
                # Extract optional fields
                category = None
                category_col = schema.get("category", {}).get("column")
                if category_col and category_col in row:
                    category = str(row[category_col]).strip() or None
                
                merchant = None
                merchant_col = schema.get("merchant", {}).get("column")
                if merchant_col and merchant_col in row:
                    merchant = str(row[merchant_col]).strip() or None
                
                transaction = BankTransaction(
                    date=date,
                    description=description,
                    amount=amount,
                    transaction_type=txn_type,
                    balance=None,
                    category=category,
                    merchant=merchant,
                    account_last_4=None,
                    check_number=None,
                    memo=None,
                    raw_data=dict(row),
                )
                
                transactions.append(transaction)
                
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Skipping row in transaction extraction: {e}")
                continue
        
        logger.info(f"Extracted {len(transactions)} transactions locally (privacy-preserving)")
        return transactions

    async def _fallback_basic_parse(self, rows: list[dict]) -> tuple[list[InvestmentHolding], list[BankTransaction]]:
        """
        Fallback parser if LLM fails - uses simple heuristics.
        
        Args:
            rows: CSV rows as dicts
            
        Returns:
            Tuple of (holdings list, transactions list)
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
        return holdings, []  # Fallback only handles holdings, not transactions
