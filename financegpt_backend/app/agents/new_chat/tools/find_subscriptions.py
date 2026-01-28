"""
Subscription finder tool for FinanceGPT.

This tool analyzes transactions to identify recurring subscriptions
and provides insights on usage, value, and recommendations.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connector_service import ConnectorService
from app.utils.subscription_utils import (
    create_merchant_amount_key,
    normalize_merchant,
)

logger = logging.getLogger(__name__)


def create_find_subscriptions_tool(
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
):
    """
    Create a subscription finder tool.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for queries
        connector_service: Service for searching knowledge base

    Returns:
        Langchain tool for finding subscriptions
    """

    @tool
    async def find_subscriptions(
        min_occurrences: int = 2,
        days_back: int = 90,
    ) -> dict[str, Any]:
        """Find recurring subscriptions and memberships in transaction history.

        This tool analyzes your transactions to identify potential subscriptions
        by looking for recurring charges from the same merchants.

        Args:
            min_occurrences: Minimum number of charges to consider as subscription (default: 2)
            days_back: How many days of history to analyze (default: 90)

        Returns:
            A dictionary containing:
            - subscriptions: List of detected subscriptions with details
            - total_monthly_cost: Estimated total monthly subscription cost
            - summary: Text summary of findings
            - recommendations: List of actionable recommendations

        Example:
            User: "Find all my subscriptions"
            Tool returns: {
                "subscriptions": [
                    {
                        "merchant": "Netflix",
                        "amount": 15.99,
                        "frequency": "monthly",
                        "charge_count": 6,
                        "total_spent": 95.94,
                        "first_charge": "2023-07-15",
                        "last_charge": "2024-01-15",
                        "status": "active"
                    }
                ],
                "total_monthly_cost": 87.45,
                "summary": "Found 8 active subscriptions costing $87.45/month"
            }
        """
        try:
            logger.info(f"Searching for subscriptions in last {days_back} days")

            # Search for transaction documents
            _, transaction_results = await connector_service.search_files(
                user_query="transactions charges payments subscriptions",
                search_space_id=search_space_id,
                top_k=30,  # Reduced from 100 to prevent context overflow
            )

            if not transaction_results:
                return {
                    "subscriptions": [],
                    "total_monthly_cost": 0,
                    "summary": "No transaction data found.",
                    "recommendations": [],
                }

            # Extract and group transactions
            transactions = _extract_transactions_from_results(transaction_results)
            logger.info(f"Extracted {len(transactions)} transactions from results")

            # Group by merchant + amount
            grouped_transactions = _group_transactions_by_merchant(transactions)
            logger.info(f"Grouped into {len(grouped_transactions)} unique merchant patterns")

            # Identify recurring patterns
            subscriptions = []
            for key, txn_list in grouped_transactions.items():
                if len(txn_list) >= min_occurrences:
                    subscription_info = _analyze_subscription_pattern(txn_list)
                    if subscription_info:
                        subscriptions.append(subscription_info)

            # Sort by total spent (descending)
            subscriptions.sort(key=lambda x: x.get("total_spent", 0), reverse=True)

            # Calculate total monthly cost
            total_monthly = sum(
                sub.get("estimated_monthly_cost", 0) for sub in subscriptions
            )

            # Generate summary
            active_subs = [s for s in subscriptions if s.get("status") == "active"]
            summary = f"Found {len(active_subs)} active subscriptions with estimated monthly cost of ${total_monthly:.2f}"

            # Generate recommendations
            recommendations = _generate_recommendations(subscriptions)

            return {
                "subscriptions": subscriptions,
                "total_monthly_cost": round(total_monthly, 2),
                "summary": summary,
                "recommendations": recommendations,
                "analysis_period_days": days_back,
            }

        except Exception as e:
            logger.error(f"Error finding subscriptions: {e}", exc_info=True)
            return {
                "subscriptions": [],
                "total_monthly_cost": 0,
                "summary": f"Error analyzing subscriptions: {str(e)}",
                "recommendations": [],
            }

    return find_subscriptions


def _extract_transactions_from_results(results: list) -> list[dict]:
    """Extract individual transactions from search results."""
    transactions = []
    
    for doc in results:
        # Handle both dict and LangChain document format
        if isinstance(doc, dict):
            content = doc.get('content', '')
        elif hasattr(doc, 'page_content'):
            content = doc.page_content
        else:
            content = str(doc)
        
        # Parse markdown transaction lines
        # Format: - **2024-01-15** - Netflix: -$15.99 (Subscription)
        import re
        pattern = r'-\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s+-\s+([^:]+):\s+([+-]?\$[\d,.]+)\s+\(([^)]+)\)'
        
        for match in re.finditer(pattern, content):
            date_str, description, amount_str, category = match.groups()
            
            # Parse amount
            amount = float(amount_str.replace('$', '').replace(',', ''))
            
            # Only include debits (expenses)
            if amount < 0:
                transactions.append({
                    'date': date_str,
                    'description': description.strip(),
                    'amount': abs(amount),
                    'category': category.strip(),
                })
    
    return transactions


def _group_transactions_by_merchant(transactions: list[dict]) -> dict[str, list]:
    """Group transactions by normalized merchant name and amount."""
    grouped = defaultdict(list)
    
    for txn in transactions:
        merchant = txn['description']
        amount = txn['amount']
        
        # Create grouping key
        key = create_merchant_amount_key(merchant, amount)
        
        txn['merchant_normalized'] = normalize_merchant(merchant)
        txn['merchant_raw'] = merchant
        
        grouped[key].append(txn)
    
    return dict(grouped)


def _analyze_subscription_pattern(transactions: list[dict]) -> dict[str, Any] | None:
    """Analyze a group of transactions to determine if it's a subscription."""
    if not transactions:
        return None
    
    # Sort by date
    sorted_txns = sorted(transactions, key=lambda x: x['date'])
    
    # Calculate intervals between charges
    intervals = []
    for i in range(1, len(sorted_txns)):
        date1 = datetime.fromisoformat(sorted_txns[i-1]['date'])
        date2 = datetime.fromisoformat(sorted_txns[i]['date'])
        days_between = (date2 - date1).days
        intervals.append(days_between)
    
    # Determine if it's recurring
    if not intervals:
        return None
    
    avg_interval = sum(intervals) / len(intervals)
    
    # Classify frequency
    if 25 <= avg_interval <= 35:
        frequency = "monthly"
        estimated_monthly_cost = transactions[0]['amount']
    elif 85 <= avg_interval <= 95:
        frequency = "quarterly"
        estimated_monthly_cost = transactions[0]['amount'] / 3
    elif 355 <= avg_interval <= 375:
        frequency = "yearly"
        estimated_monthly_cost = transactions[0]['amount'] / 12
    elif 6 <= avg_interval <= 8:
        frequency = "weekly"
        estimated_monthly_cost = transactions[0]['amount'] * 4
    else:
        frequency = f"every {int(avg_interval)} days"
        estimated_monthly_cost = (transactions[0]['amount'] * 30) / avg_interval
    
    # Check if still active (last charge within expected interval + grace period)
    last_charge_date = datetime.fromisoformat(sorted_txns[-1]['date'])
    days_since_last = (datetime.now() - last_charge_date).days
    grace_period = avg_interval * 1.5  # 50% grace period
    
    status = "active" if days_since_last < grace_period else "inactive"
    
    # If inactive for too long, mark as zombie
    if days_since_last > avg_interval * 2:
        status = "zombie"
    
    return {
        "merchant": transactions[0]['merchant_normalized'],
        "merchant_raw": transactions[0]['merchant_raw'],
        "amount": round(transactions[0]['amount'], 2),
        "frequency": frequency,
        "charge_count": len(transactions),
        "total_spent": round(sum(t['amount'] for t in transactions), 2),
        "first_charge": sorted_txns[0]['date'],
        "last_charge": sorted_txns[-1]['date'],
        "days_since_last_charge": days_since_last,
        "average_interval_days": round(avg_interval, 1),
        "estimated_monthly_cost": round(estimated_monthly_cost, 2),
        "status": status,
        "category": transactions[0].get('category', 'Unknown'),
    }


