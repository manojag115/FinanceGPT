"""
Investment holdings API routes.

Handles uploading CSV files, managing investment accounts and holdings,
and retrieving portfolio data.
"""

from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.users import get_current_user_id
from app.schemas.investments import (
    InvestmentAccountCreate,
    InvestmentAccountResponse,
    InvestmentHoldingResponse,
)
from app.services.yahoo_finance_enrichment import YahooFinanceEnrichmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/investments", tags=["investments"])


@router.post("/accounts", response_model=InvestmentAccountResponse)
async def create_investment_account(
    account: InvestmentAccountCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Create a new investment account.
    
    Args:
        account: Account details including name, type, tax treatment
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        Created investment account
    """
    from app.db import InvestmentAccount
    
    # Create account
    db_account = InvestmentAccount(
        user_id=user_id,
        account_number=account.account_number,
        account_name=account.account_name,
        account_type=account.account_type,
        account_tax_type=account.account_tax_type,
        institution=account.institution,
        total_value=account.total_value or 0.0,
        metadata_=account.metadata_,
    )
    
    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    
    return InvestmentAccountResponse.model_validate(db_account)


@router.get("/accounts", response_model=List[InvestmentAccountResponse])
async def list_investment_accounts(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    List all investment accounts for the current user.
    
    Args:
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        List of investment accounts
    """
    from app.db import InvestmentAccount
    
    result = await db.execute(
        select(InvestmentAccount).where(InvestmentAccount.user_id == user_id)
    )
    accounts = result.scalars().all()
    
    return [InvestmentAccountResponse.model_validate(account) for account in accounts]


@router.get("/accounts/{account_id}", response_model=InvestmentAccountResponse)
async def get_investment_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get a specific investment account.
    
    Args:
        account_id: Account ID
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        Investment account details
    """
    from app.db import InvestmentAccount
    
    result = await db.execute(
        select(InvestmentAccount).where(
            InvestmentAccount.id == account_id,
            InvestmentAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment account not found",
        )
    
    return InvestmentAccountResponse.model_validate(account)


@router.delete("/accounts/{account_id}")
async def delete_investment_account(
    account_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Delete an investment account and all its holdings.
    
    Args:
        account_id: Account ID
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    from app.db import InvestmentAccount, InvestmentHolding
    
    # Verify account belongs to user
    result = await db.execute(
        select(InvestmentAccount).where(
            InvestmentAccount.id == account_id,
            InvestmentAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment account not found",
        )
    
    # Delete all holdings for this account
    await db.execute(
        delete(InvestmentHolding).where(InvestmentHolding.account_id == account_id)
    )
    
    # Delete account
    await db.delete(account)
    await db.commit()
    
    return {"message": "Investment account deleted successfully"}


@router.get("/holdings", response_model=List[InvestmentHoldingResponse])
async def list_holdings(
    account_id: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    List all investment holdings for the current user.
    
    Args:
        account_id: Optional filter by account
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        List of investment holdings
    """
    from app.db import InvestmentHolding
    
    query = select(InvestmentHolding).where(InvestmentHolding.user_id == user_id)
    
    if account_id:
        query = query.where(InvestmentHolding.account_id == account_id)
    
    result = await db.execute(query)
    holdings = result.scalars().all()
    
    return [InvestmentHoldingResponse.model_validate(holding) for holding in holdings]


@router.post("/holdings/{holding_id}/refresh-price")
async def refresh_holding_price(
    holding_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Refresh the current price and related fields for a holding using Yahoo Finance.
    
    Args:
        holding_id: Holding ID
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        Updated holding with refreshed price data
    """
    from app.db import InvestmentHolding
    
    # Get holding
    result = await db.execute(
        select(InvestmentHolding).where(
            InvestmentHolding.id == holding_id,
            InvestmentHolding.user_id == user_id,
        )
    )
    holding = result.scalar_one_or_none()
    
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment holding not found",
        )
    
    # Refresh price from Yahoo Finance
    try:
        refreshed = await YahooFinanceEnrichmentService.refresh_holding_prices(
            symbol=holding.symbol,
            quantity=holding.quantity,
            cost_basis=holding.cost_basis,
        )
        
        # Update holding fields
        holding.current_price = refreshed.current_price
        holding.market_value = refreshed.market_value
        holding.day_change = refreshed.day_change
        holding.day_change_pct = refreshed.day_change_pct
        holding.unrealized_gain_loss = refreshed.unrealized_gain_loss
        holding.unrealized_gain_loss_pct = refreshed.unrealized_gain_loss_pct
        
        await db.commit()
        await db.refresh(holding)
        
        return InvestmentHoldingResponse.model_validate(holding)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh price: {str(e)}",
        )


@router.delete("/holdings/{holding_id}")
async def delete_holding(
    holding_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Delete a specific investment holding.
    
    Args:
        holding_id: Holding ID
        user_id: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    from app.db import InvestmentHolding, InvestmentAccount
    
    # Get holding
    result = await db.execute(
        select(InvestmentHolding).where(
            InvestmentHolding.id == holding_id,
            InvestmentHolding.user_id == user_id,
        )
    )
    holding = result.scalar_one_or_none()
    
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment holding not found",
        )
    
    account_id = holding.account_id
    
    # Delete holding
    await db.delete(holding)
    
    # Recalculate account total value
    result = await db.execute(
        select(InvestmentHolding).where(InvestmentHolding.account_id == account_id)
    )
    remaining_holdings = result.scalars().all()
    
    total_value = sum(h.market_value or 0.0 for h in remaining_holdings)
    
    # Update account
    result = await db.execute(
        select(InvestmentAccount).where(InvestmentAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    
    if account:
        account.total_value = total_value
    
    await db.commit()
    
    return {"message": "Investment holding deleted successfully"}
