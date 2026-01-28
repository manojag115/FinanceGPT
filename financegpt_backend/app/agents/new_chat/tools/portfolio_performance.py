"""
Portfolio performance analysis tool for FinanceGPT.

This tool calculates historical portfolio performance by:
1. Searching for current holdings in the knowledge base
2. Extracting ticker symbols and quantities
3. Looking up historical prices via web search (future enhancement)
4. Calculating performance metrics based on cost basis
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document
from app.services.connector_service import ConnectorService

logger = logging.getLogger(__name__)


async def _get_latest_holdings_snapshot(
    session: AsyncSession,
    search_space_id: int,
) -> Document | None:
    """
    Get the most recent investment holdings snapshot.
    
    Args:
        session: Database session
        search_space_id: User's search space ID
        
    Returns:
        Latest holdings document or None
    """
    stmt = (
        select(Document)
        .where(
            and_(
                Document.search_space_id == search_space_id,
                Document.document_metadata["document_subtype"].as_string() == "investment_holdings",
                or_(
                    Document.document_metadata["is_plaid_document"].as_string() == "true",
                    Document.document_metadata["is_financial_document"].as_string() == "true",
                ),
            )
        )
        .order_by(Document.document_metadata["snapshot_date"].as_string().desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_holdings_snapshot_near_date(
    session: AsyncSession,
    search_space_id: int,
    target_date: datetime,
) -> Document | None:
    """
    Get the holdings snapshot closest to a target date (not after it).
    
    Args:
        session: Database session
        search_space_id: User's search space ID
        target_date: Target date to find snapshot for
        
    Returns:
        Closest holdings document on or before target date, or None
    """
    target_iso = target_date.isoformat()
    
    stmt = (
        select(Document)
        .where(
            and_(
                Document.search_space_id == search_space_id,
                Document.document_metadata["document_subtype"].as_string() == "investment_holdings",
                or_(
                    Document.document_metadata["is_plaid_document"].as_string() == "true",
                    Document.document_metadata["is_financial_document"].as_string() == "true",
                ),
                Document.document_metadata["snapshot_date"].as_string() <= target_iso,
            )
        )
        .order_by(Document.document_metadata["snapshot_date"].as_string().desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def create_portfolio_performance_tool(
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
):
    """
    Create a portfolio performance calculation tool.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for queries
        connector_service: Service for searching knowledge base

    Returns:
        Langchain tool for calculating portfolio performance
    """

    @tool
    async def calculate_portfolio_performance(
        time_period: str = "week",
    ) -> dict[str, Any]:
        """Calculate portfolio performance over a specified time period.

        This tool analyzes your investment portfolio's performance by looking up
        current holdings and comparing them to historical prices.

        Args:
            time_period: The time period for performance calculation. Options:
                - "week" or "wow": Week-over-week (last 7 days)
                - "month" or "mom": Month-over-month (last 30 days)
                - "quarter" or "qtd": Quarter-to-date (last 90 days)
                - "year" or "yoy": Year-over-year (last 365 days)
                Default: "week"

        Returns:
            A dictionary containing:
            - summary: Overall portfolio performance summary
            - holdings: List of individual holdings with performance data
            - total_value: Current total portfolio value
            - total_change_dollars: Total dollar change
            - total_change_percent: Total percentage change
            - period: The time period analyzed
            - note: Any important notes or limitations

        Example:
            User: "What's my portfolio performance this week?"
            Tool returns: {
                "summary": "Your portfolio gained $1,234 (+5.2%) this week",
                "holdings": [
                    {
                        "name": "Southside Bancshares (SBSI)",
                        "current_value": 7397.49,
                        "change_dollars": 347.00,
                        "change_percent": 4.9
                    }
                ],
                "total_value": 25125.63,
                "total_change_dollars": 1234.56,
                "total_change_percent": 5.2
            }
        """
        try:
            # Normalize time period
            period_lower = time_period.lower().strip()
            if period_lower in ["week", "wow", "w"]:
                days_back = 7
                period_label = "Week-over-Week"
            elif period_lower in ["month", "mom", "m"]:
                days_back = 30
                period_label = "Month-over-Month"
            elif period_lower in ["quarter", "qtd", "q", "quarterly"]:
                days_back = 90
                period_label = "Quarterly"
            elif period_lower in ["year", "yoy", "y", "annual"]:
                days_back = 365
                period_label = "Year-over-Year"
            else:
                days_back = 7
                period_label = "Week-over-Week"

            # Step 1: Get current holdings snapshot
            logger.info(f"Getting latest holdings snapshot for search_space_id={search_space_id}")

            current_snapshot = await _get_latest_holdings_snapshot(db_session, search_space_id)
            
            if not current_snapshot:
                return {
                    "summary": "No investment holdings found in your accounts.",
                    "holdings": [],
                    "total_value": 0,
                    "total_change_dollars": 0,
                    "total_change_percent": 0,
                    "period": period_label,
                    "note": "Please connect your investment accounts or sync your holdings data.",
                }

            # Extract current holdings data
            current_holdings = _extract_holdings_from_results([current_snapshot])
            logger.info(f"Extracted {len(current_holdings)} holdings from current snapshot")

            if not current_holdings:
                return {
                    "summary": "Could not extract holdings information from your accounts.",
                    "holdings": [],
                    "total_value": 0,
                    "total_change_dollars": 0,
                    "total_change_percent": 0,
                    "period": period_label,
                    "note": "Holdings data may not be in the expected format. Please sync your accounts.",
                }

            # Step 2: Get historical snapshot for comparison
            target_date = datetime.now(UTC) - timedelta(days=days_back)
            logger.info(f"Target date for comparison: {target_date.strftime('%Y-%m-%d')} ({days_back} days ago)")
            
            historical_snapshot = await _get_holdings_snapshot_near_date(
                db_session, search_space_id, target_date
            )
            
            # Extract historical holdings if available
            historical_holdings_map = {}
            if historical_snapshot:
                historical_holdings = _extract_holdings_from_results([historical_snapshot])
                # Create a map by ticker for easy lookup
                historical_holdings_map = {
                    h["ticker"]: h for h in historical_holdings if h.get("ticker")
                }
                logger.info(
                    f"Found historical snapshot from {historical_snapshot.document_metadata.get('snapshot_date', 'unknown')} "
                    f"with {len(historical_holdings)} holdings"
                )
            else:
                logger.info(f"No historical snapshot found for {target_date.strftime('%Y-%m-%d')}")
            
            # Step 3: Calculate performance by comparing snapshots
            performance_holdings = []
            total_current_value = 0
            total_historical_value = 0
            has_historical_data = len(historical_holdings_map) > 0

            for holding in current_holdings:
                current_value = holding.get("value", 0)
                current_price = holding.get("price", 0)
                quantity = holding.get("quantity", 0)
                ticker = holding.get("ticker", "")
                name = holding.get("name", "Unknown")
                
                total_current_value += current_value
                
                # Try to find this holding in historical snapshot
                historical_holding = historical_holdings_map.get(ticker) if ticker else None
                
                if historical_holding:
                    # Calculate period-specific performance from snapshot comparison
                    historical_value = historical_holding.get("value", 0)
                    historical_price = historical_holding.get("price", 0)
                    historical_quantity = historical_holding.get("quantity", 0)
                    total_historical_value += historical_value
                    
                    value_change = current_value - historical_value
                    price_change = current_price - historical_price if historical_price > 0 else 0
                    price_change_pct = (price_change / historical_price) * 100 if historical_price > 0 else 0
                    value_change_pct = (value_change / historical_value) * 100 if historical_value > 0 else 0
                    
                    performance_holdings.append({
                        "name": name,
                        "ticker": ticker,
                        "current_quantity": quantity,
                        "historical_quantity": historical_quantity,
                        "quantity_change": quantity - historical_quantity,
                        "current_price": current_price,
                        "current_value": current_value,
                        "historical_price": historical_price,
                        "historical_value": historical_value,
                        "price_change_dollars": price_change,
                        "price_change_percent": price_change_pct,
                        "value_change_dollars": value_change,
                        "value_change_percent": value_change_pct,
                    })
                else:
                    # Position didn't exist in historical snapshot (newly added)
                    # Fall back to cost basis if available
                    cost_basis = holding.get("cost_basis", 0)
                    if cost_basis and cost_basis > 0:
                        gain_loss = current_value - cost_basis
                        gain_loss_pct = (gain_loss / cost_basis) * 100
                        
                        performance_holdings.append({
                            "name": name,
                            "ticker": ticker,
                            "quantity": quantity,
                            "current_value": current_value,
                            "cost_basis": cost_basis,
                            "gain_loss_dollars": gain_loss,
                            "gain_loss_percent": gain_loss_pct,
                            "note": "New position (not in historical snapshot) - showing total return",
                        })
                    else:
                        # No historical or cost basis data
                        performance_holdings.append({
                            "name": name,
                            "ticker": ticker,
                            "quantity": quantity,
                            "current_value": current_value,
                            "note": "New position - performance data not available",
                        })

            # Calculate total portfolio performance
            if has_historical_data and total_historical_value > 0:
                # Period-specific performance available from snapshot comparison
                total_change = total_current_value - total_historical_value
                total_change_pct = (total_change / total_historical_value) * 100

                snapshot_date = historical_snapshot.document_metadata.get("snapshot_date", "unknown")
                if isinstance(snapshot_date, str) and "T" in snapshot_date:
                    snapshot_date_str = datetime.fromisoformat(snapshot_date).strftime('%Y-%m-%d')
                else:
                    snapshot_date_str = str(snapshot_date)

                summary = (
                    f"Your portfolio {period_label} performance: ${total_change:+,.2f} ({total_change_pct:+.2f}%). "
                    f"Current value: ${total_current_value:,.2f}, on {snapshot_date_str}: ${total_historical_value:,.2f}."
                )
                
                return {
                    "summary": summary,
                    "holdings": performance_holdings,
                    "total_value": total_current_value,
                    "total_historical_value": total_historical_value,
                    "total_change_dollars": total_change,
                    "total_change_percent": total_change_pct,
                    "period_requested": period_label,
                    "calculation_method": "snapshot_comparison",
                    "historical_snapshot_date": snapshot_date_str,
                    "note": f"Performance calculated by comparing current snapshot to historical snapshot from {snapshot_date_str}",
                }
            else:
                # Fall back to cost basis for total return
                total_cost_basis = sum(h.get("cost_basis", 0) for h in performance_holdings if h.get("cost_basis"))
                
                if total_cost_basis > 0:
                    total_gain_loss = total_current_value - total_cost_basis
                    total_gain_loss_pct = (total_gain_loss / total_cost_basis) * 100

                    summary = (
                        f"Your portfolio has a total value of ${total_current_value:,.2f} with "
                        f"an overall return of ${total_gain_loss:,.2f} ({total_gain_loss_pct:+.2f}%) "
                        f"since purchase. (Note: {period_label} data unavailable, showing total return)"
                    )
                else:
                    total_gain_loss = 0
                    total_gain_loss_pct = 0
                    summary = (
                        f"Your portfolio has a total value of ${total_current_value:,.2f}. "
                        f"Historical performance data is not available."
                    )

                return {
                    "summary": summary,
                    "holdings": performance_holdings,
                    "total_value": total_current_value,
                    "total_cost_basis": total_cost_basis,
                    "total_gain_loss_dollars": total_gain_loss,
                    "total_gain_loss_percent": total_gain_loss_pct,
                    "period_requested": period_label,
                    "calculation_method": "cost_basis",
                    "note": (
                        f"No historical snapshot available for {period_label} comparison. "
                        f"Showing total return since purchase based on cost basis. "
                        f"Historical snapshots will be available after syncing data for {days_back}+ days."
                    ),
                }

        except Exception as e:
            logger.error(f"ERROR calculating portfolio performance: {e}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            return {
                "summary": f"Error calculating portfolio performance: {str(e)}",
                "holdings": [],
                "total_value": 0,
                "total_change_dollars": 0,
                "total_change_percent": 0,
                "period": period_label if "period_label" in locals() else "Unknown",
                "note": "An error occurred while analyzing your portfolio.",
            }

    return calculate_portfolio_performance


def _extract_holdings_from_results(docs: list) -> list[dict]:
    """
    Extract holdings data from documents.

    Parses markdown-formatted holdings documents to extract:
    - Security name and ticker
    - Quantity
    - Current price and value
    - Cost basis and gain/loss

    Args:
        docs: List of Document objects (SQLAlchemy) or LangChain documents

    Returns:
        List of holding dictionaries with extracted data
    """
    holdings = []

    for doc in docs:
        # Handle different document formats
        if hasattr(doc, "content"):
            # SQLAlchemy Document object
            content = doc.content
        elif isinstance(doc, dict):
            content = doc.get('content', '')
        elif hasattr(doc, "page_content"):
            # LangChain document
            content = doc.page_content
        else:
            content = str(doc)

        # Look for holdings in markdown format
        # Pattern: #### Security Name (TICKER)
        # - **Type:** Equity
        # - **Quantity:** 100.0000 shares
        # - **Price:** $73.97 per share
        # - **Value:** $7,397.49 | **Gain/Loss:** +$7,367.49 (+24558.30%)

        # Find all security sections - match heading followed by list items (with variable whitespace)
        security_pattern = r"#### (.+?)(?:\(([^)]+)\))?\s*\n+((?:- .+?\n)+)"
        matches = re.finditer(security_pattern, content, re.MULTILINE)

        for match in matches:
            name = match.group(1).strip()
            ticker = match.group(2).strip() if match.group(2) else ""
            details = match.group(3)

            # Extract values
            quantity_match = re.search(r"\*\*Quantity:\*\* ([\d,.]+)", details)
            price_match = re.search(r"\*\*Price:\*\* \$([\d,.]+)", details)
            value_match = re.search(r"\*\*Value:\*\* \$([\d,.]+)", details)
            gain_loss_match = re.search(
                r"\*\*Gain/Loss:\*\* ([+-])\$([\d,.]+) \(([+-]?[\d,.]+)%\)", details
            )

            quantity = (
                float(quantity_match.group(1).replace(",", ""))
                if quantity_match
                else 0
            )
            price = (
                float(price_match.group(1).replace(",", "")) if price_match else 0
            )
            value = (
                float(value_match.group(1).replace(",", "")) if value_match else 0
            )

            # Calculate cost basis from gain/loss if available
            cost_basis = None
            if gain_loss_match and value > 0:
                sign = gain_loss_match.group(1)
                gain_amount = float(gain_loss_match.group(2).replace(",", ""))
                if sign == "+":
                    cost_basis = value - gain_amount
                else:
                    cost_basis = value + gain_amount

            holdings.append(
                {
                    "name": name,
                    "ticker": ticker,
                    "quantity": quantity,
                    "price": price,
                    "value": value,
                    "cost_basis": cost_basis if cost_basis and cost_basis > 0 else None,
                }
            )

    return holdings
