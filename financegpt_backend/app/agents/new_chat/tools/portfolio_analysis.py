"""
Portfolio analysis and advisory tool for FinanceGPT.

This tool provides comprehensive portfolio analysis including:
- Asset allocation analysis (stocks, bonds, cash, etc.)
- Geographic exposure (domestic vs international)
- Sector diversification
- Comparison to investment philosophies (Bogleheads, etc.)
- Rebalancing recommendations
"""

import logging
import re
from typing import Any

import aiohttp
from langchain_core.tools import tool
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document
from app.services.connector_service import ConnectorService

logger = logging.getLogger(__name__)


# Asset class mappings for common tickers
ASSET_CLASS_MAP = {
    # US Broad Market ETFs
    "VOO": {"type": "equity", "region": "us", "category": "large_cap", "name": "Vanguard S&P 500 ETF"},
    "VTI": {"type": "equity", "region": "us", "category": "total_market", "name": "Vanguard Total Stock Market ETF"},
    "SPY": {"type": "equity", "region": "us", "category": "large_cap", "name": "SPDR S&P 500 ETF"},
    "IVV": {"type": "equity", "region": "us", "category": "large_cap", "name": "iShares Core S&P 500 ETF"},
    "QQQ": {"type": "equity", "region": "us", "category": "large_cap_growth", "name": "Invesco QQQ ETF"},
    
    # International ETFs
    "VXUS": {"type": "equity", "region": "international", "category": "total_international", "name": "Vanguard Total International Stock ETF"},
    "VEA": {"type": "equity", "region": "international", "category": "developed", "name": "Vanguard Developed Markets ETF"},
    "VWO": {"type": "equity", "region": "international", "category": "emerging", "name": "Vanguard Emerging Markets ETF"},
    "EFA": {"type": "equity", "region": "international", "category": "developed", "name": "iShares MSCI EAFE ETF"},
    
    # Bond ETFs
    "BND": {"type": "bond", "region": "us", "category": "total_bond", "name": "Vanguard Total Bond Market ETF"},
    "AGG": {"type": "bond", "region": "us", "category": "total_bond", "name": "iShares Core U.S. Aggregate Bond ETF"},
    "TLT": {"type": "bond", "region": "us", "category": "long_term_treasury", "name": "iShares 20+ Year Treasury Bond ETF"},
    "BNDX": {"type": "bond", "region": "international", "category": "international_bond", "name": "Vanguard Total International Bond ETF"},
    
    # Fidelity Funds
    "FXNAX": {"type": "bond", "region": "us", "category": "money_market", "name": "Fidelity U.S. Bond Index Fund"},
    "FCASH": {"type": "cash", "region": "us", "category": "cash", "name": "Fidelity Cash Reserves"},
    
    # Individual Stocks (examples - stocks are generally equity/us)
    "MSFT": {"type": "equity", "region": "us", "category": "large_cap_tech", "name": "Microsoft Corporation"},
    "AAPL": {"type": "equity", "region": "us", "category": "large_cap_tech", "name": "Apple Inc."},
    "GOOGL": {"type": "equity", "region": "us", "category": "large_cap_tech", "name": "Alphabet Inc."},
    "AMZN": {"type": "equity", "region": "us", "category": "large_cap_tech", "name": "Amazon.com Inc."},
}


# Investment philosophy templates
INVESTMENT_PHILOSOPHIES = {
    "bogleheads_conservative": {
        "name": "Bogleheads Conservative (Age 50+)",
        "description": "Conservative allocation focused on capital preservation with moderate growth",
        "allocation": {
            "equity": 0.40,  # 40% stocks
            "bond": 0.50,    # 50% bonds
            "cash": 0.10,    # 10% cash
        },
        "equity_breakdown": {
            "us": 0.70,           # 70% US
            "international": 0.30, # 30% international
        },
    },
    "bogleheads_moderate": {
        "name": "Bogleheads Moderate (Age 30-50)",
        "description": "Balanced allocation for moderate risk tolerance and long-term growth",
        "allocation": {
            "equity": 0.60,  # 60% stocks
            "bond": 0.35,    # 35% bonds
            "cash": 0.05,    # 5% cash
        },
        "equity_breakdown": {
            "us": 0.70,
            "international": 0.30,
        },
    },
    "bogleheads_aggressive": {
        "name": "Bogleheads Aggressive (Age < 30)",
        "description": "Growth-focused allocation for long time horizons",
        "allocation": {
            "equity": 0.90,  # 90% stocks
            "bond": 0.10,    # 10% bonds
            "cash": 0.00,
        },
        "equity_breakdown": {
            "us": 0.70,
            "international": 0.30,
        },
    },
    "three_fund_portfolio": {
        "name": "Bogleheads Three-Fund Portfolio",
        "description": "Classic three-fund portfolio: US stocks, international stocks, bonds",
        "allocation": {
            "equity": 0.80,  # 80% stocks
            "bond": 0.20,    # 20% bonds
            "cash": 0.00,
        },
        "equity_breakdown": {
            "us": 0.67,           # 2/3 US
            "international": 0.33, # 1/3 international
        },
    },
}


