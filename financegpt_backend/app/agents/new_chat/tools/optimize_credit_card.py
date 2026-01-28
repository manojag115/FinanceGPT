"""
Credit card optimization tool for FinanceGPT.

This tool analyzes user's credit card transactions and recommends the optimal
card to use for each purchase category based on rewards structures.
"""

import json
import logging
import re
from datetime import datetime, timedelta, UTC
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document
from app.services.connector_service import ConnectorService
from app.utils.credit_card_rewards_fetcher import CreditCardRewardsFetcher

logger = logging.getLogger(__name__)


def create_optimize_credit_card_usage_tool(
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
):
    """
    Create a credit card optimization tool.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for queries
        connector_service: Service for searching knowledge base

    Returns:
        Langchain tool for optimizing credit card usage
    """

    @tool
    async def optimize_credit_card_usage(
        time_period: str = "month",
    ) -> dict[str, Any]:
        """Analyze credit card usage and recommend optimal cards for each category.

        This tool analyzes your recent credit card transactions, fetches the rewards
        structures for all your cards, and identifies opportunities to maximize rewards
        by using the right card for each purchase category.

        Args:
            time_period: Time period to analyze. Options:
                - "week": Last 7 days
                - "month" (default): Last 30 days
                - "quarter": Last 90 days

        Returns:
            A dictionary containing:
            - summary: Overall optimization summary
            - missed_rewards: Total money left on the table
            - recommendations: List of specific card usage recommendations
            - category_analysis: Breakdown by spending category
            - potential_annual_savings: Estimated yearly savings if optimized

        Example:
            User: "Which credit card should I use for groceries?"
            Tool returns: {
                "summary": "You could save $42.50/month by optimizing card usage",
                "missed_rewards": 42.50,
                "recommendations": [
                    {
                        "category": "groceries",
                        "current_card": "Chase Sapphire Preferred",
                        "current_rate": 1.0,
                        "optimal_card": "Amex Blue Cash Everyday",
                        "optimal_rate": 3.0,
                        "monthly_spend": 850.00,
                        "savings": 17.00
                    }
                ],
                "potential_annual_savings": 510.00
            }
        """
        try:
            # Parse time period
            days_back = {"week": 7, "month": 30, "quarter": 90}.get(
                time_period.lower(), 30
            )

            # Step 1: Find user's credit cards from Plaid accounts and manual uploads
            logger.info("Fetching user's credit card accounts")
            cards_info = await _get_user_credit_cards(
                connector_service, search_space_id, db_session
            )

            if not cards_info:
                return {
                    "summary": "No credit card accounts found. Please connect your credit cards via Plaid to use this feature.",
                    "error": "NO_CARDS_FOUND",
                }

            logger.info(f"Found {len(cards_info)} credit card(s)")

            # Step 2: Fetch rewards structures for each card
            logger.info("Fetching rewards structures for credit cards")
            llm_service = await _get_llm_service(db_session, search_space_id)
            rewards_fetcher = CreditCardRewardsFetcher(llm_service)

            cards_with_rewards = []
            cards_with_real_rewards = 0
            cards_with_fallback_rewards = 0

            for card in cards_info:
                card_name = card["name"]
                logger.info(f"Fetching rewards for: {card_name}")

                rewards = await rewards_fetcher.fetch_rewards_structure(
                    session=db_session,
                    card_name=card_name,
                    search_space_id=search_space_id,
                    user_id=card["user_id"],
                )

                if rewards:
                    cards_with_rewards.append(
                        {
                            "account_id": card["account_id"],
                            "name": card_name,
                            "rewards": rewards.get("rewards", {}),
                            "annual_fee": rewards.get("annual_fee", 0),
                            "currency": rewards.get("currency", "points"),
                        }
                    )
                    cards_with_real_rewards += 1
                else:
                    # Fallback to 1% default if can't fetch rewards
                    logger.warning(
                        f"Could not fetch rewards for {card_name}, using 1% default"
                    )
                    cards_with_rewards.append(
                        {
                            "account_id": card["account_id"],
                            "name": card_name,
                            "rewards": {"default": 1.0},
                            "annual_fee": 0,
                            "currency": "cashback",
                        }
                    )
                    cards_with_fallback_rewards += 1

            if not cards_with_rewards:
                return {
                    "summary": "Could not fetch rewards information for your cards. Please try again later.",
                    "error": "REWARDS_FETCH_FAILED",
                }

            # Step 3: Fetch recent transactions
            logger.info(f"Fetching transactions for last {days_back} days")
            transactions = await _get_user_transactions(
                db_session, search_space_id, days_back
            )

            if not transactions:
                return {
                    "summary": f"No transactions found in the last {days_back} days.",
                    "cards_analyzed": len(cards_with_rewards),
                }

            logger.info(f"Found {len(transactions)} transactions to analyze")

            # Step 4: Analyze transactions and calculate optimization opportunities
            logger.info("Analyzing transaction optimization opportunities")
            analysis = await _analyze_card_optimization(
                transactions=transactions,
                cards_with_rewards=cards_with_rewards,
                days_back=days_back,
            )

            # Add disclaimer if using fallback data
            if cards_with_fallback_rewards > 0:
                analysis["warning"] = (
                    f"⚠️ Could not fetch real rewards data for {cards_with_fallback_rewards} of your {len(cards_with_rewards)} cards. "
                    f"Analysis assumes 1% rewards for those cards. Results may not reflect actual optimization opportunities. "
                    f"Please ensure your credit card account names match known card products (e.g., 'Chase Sapphire Preferred', 'Amex Blue Cash')."
                )

            return analysis

        except Exception as e:
            logger.error(f"Error optimizing credit card usage: {e}", exc_info=True)
            return {
                "summary": f"Error analyzing credit card usage: {str(e)}",
                "error": "ANALYSIS_ERROR",
            }

    return optimize_credit_card_usage