def _generate_recommendations(subscriptions: list[dict]) -> list[str]:
    """Generate actionable recommendations based on subscription analysis."""
    recommendations = []
    
    # Find zombie subscriptions
    zombies = [s for s in subscriptions if s.get('status') == 'zombie']
    if zombies:
        total_waste = sum(s.get('estimated_monthly_cost', 0) for s in zombies)
        zombie_names = ", ".join(s['merchant'] for s in zombies[:3])
        recommendations.append(
            f"🧟 Cancel {len(zombies)} zombie subscription(s) to save ${total_waste:.2f}/month: {zombie_names}"
        )
    
    # Find duplicate categories
    by_category = defaultdict(list)
    for sub in subscriptions:
        if sub.get('status') == 'active':
            category = sub.get('category', 'Unknown')
            by_category[category].append(sub)
    
    for category, subs in by_category.items():
        if len(subs) > 1 and 'streaming' in category.lower():
            total = sum(s.get('estimated_monthly_cost', 0) for s in subs)
            names = ", ".join(s['merchant'] for s in subs)
            recommendations.append(
                f"📺 You have {len(subs)} streaming services ({names}) costing ${total:.2f}/month - consider consolidating"
            )
    
    # Find expensive subscriptions
    expensive = [s for s in subscriptions if s.get('estimated_monthly_cost', 0) > 50]
    if expensive:
        for sub in expensive[:2]:
            recommendations.append(
                f"💰 {sub['merchant']} costs ${sub['estimated_monthly_cost']:.2f}/month - verify you're getting value"
            )
    
    # General advice
    if subscriptions:
        total_annual = sum(s.get('estimated_monthly_cost', 0) for s in subscriptions) * 12
        recommendations.append(
            f"📊 Total annual subscription cost: ${total_annual:.2f} - review quarterly to avoid waste"
        )
    
    return recommendations
