"""Portfolio performance tool using structured investment holdings data."""
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession


def create_check_portfolio_performance_tool(user_id: str, db_session: AsyncSession):
    """
    Factory function to create the portfolio performance tool.
    
    This checks today's stock performance from uploaded investment holdings.
    """
    
    @tool
    async def check_portfolio_performance() -> dict:
        """
        Get today's portfolio performance including top gainers and losers.
        Returns real-time price changes, gains/losses for all stock holdings.
        
        Use for questions like:
        - "How are my stocks performing today?"
        - "What are my top gainers and losers?"
        - "Show me today's performance"
        
        Returns:
            Dict with total portfolio value, day change, top gainers/losers
        """
        from app.agents.tools.investment_tools import check_portfolio_performance as _check_perf
        return await _check_perf.ainvoke({"user_id": str(user_id)})
    
    return check_portfolio_performance


def create_analyze_portfolio_allocation_tool(user_id: str, db_session: AsyncSession):
    """
    Factory function to create the portfolio allocation analysis tool.
    
    Analyzes allocation across asset classes, sectors, and compares to targets.
    """
    
    @tool
    async def analyze_portfolio_allocation() -> dict:
        """
        Analyze portfolio allocation across asset classes, sectors, and regions.
        Compares current allocation to user's targets and suggests rebalancing.
        
        Use for questions like:
        - "How is my portfolio allocated?"
        - "Show me my asset allocation"
        - "Do I need to rebalance?"
        - "What's my sector breakdown?"
        
        Returns:
            Dict with allocation breakdowns and rebalancing suggestions
        """
        from app.agents.tools.investment_tools import analyze_portfolio_allocation as _analyze
        return await _analyze.ainvoke({"user_id": str(user_id)})
    
    return analyze_portfolio_allocation


def create_find_tax_loss_harvesting_tool(user_id: str, db_session: AsyncSession):
    """
    Factory function to create the tax loss harvesting tool.
    
    Identifies opportunities to harvest losses in taxable accounts.
    """
    
    @tool
    async def find_tax_loss_harvesting_opportunities() -> dict:
        """
        Identify tax loss harvesting opportunities in taxable accounts.
        Returns holdings with unrealized losses that qualify for tax harvesting.
        Checks for wash sale risks (purchases in last 30 days).
        
        Use for questions like:
        - "Are there any tax loss harvesting opportunities?"
        - "Can I save on taxes?"
        - "Show me my losses for tax purposes"
        
        Returns:
            Dict with harvesting opportunities and potential tax savings
        """
        from app.agents.tools.investment_tools import find_tax_loss_harvesting_opportunities as _find_tlh
        return await _find_tlh.ainvoke({"user_id": str(user_id)})
    
    return find_tax_loss_harvesting_opportunities
