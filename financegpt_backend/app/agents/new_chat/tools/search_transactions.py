"""
Transaction search tool for FinanceGPT.

This tool performs keyword-based search on transaction data,
perfect for finding specific merchants, categories, or transaction patterns.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document

logger = logging.getLogger(__name__)


def parse_plaid_markdown_transactions(content: str) -> list[dict[str, Any]]:
    """
    Parse transaction data from Plaid markdown format.
    
    Format: - **YYYY-MM-DD** - Description: +/-$amount (TransactionType.TYPE)
    Example: - **2026-01-10** - SparkFun: -$89.40 (TransactionType.PURCHASE)
    """
    transactions = []
    
    # Pattern: - **2026-01-10** - SparkFun: -$89.40 (TransactionType.PURCHASE)
    pattern = r'-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s+-\s+([^:]+):\s+([-+]?\$[\d,]+\.?\d*)\s+\(TransactionType\.(\w+)\)'
    
    for match in re.finditer(pattern, content):
        date_str = match.group(1)
        description = match.group(2).strip()
        amount_str = match.group(3).replace('$', '').replace(',', '')
        txn_type = match.group(4)
        
        # Parse amount (negative for spending, positive for deposits)
        try:
            amount = float(amount_str)
        except ValueError:
            continue
            
        transactions.append({
            "date": date_str,
            "description": description,
            "merchant": description,  # Use description as merchant for Plaid
            "amount": amount,
            "category": None,  # Plaid doesn't provide categories in markdown
            "transaction_type": txn_type,
        })
    
    return transactions


def create_search_transactions_tool(
    search_space_id: int,
    db_session: AsyncSession,
):
    """
    Create a transaction search tool.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for queries

    Returns:
        Langchain tool for searching transactions
    """

    @tool
    async def search_transactions(
        keywords: str | None = None,
        category: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """Search for transactions by merchant, category, or keywords.

        Use this tool when users ask about:
        - Specific merchants (e.g., "Doordash", "Starbucks", "Costco")
        - Spending categories (e.g., "restaurants", "groceries", "gas", "travel")
        - Transaction patterns across time periods
        
        This tool searches the structured transaction data with exact matching for 
        merchants and categories.

        Args:
            keywords: Merchant name or keywords to search for (e.g., "DOORDASH", "starbucks")
            category: Transaction category (e.g., "Food & Drink", "Groceries", "Travel", "Gas", "Shopping")
            start_date: Optional start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format  
            limit: Maximum number of transactions to return (default: 1000)

        Returns:
            A dictionary containing:
            - transactions: List of matching transactions with details
            - total_amount: Sum of all transaction amounts
            - count: Number of transactions found
            - summary: Text summary of results
            - categories_breakdown: Spending by category (if no category filter)

        Examples:
            User: "How much did I spend on Doordash last year?"
            Tool call: search_transactions(keywords="doordash", start_date="2025-01-01", end_date="2025-12-31")
            
            User: "Show me all my restaurant spending"
            Tool call: search_transactions(category="Food & Drink")
            
            User: "What did I spend on groceries in December?"
            Tool call: search_transactions(category="Groceries", start_date="2025-12-01", end_date="2025-12-31")
        """
        try:
            if not keywords and not category:
                return {
                    "transactions": [],
                    "total_amount": 0,
                    "count": 0,
                    "summary": "Please provide either keywords or category to search",
                }

            logger.info(f"Searching transactions: keywords={keywords}, category={category}")

            # Get financial documents (both manual uploads and Plaid)
            # Need to get both metadata and content for Plaid documents
            query = (
                select(Document.document_metadata, Document.content, Document.document_metadata.op("->>")("is_plaid_document"))
                .where(
                    and_(
                        Document.search_space_id == search_space_id,
                        # Match either manual uploads or Plaid documents
                        (
                            (Document.document_metadata.op("->>")("is_financial_document") == "true") |
                            (Document.document_metadata.op("->>")("is_plaid_document") == "true")
                        )
                    )
                )
            )

            result = await db_session.execute(query)
            documents = result.all()

            if not documents:
                return {
                    "transactions": [],
                    "total_amount": 0,
                    "count": 0,
                    "summary": "No financial documents found",
                }

            # Extract and filter transactions
            all_transactions = []
            for doc_metadata, doc_content, is_plaid in documents:
                transactions = []
                
                # Handle Plaid documents (parse markdown)
                if is_plaid == "true" and doc_content:
                    transactions = parse_plaid_markdown_transactions(doc_content)
                else:
                    # Handle manual upload documents (JSON metadata)
                    # Parse JSON if it's a string
                    if isinstance(doc_metadata, str):
                        try:
                            doc_metadata = json.loads(doc_metadata)
                        except json.JSONDecodeError:
                            logger.error("Failed to parse document metadata as JSON")
                            continue
                    
                    financial_data = doc_metadata.get("financial_data", {})
                    
                    # Parse financial_data if it's also a JSON string
                    if isinstance(financial_data, str):
                        try:
                            financial_data = json.loads(financial_data)
                        except json.JSONDecodeError:
                            logger.error("Failed to parse financial_data as JSON")
                            continue
                    
                    transactions = financial_data.get("transactions", [])
                
                for txn in transactions:
                    # Date filtering
                    txn_date_str = txn.get("date", "")
                    if txn_date_str:
                        try:
                            txn_date = datetime.fromisoformat(txn_date_str.replace("Z", "+00:00")).date()
                            
                            if start_date:
                                start = datetime.strptime(start_date, "%Y-%m-%d").date()
                                if txn_date < start:
                                    continue
                            if end_date:
                                end = datetime.strptime(end_date, "%Y-%m-%d").date()
                                if txn_date > end:
                                    continue
                        except (ValueError, AttributeError):
                            continue
                    
                    # Category filtering (exact match, case-insensitive)
                    # Only filter by category if the transaction has one (manual uploads)
                    # Plaid transactions don't have categories, so skip category filter for them
                    if category:
                        txn_category = txn.get("category")
                        if txn_category is not None:  # Has a category
                            if category.lower() not in txn_category.lower():
                                continue
                        # If txn_category is None (Plaid), don't filter - rely on keywords instead
                    
                    # Keywords filtering (search in description/merchant)
                    if keywords:
                        description = (txn.get("description") or "").lower()
                        merchant = (txn.get("merchant") or "").lower()
                        keywords_lower = keywords.lower()
                        
                        if keywords_lower not in description and keywords_lower not in merchant:
                            continue
                    
                    # Add matching transaction
                    all_transactions.append({
                        "date": txn_date_str.split("T")[0] if txn_date_str else None,
                        "description": txn.get("description"),
                        "merchant": txn.get("merchant"),
                        "amount": float(txn.get("amount", 0)),
                        "category": txn.get("category"),
                        "transaction_type": txn.get("transaction_type", "").replace("TransactionType.", ""),
                    })
                    
                    if len(all_transactions) >= limit:
                        break
                
                if len(all_transactions) >= limit:
                    break

            # Sort by date descending
            all_transactions.sort(key=lambda x: x.get("date", ""), reverse=True)

            # Calculate totals (only negative amounts are spending)
            total_amount = sum(abs(t["amount"]) for t in all_transactions if t["amount"] < 0)
            count = len(all_transactions)

            # Build category breakdown if no category filter
            categories_breakdown = {}
            if not category and all_transactions:
                for txn in all_transactions:
                    if txn["amount"] < 0:  # Only spending
                        cat = txn.get("category") or "Uncategorized"
                        categories_breakdown[cat] = categories_breakdown.get(cat, 0) + abs(txn["amount"])

            # Build summary
            date_range = ""
            if start_date and end_date:
                date_range = f" between {start_date} and {end_date}"
            elif start_date:
                date_range = f" since {start_date}"
            elif end_date:
                date_range = f" until {end_date}"

            search_desc = category if category else f"'{keywords}'"
            summary = (
                f"Found {count} transaction(s) for {search_desc}{date_range}. "
                f"Total spent: ${total_amount:.2f}"
            )

            return {
                "transactions": all_transactions[:100],  # Return max 100 for display
                "total_amount": total_amount,
                "count": count,
                "summary": summary,
                "categories_breakdown": categories_breakdown if categories_breakdown else None,
            }

        except Exception as e:
            logger.error(f"Error searching transactions: {e}", exc_info=True)
            return {
                "transactions": [],
                "total_amount": 0,
                "count": 0,
                "summary": f"Error searching transactions: {str(e)}",
            }

    return search_transactions