async def _get_latest_holdings(
    session: AsyncSession,
    search_space_id: int,
) -> list[dict[str, Any]]:
    """Get current holdings from the database."""
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
        .order_by(Document.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        return []
    
    # Extract holdings from markdown
    return _extract_holdings_from_content(doc.content)


def _extract_holdings_from_content(content: str) -> list[dict[str, Any]]:
    """Extract holdings from markdown content."""
    holdings = []
    
    # Pattern: - **TICKER**: quantity shares @ $value | Cost Basis: $X | Gain/Loss: $Y
    pattern = r"- \*\*([A-Z0-9]+)\*\*(?:\*)?:\s*([\d.]+)\s+shares?\s+@\s+\$([\d,.]+)"
    matches = re.finditer(pattern, content, re.MULTILINE)
    
    for match in matches:
        ticker = match.group(1).strip()
        quantity = float(match.group(2).replace(",", ""))
        value = float(match.group(3).replace(",", ""))
        
        holdings.append({
            "ticker": ticker,
            "quantity": quantity,
            "value": value,
        })
    
    return holdings


def _classify_holding(ticker: str) -> dict[str, str]:
    """Classify a holding by ticker symbol."""
    # Check known mappings first
    if ticker in ASSET_CLASS_MAP:
        return ASSET_CLASS_MAP[ticker]
    
    # Default classification for unknown stocks
    # Most individual stocks are US equities
    return {
        "type": "equity",
        "region": "us",
        "category": "individual_stock",
        "name": ticker,
    }


def _calculate_allocation(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate current portfolio allocation."""
    total_value = sum(h["value"] for h in holdings)
    
    if total_value == 0:
        return {
            "total_value": 0,
            "by_asset_class": {},
            "by_region": {},
            "holdings_detail": [],
        }
    
    allocation_by_type = {}
    allocation_by_region = {}
    holdings_detail = []
    
    for holding in holdings:
        ticker = holding["ticker"]
        value = holding["value"]
        classification = _classify_holding(ticker)
        
        asset_type = classification["type"]
        region = classification["region"]
        pct_of_portfolio = (value / total_value) * 100
        
        # Aggregate by asset class
        if asset_type not in allocation_by_type:
            allocation_by_type[asset_type] = {"value": 0, "percentage": 0}
        allocation_by_type[asset_type]["value"] += value
        allocation_by_type[asset_type]["percentage"] += pct_of_portfolio
        
        # Aggregate by region
        if region not in allocation_by_region:
            allocation_by_region[region] = {"value": 0, "percentage": 0}
        allocation_by_region[region]["value"] += value
        allocation_by_region[region]["percentage"] += pct_of_portfolio
        
        holdings_detail.append({
            "ticker": ticker,
            "name": classification["name"],
            "value": value,
            "percentage": pct_of_portfolio,
            "type": asset_type,
            "region": region,
            "category": classification["category"],
        })
    
    return {
        "total_value": total_value,
        "by_asset_class": allocation_by_type,
        "by_region": allocation_by_region,
        "holdings_detail": holdings_detail,
    }


def _compare_to_philosophy(
    current_allocation: dict[str, Any],
    philosophy: dict[str, Any],
) -> dict[str, Any]:
    """Compare current allocation to a target philosophy."""
    total_value = current_allocation["total_value"]
    by_type = current_allocation["by_asset_class"]
    
    # Calculate current percentages
    current_equity_pct = by_type.get("equity", {}).get("percentage", 0) / 100
    current_bond_pct = by_type.get("bond", {}).get("percentage", 0) / 100
    current_cash_pct = by_type.get("cash", {}).get("percentage", 0) / 100
    
    # Get target percentages
    target = philosophy["allocation"]
    target_equity = target.get("equity", 0)
    target_bond = target.get("bond", 0)
    target_cash = target.get("cash", 0)
    
    # Calculate differences
    equity_diff = current_equity_pct - target_equity
    bond_diff = current_bond_pct - target_bond
    cash_diff = current_cash_pct - target_cash
    
    # Generate recommendations
    recommendations = []
    
    if abs(equity_diff) > 0.05:  # More than 5% off target
        if equity_diff > 0:
            recommendations.append({
                "action": "reduce",
                "asset_class": "equity",
                "current": f"{current_equity_pct*100:.1f}%",
                "target": f"{target_equity*100:.1f}%",
                "amount": f"${abs(equity_diff * total_value):,.2f}",
                "message": f"Reduce equities by ${abs(equity_diff * total_value):,.2f} ({abs(equity_diff)*100:.1f}% of portfolio)",
            })
        else:
            recommendations.append({
                "action": "increase",
                "asset_class": "equity",
                "current": f"{current_equity_pct*100:.1f}%",
                "target": f"{target_equity*100:.1f}%",
                "amount": f"${abs(equity_diff * total_value):,.2f}",
                "message": f"Increase equities by ${abs(equity_diff * total_value):,.2f} ({abs(equity_diff)*100:.1f}% of portfolio)",
            })
    
    if abs(bond_diff) > 0.05:
        if bond_diff > 0:
            recommendations.append({
                "action": "reduce",
                "asset_class": "bond",
                "current": f"{current_bond_pct*100:.1f}%",
                "target": f"{target_bond*100:.1f}%",
                "amount": f"${abs(bond_diff * total_value):,.2f}",
                "message": f"Reduce bonds by ${abs(bond_diff * total_value):,.2f} ({abs(bond_diff)*100:.1f}% of portfolio)",
            })
        else:
            recommendations.append({
                "action": "increase",
                "asset_class": "bond",
                "current": f"{current_bond_pct*100:.1f}%",
                "target": f"{target_bond*100:.1f}%",
                "amount": f"${abs(bond_diff * total_value):,.2f}",
                "message": f"Increase bonds by ${abs(bond_diff * total_value):,.2f} ({abs(bond_diff)*100:.1f}% of portfolio)",
            })
    
    # Analyze equity geographic distribution if applicable
    equity_recs = []
    if current_equity_pct > 0.10:  # If portfolio has meaningful equity exposure
        by_region = current_allocation["by_region"]
        us_value = by_region.get("us", {}).get("value", 0)
        intl_value = by_region.get("international", {}).get("value", 0)
        total_equity_value = by_type.get("equity", {}).get("value", 1)
        
        current_us_pct = us_value / total_equity_value if total_equity_value > 0 else 0
        current_intl_pct = intl_value / total_equity_value if total_equity_value > 0 else 0
        
        target_us = philosophy["equity_breakdown"].get("us", 0.70)
        target_intl = philosophy["equity_breakdown"].get("international", 0.30)
        
        us_equity_diff = current_us_pct - target_us
        intl_equity_diff = current_intl_pct - target_intl
        
        if abs(us_equity_diff) > 0.10:  # More than 10% off target
            if us_equity_diff > 0:
                equity_recs.append(
                    f"Your US equity allocation ({current_us_pct*100:.1f}%) is higher than recommended ({target_us*100:.1f}%). "
                    f"Consider shifting ${abs(us_equity_diff * total_equity_value):,.2f} to international stocks."
                )
            else:
                equity_recs.append(
                    f"Your US equity allocation ({current_us_pct*100:.1f}%) is lower than recommended ({target_us*100:.1f}%). "
                    f"Consider shifting ${abs(us_equity_diff * total_equity_value):,.2f} from international to US stocks."
                )
    
    return {
        "philosophy_name": philosophy["name"],
        "description": philosophy["description"],
        "target_allocation": {
            "equity": f"{target_equity*100:.0f}%",
            "bond": f"{target_bond*100:.0f}%",
            "cash": f"{target_cash*100:.0f}%",
        },
        "current_allocation": {
            "equity": f"{current_equity_pct*100:.1f}%",
            "bond": f"{current_bond_pct*100:.1f}%",
            "cash": f"{current_cash_pct*100:.1f}%",
        },
        "differences": {
            "equity": f"{equity_diff*100:+.1f}%",
            "bond": f"{bond_diff*100:+.1f}%",
            "cash": f"{cash_diff*100:+.1f}%",
        },
        "recommendations": recommendations,
        "equity_geographic_recommendations": equity_recs,
        "alignment_score": max(0, 100 - (abs(equity_diff) + abs(bond_diff) + abs(cash_diff)) * 100),
    }


def create_portfolio_analysis_tool(
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
):
    """
    Create a portfolio analysis and advisory tool.

    Args:
        search_space_id: The user's search space ID
        db_session: Database session for queries
        connector_service: Service for searching knowledge base

    Returns:
        Langchain tool for analyzing portfolio allocation
    """

    @tool
    async def analyze_portfolio_allocation(
        philosophy: str = "bogleheads_moderate",
    ) -> dict[str, Any]:
        """Analyze your investment portfolio allocation and get rebalancing advice.

        This tool examines your current holdings and provides detailed analysis including:
        - Asset allocation breakdown (stocks, bonds, cash)
        - Geographic diversification (US vs international)
        - Comparison to established investment philosophies
        - Specific rebalancing recommendations

        Args:
            philosophy: Investment philosophy to compare against. Options:
                - "bogleheads_conservative": Conservative allocation for capital preservation (Age 50+)
                - "bogleheads_moderate": Balanced allocation for moderate risk (Age 30-50, DEFAULT)
                - "bogleheads_aggressive": Growth-focused allocation (Age < 30)
                - "three_fund_portfolio": Classic Bogleheads three-fund approach
                - "current": Just show current allocation without comparison

        Returns:
            A dictionary containing:
            - summary: Overall portfolio allocation summary
            - current_allocation: Breakdown by asset class and region
            - holdings_detail: Details of each holding
            - comparison: Comparison to selected philosophy (if not "current")
            - recommendations: Specific actions to rebalance portfolio
            - alignment_score: How well aligned you are with the target (0-100)

        Example:
            User: "Is my portfolio allocation correct?"
            User: "How should I rebalance my portfolio?"
            User: "What's my exposure to international stocks?"
        """
        try:
            # Get current holdings
            holdings = await _get_latest_holdings(db_session, search_space_id)
            
            if not holdings:
                return {
                    "summary": "No investment holdings found in your accounts.",
                    "note": "Please connect your investment accounts or upload portfolio data to analyze allocation.",
                }
            
            # Calculate current allocation
            allocation = _calculate_allocation(holdings)
            
            # Format current allocation summary
            by_type = allocation["by_asset_class"]
            by_region = allocation["by_region"]
            
            allocation_summary = f"Portfolio Value: ${allocation['total_value']:,.2f}\n\n"
            allocation_summary += "Asset Allocation:\n"
            for asset_class, data in by_type.items():
                allocation_summary += f"  • {asset_class.title()}: ${data['value']:,.2f} ({data['percentage']:.1f}%)\n"
            
            allocation_summary += "\nGeographic Allocation:\n"
            for region, data in by_region.items():
                allocation_summary += f"  • {region.upper()}: ${data['value']:,.2f} ({data['percentage']:.1f}%)\n"
            
            # If only current allocation requested, return without comparison
            if philosophy.lower() == "current":
                return {
                    "summary": allocation_summary,
                    "total_value": allocation["total_value"],
                    "current_allocation": allocation,
                    "holdings": allocation["holdings_detail"],
                }
            
            # Get selected philosophy
            selected_philosophy = INVESTMENT_PHILOSOPHIES.get(
                philosophy, INVESTMENT_PHILOSOPHIES["bogleheads_moderate"]
            )
            
            # Compare to philosophy
            comparison = _compare_to_philosophy(allocation, selected_philosophy)
            
            # Build comprehensive summary
            summary = allocation_summary + "\n"
            summary += f"\nCompared to: {comparison['philosophy_name']}\n"
            summary += f"{comparison['description']}\n\n"
            
            summary += "Alignment Score: {:.0f}/100\n\n".format(comparison["alignment_score"])
            
            if comparison["recommendations"]:
                summary += "Rebalancing Recommendations:\n"
                for rec in comparison["recommendations"]:
                    summary += f"  • {rec['message']}\n"
            else:
                summary += "✓ Your portfolio is well-aligned with this philosophy.\n"
            
            if comparison["equity_geographic_recommendations"]:
                summary += "\nGeographic Diversification:\n"
                for rec in comparison["equity_geographic_recommendations"]:
                    summary += f"  • {rec}\n"
            
            return {
                "summary": summary,
                "total_value": allocation["total_value"],
                "current_allocation": allocation,
                "comparison": comparison,
                "holdings": allocation["holdings_detail"],
                "philosophy": selected_philosophy,
            }
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio allocation: {e}", exc_info=True)
            return {
                "summary": f"Error analyzing portfolio: {str(e)}",
                "error": str(e),
            }

    return analyze_portfolio_allocation