async def _get_user_credit_cards(
    connector_service: ConnectorService,
    search_space_id: int,
    db_session: AsyncSession,
) -> list[dict[str, Any]]:
    """
    Extract user's credit card accounts from Plaid account summaries and manual CSV uploads.

    Args:
        connector_service: Service for searching documents
        search_space_id: User's search space ID
        db_session: Database session for direct queries

    Returns:
        List of credit card account dictionaries with name and account_id
    """
    try:
        cards = []
        
        # First, check for manual CSV uploads (financial documents)
        logger.info("Checking for manually uploaded credit card CSVs")
        query = (
            select(Document.document_metadata)
            .where(
                and_(
                    Document.search_space_id == search_space_id,
                    Document.document_metadata.op("->>")("is_financial_document") == "true"
                )
            )
        )
        result = await db_session.execute(query)
        financial_docs = result.scalars().all()
        
        for doc_metadata in financial_docs:
            # Parse JSON if it's a string
            if isinstance(doc_metadata, str):
                try:
                    doc_metadata = json.loads(doc_metadata)
                except json.JSONDecodeError:
                    continue
            
            institution = doc_metadata.get("institution", "")
            if "credit card" in institution.lower():
                # Extract card name from institution
                cards.append({
                    "name": institution,
                    "account_id": institution,
                    "user_id": "",
                    "source": "manual_upload"
                })
                logger.info(f"Found manual upload credit card: {institution}")
        
        # Then search for Plaid account summaries
        logger.info("Searching for Plaid credit card accounts")
        user_query = "credit card account balance"
        _, results = await connector_service.search_files(
            user_query=user_query,
            search_space_id=search_space_id,
            top_k=10,
        )

        if not results and not cards:
            return []

        # Extract credit card accounts from Plaid results
        account_pattern = r"##\s+(.+?)\s*\n.*?-\s+\*\*Type:\*\*\s+credit"

        for doc in results:
            content = doc.get("content", "")

            # Find all credit card accounts in this document
            matches = re.finditer(account_pattern, content, re.IGNORECASE | re.DOTALL)

            for match in matches:
                account_name = match.group(1).strip()

                # Extract account ID if present (usually in parentheses or after dash)
                account_id_match = re.search(
                    r"\((.*?)\)|ending in (\d+)", account_name, re.IGNORECASE
                )
                account_id = (
                    account_id_match.group(1) or account_id_match.group(2)
                    if account_id_match
                    else account_name
                )

                cards.append(
                    {
                        "name": account_name,
                        "account_id": account_id,
                        "user_id": doc.get("user_id", ""),
                        "source": "plaid"
                    }
                )

        # Deduplicate by account_id
        seen = set()
        unique_cards = []
        for card in cards:
            if card["account_id"] not in seen:
                seen.add(card["account_id"])
                unique_cards.append(card)

        return unique_cards

    except Exception as e:
        logger.error(f"Error extracting credit cards: {e}")
        return []


