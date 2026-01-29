"""Specialized tools for portfolio analysis and investment queries."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.schemas.investments import (
    AllocationBreakdown,
    HoldingPerformance,
    PortfolioAllocationResponse,
    PortfolioPerformanceResponse,
    TaxHarvestingOpportunity,
    TaxHarvestingResponse,
)


@tool
async def check_portfolio_performance(user_id: str) -> dict[str, Any]:
    """
    Get portfolio holdings and performance data.
    Returns holdings with cost basis so the agent can search for current prices.
    
    IMPORTANT: After calling this tool, search for current stock prices for each symbol
    and calculate the current market values and gains/losses.
    
    Use for questions like:
    - "How are my stocks performing today?"
    - "What are my top gainers and losers?"
    - "Show me my portfolio value"
    
    Args:
        user_id: UUID of the user
        
    Returns:
        Dict with holdings data - agent should enrich with current prices via search
    """
    from app.db import InvestmentHolding, InvestmentAccount
    
    user_uuid = UUID(user_id)
    
    async for session in get_async_session():
        # Query holdings (basic data only)
        query = (
            select(InvestmentHolding)
            .join(InvestmentAccount)
            .where(InvestmentAccount.user_id == user_uuid)
        )
        
        result = await session.execute(query)
        holdings = result.scalars().all()
        
        if not holdings:
            return {
                "error": "No holdings found. Please upload your portfolio first."
            }
        
        # Return holdings data for agent to enrich with current prices
        holdings_data = [
            {
                "symbol": h.symbol,
                "description": h.description or h.symbol,
                "quantity": float(h.quantity or 0),
                "cost_basis": float(h.cost_basis or 0),
                "average_cost_basis": float(h.average_cost_basis or 0),
            }
            for h in holdings
        ]
        
        total_cost_basis = sum(h["cost_basis"] for h in holdings_data)
        
        return {
            "holdings": holdings_data,
            "total_cost_basis": total_cost_basis,
            "instruction": f"Search for current stock prices for these symbols: {', '.join(h['symbol'] for h in holdings_data)}. Then calculate market value (price * quantity) and gains/losses for each holding.",
        }


@tool
async def analyze_portfolio_allocation(user_id: str) -> dict[str, Any]:
    """
    Analyze portfolio allocation across asset classes, sectors, and regions.
    Compares current allocation to user's targets and suggests rebalancing.
    
    Use for questions like:
    - "How is my portfolio allocated?"
    - "Show me my asset allocation"
    - "Do I need to rebalance?"
    - "What's my sector breakdown?"
    
    Args:
        user_id: UUID of the user
        
    Returns:
        Dict with allocation breakdowns and rebalancing suggestions
    """
    from app.db import InvestmentHolding, InvestmentAccount, PortfolioAllocationTarget
    
    user_uuid = UUID(user_id)
    
    async for session in get_async_session():
        # Get all holdings
        query = (
            select(InvestmentHolding)
            .join(InvestmentAccount)
            .where(InvestmentAccount.user_id == user_uuid)
        )
        result = await session.execute(query)
        holdings = result.scalars().all()
        
        if not holdings:
            return {"error": "No holdings with market value found"}
        
        # Calculate total value
        total_value = sum(float(h.market_value or 0) for h in holdings)
        
        if total_value == 0:
            return {"error": "No holdings with market value found"}
        
        # Group by asset type
        asset_groups = {}
        for h in holdings:
            asset_type = h.asset_type or "Unknown"
            if asset_type not in asset_groups:
                asset_groups[asset_type] = 0.0
            asset_groups[asset_type] += float(h.market_value or 0)
        
        by_asset_type = [
            AllocationBreakdown(
                category=asset_type,
                value=value,
                percentage=value / total_value * 100,
            )
            for asset_type, value in sorted(asset_groups.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Group by sector
        sector_groups = {}
        for h in holdings:
            if h.sector:
                sector = h.sector
                if sector not in sector_groups:
                    sector_groups[sector] = 0.0
                sector_groups[sector] += float(h.market_value or 0)
        
        by_sector = [
            AllocationBreakdown(
                category=sector,
                value=value,
                percentage=value / total_value * 100,
            )
            for sector, value in sorted(sector_groups.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Get user's target allocation
        targets_query = select(PortfolioAllocationTarget).where(
            PortfolioAllocationTarget.user_id == user_uuid
        )
        targets_result = await session.execute(targets_query)
        targets = targets_result.scalar_one_or_none()
        
        # Check if rebalancing needed (> 5% variance from targets)
        rebalancing_needed = False
        suggestions = []
        
        if targets:
            for alloc in by_asset_type:
                if alloc.category.lower() == "stock":
                    target_stocks_pct = float(targets.target_stocks_pct or 0)
                    variance = alloc.percentage - target_stocks_pct
                    alloc.target_percentage = target_stocks_pct
                    alloc.variance = variance
                    if abs(variance) > 5:
                        rebalancing_needed = True
                        action = "Sell" if variance > 0 else "Buy"
                        suggestions.append(f"{action} stocks by ~{abs(variance):.1f}%")
        
        response = PortfolioAllocationResponse(
            total_value=total_value,
            by_asset_type=by_asset_type,
            by_sector=by_sector,
            rebalancing_needed=rebalancing_needed,
            rebalancing_suggestions=suggestions if suggestions else None,
        )
        
        return response.model_dump()


@tool
async def find_tax_loss_harvesting_opportunities(user_id: str) -> dict[str, Any]:
    """
    Identify tax loss harvesting opportunities in taxable accounts.
    Returns holdings with unrealized losses that qualify for tax harvesting.
    Checks for wash sale risks (purchases in last 30 days).
    
    Use for questions like:
    - "Are there any tax loss harvesting opportunities?"
    - "Can I save on taxes?"
    - "Show me my losses for tax purposes"
    
    Args:
        user_id: UUID of the user
        
    Returns:
        Dict with harvesting opportunities and potential tax savings
    """
    from app.db import InvestmentHolding, InvestmentAccount, InvestmentTransaction
    
    user_uuid = UUID(user_id)
    
    async for session in get_async_session():
        # Query holdings in taxable accounts with losses
        holdings_query = (
            select(InvestmentHolding)
            .join(InvestmentAccount)
            .where(InvestmentAccount.user_id == user_uuid)
            .where(InvestmentAccount.account_tax_type == "taxable")
        )
        
        result = await session.execute(holdings_query)
        all_holdings = result.scalars().all()
        
        # Filter holdings with meaningful losses
        holdings_with_losses = [h for h in all_holdings if float(h.unrealized_gain_loss or 0) < -1000]
        
        if not holdings_with_losses:
            return {
                "opportunities": [],
                "total_potential_loss": 0,
                "total_potential_tax_savings": 0,
                "warnings": ["No significant losses found in taxable accounts."]
            }
        
        opportunities = []
        total_potential_loss = 0.0
        warnings = []
        
        for holding in holdings_with_losses:
            # Check for wash sale risk (buys in last 30 days)
            wash_sale_query = (
                select(func.count())
                .select_from(InvestmentTransaction)
                .where(InvestmentTransaction.symbol == holding.symbol)
                .where(InvestmentTransaction.transaction_type == "buy")
                .where(InvestmentTransaction.transaction_date > (date.today() - timedelta(days=30)))
            )
            wash_result = await session.execute(wash_sale_query)
            has_recent_buys = wash_result.scalar() > 0
            
            # Calculate holding period (days since acquisition)
            holding_period_days = 0
            if holding.acquisition_date:
                holding_period_days = (date.today() - holding.acquisition_date.date()).days
            
            is_long_term = holding_period_days > 365
            
            # Estimate tax savings (15% or 20% for long-term, up to 37% for short-term)
            tax_rate = 0.15 if is_long_term else 0.25
            unrealized_loss = abs(float(holding.unrealized_gain_loss or 0))
            potential_tax_savings = unrealized_loss * tax_rate
            
            opportunity = TaxHarvestingOpportunity(
                symbol=holding.symbol,
                quantity=float(holding.quantity or 0),
                cost_basis=float(holding.cost_basis or 0),
                current_value=float(holding.market_value or 0),
                unrealized_loss=-unrealized_loss,
                holding_period_days=holding_period_days,
                is_long_term=is_long_term,
                potential_tax_savings=potential_tax_savings,
                wash_sale_risk=has_recent_buys,
            )
            
            opportunities.append(opportunity)
            total_potential_loss += unrealized_loss
            
            if has_recent_buys:
                warnings.append(f"⚠️ {holding.symbol}: Wash sale risk - purchased in last 30 days")
        
        # Calculate total tax savings
        total_tax_savings = sum(opp.potential_tax_savings for opp in opportunities)
        
        response = TaxHarvestingResponse(
            opportunities=opportunities,
            total_potential_loss=total_potential_loss,
            total_potential_tax_savings=total_tax_savings,
            warnings=warnings if warnings else ["All opportunities look good!"],
        )
        
        return response.model_dump()


# Export tools for agent
INVESTMENT_TOOLS = [
    check_portfolio_performance,
    analyze_portfolio_allocation,
    find_tax_loss_harvesting_opportunities,
]