async def _get_user_transactions(
    db_session: AsyncSession,
    search_space_id: int,
    days_back: int,
) -> list[dict[str, Any]]:
    """
    Extract user's recent credit card transactions from both manual uploads and Plaid.

    Args:
        db_session: Database session for direct queries
        search_space_id: User's search space ID
        days_back: Number of days to look back

    Returns:
        List of transaction dictionaries
    """
    try:
        # Calculate cutoff date
        cutoff_date = (datetime.now(UTC) - timedelta(days=days_back)).date()
        
        # Get all financial documents (both manual uploads and Plaid)
        query = (
            select(Document.document_metadata, Document.content, Document.document_metadata.op("->>")("is_plaid_document"))
            .where(
                and_(
                    Document.search_space_id == search_space_id,
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
            return []
        
        transactions = []
        
        for doc_metadata, doc_content, is_plaid in documents:
            doc_transactions = []
            
            # Handle Plaid documents (parse markdown)
            if is_plaid == "true" and doc_content:
                doc_transactions = _parse_plaid_markdown_transactions(doc_content)
            else:
                # Handle manual upload documents (JSON metadata)
                if isinstance(doc_metadata, str):
                    try:
                        doc_metadata = json.loads(doc_metadata)
                    except json.JSONDecodeError:
                        continue
                
                financial_data = doc_metadata.get("financial_data", {})
                
                if isinstance(financial_data, str):
                    try:
                        financial_data = json.loads(financial_data)
                    except json.JSONDecodeError:
                        continue
                
                doc_transactions = financial_data.get("transactions", [])
            
            # Filter by date and add to results
            for txn in doc_transactions:
                txn_date_str = txn.get("date", "")
                if not txn_date_str:
                    continue
                    
                try:
                    txn_date = datetime.fromisoformat(txn_date_str.replace("Z", "+00:00")).date()
                    
                    # Only include transactions within the lookback period
                    if txn_date < cutoff_date:
                        continue
                        
                except (ValueError, AttributeError):
                    continue
                
                # Get amount (only include expenses)
                amount = float(txn.get("amount", 0))
                if amount >= 0:  # Skip deposits/credits
                    continue
                
                transactions.append({
                    "date": txn_date_str.split("T")[0],
                    "merchant": txn.get("merchant") or txn.get("description", "Unknown"),
                    "amount": abs(amount),  # Convert to positive for spending
                    "category": txn.get("category", "Other"),
                })
        
        logger.info(f"Extracted {len(transactions)} credit card transactions")
        return transactions

    except Exception as e:
        logger.error(f"Error extracting transactions: {e}", exc_info=True)
        return []


def _parse_plaid_markdown_transactions(content: str) -> list[dict[str, Any]]:
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
            "merchant": description,
            "amount": amount,
            "category": None,
            "transaction_type": txn_type,
        })
    
    return transactions


async def _analyze_card_optimization(
    transactions: list[dict[str, Any]],
    cards_with_rewards: list[dict[str, Any]],
    days_back: int,
) -> dict[str, Any]:
    """
    Analyze transactions and identify optimization opportunities.

    Args:
        transactions: List of transaction dictionaries
        cards_with_rewards: List of credit cards with rewards structures
        days_back: Number of days analyzed

    Returns:
        Optimization analysis dictionary
    """
    # Group transactions by category
    category_spending = {}
    category_transactions = {}

    for txn in transactions:
        category = _map_plaid_category_to_rewards_category(txn["category"])

        if category not in category_spending:
            category_spending[category] = 0.0
            category_transactions[category] = []

        category_spending[category] += txn["amount"]
        category_transactions[category].append(txn)

    # Find optimal card for each category
    recommendations = []
    total_missed_rewards = 0.0

    for category, spend_amount in category_spending.items():
        # Find best card for this category
        best_card = None
        best_rate = 0.0

        for card in cards_with_rewards:
            rewards = card["rewards"]
            # Check if card has specific category rate, otherwise use default
            rate = rewards.get(category, rewards.get("default", 1.0))

            if rate > best_rate:
                best_rate = rate
                best_card = card

        if best_card and spend_amount > 0:
            # Calculate what user likely earned (assuming average 1% across all cards)
            # This is a simplification - in production, track which card was actually used
            current_rate = 1.0  # Conservative assumption
            current_rewards = spend_amount * (current_rate / 100)
            optimal_rewards = spend_amount * (best_rate / 100)
            missed_rewards = optimal_rewards - current_rewards

            if missed_rewards > 0.01:  # Only recommend if saves >1 cent
                total_missed_rewards += missed_rewards

                recommendations.append(
                    {
                        "category": category,
                        "optimal_card": best_card["name"],
                        "optimal_rate": best_rate,
                        "spend_amount": round(spend_amount, 2),
                        "potential_rewards": round(optimal_rewards, 2),
                        "missed_rewards": round(missed_rewards, 2),
                        "transaction_count": len(category_transactions[category]),
                    }
                )

    # Sort recommendations by missed rewards (highest first)
    recommendations.sort(key=lambda x: x["missed_rewards"], reverse=True)

    # Calculate potential annual savings
    multiplier = 365 / days_back
    annual_savings = total_missed_rewards * multiplier

    # Generate summary
    if total_missed_rewards > 0:
        period_name = {"7": "this week", "30": "this month", "90": "this quarter"}.get(
            str(days_back), f"the last {days_back} days"
        )

        summary = f"You could have earned ${total_missed_rewards:.2f} more in rewards {period_name} by using optimal cards. "
        summary += f"Estimated annual savings: ${annual_savings:.2f}"

        # Add top recommendation
        if recommendations:
            top_rec = recommendations[0]
            summary += f"\n\nTop opportunity: Use {top_rec['optimal_card']} for {top_rec['category']} "
            summary += f"({top_rec['optimal_rate']}% rewards vs current ~1%)"
    else:
        summary = f"Great job! You're already maximizing your credit card rewards for the transactions analyzed."

    return {
        "summary": summary,
        "missed_rewards": round(total_missed_rewards, 2),
        "potential_annual_savings": round(annual_savings, 2),
        "recommendations": recommendations[:10],  # Top 10 recommendations
        "period_analyzed": f"last {days_back} days",
        "total_transactions": len(transactions),
        "total_spend": round(sum(t["amount"] for t in transactions), 2),
        "cards_analyzed": len(cards_with_rewards),
    }


def _map_plaid_category_to_rewards_category(plaid_category: str) -> str:
    """
    Map Plaid transaction category to credit card rewards category.

    Args:
        plaid_category: Plaid's category string (e.g., "Food and Drink, Restaurants")

    Returns:
        Rewards category name (e.g., "dining")
    """
    plaid_lower = plaid_category.lower()

    # Mapping based on common credit card rewards categories
    category_map = {
        "dining": ["restaurant", "food and drink", "bar", "coffee", "dining"],
        "travel": ["travel", "airline", "hotel", "rental car", "taxi", "uber", "lyft"],
        "groceries": ["grocery", "supermarket", "food", "trader joe"],
        "gas": ["gas", "fuel", "gas station", "shell", "chevron", "exxon"],
        "streaming": ["streaming", "netflix", "spotify", "hulu", "disney"],
        "online_shopping": ["amazon", "online", "e-commerce"],
        "drugstore": ["pharmacy", "drugstore", "cvs", "walgreens"],
    }

    for rewards_category, keywords in category_map.items():
        if any(keyword in plaid_lower for keyword in keywords):
            return rewards_category

    # Default category
    return "default"


async def _get_llm_service(session: AsyncSession, search_space_id: int):
    """Get LLM service for the user/search space."""
    from app.services.llm_service import get_document_summary_llm

    llm = await get_document_summary_llm(session, search_space_id)
    return llm
