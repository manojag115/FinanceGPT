"""
Plaid OAuth and connector routes.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SearchSourceConnector, SearchSourceConnectorType, User, get_async_session
from app.services.plaid_service import PlaidService
from app.tasks.plaid_indexers.bank_of_america_plaid_indexer import (
    BankOfAmericaPlaidIndexer,
)
from app.tasks.plaid_indexers.chase_plaid_indexer import ChasePlaidIndexer
from app.tasks.plaid_indexers.fidelity_plaid_indexer import FidelityPlaidIndexer
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plaid", tags=["plaid"])





# Mapping of connector types to indexers
CONNECTOR_INDEXERS = {
    SearchSourceConnectorType.CHASE_BANK: ChasePlaidIndexer,
    SearchSourceConnectorType.FIDELITY_INVESTMENTS: FidelityPlaidIndexer,
    SearchSourceConnectorType.BANK_OF_AMERICA: BankOfAmericaPlaidIndexer,
}


class CreateLinkTokenRequest(BaseModel):
    """Request to create Plaid Link token."""

    connector_type: SearchSourceConnectorType
    search_space_id: int


class CreateLinkTokenResponse(BaseModel):
    """Response with Plaid Link token."""

    link_token: str
    expiration: str


class ExchangePublicTokenRequest(BaseModel):
    """Request to exchange public token."""

    public_token: str
    connector_type: SearchSourceConnectorType
    search_space_id: int
    connector_name: str | None = None


class PlaidConnectorResponse(BaseModel):
    """Response with connector details."""

    id: int
    name: str
    connector_type: SearchSourceConnectorType
    is_indexable: bool
    last_indexed_at: str | None
    periodic_indexing_enabled: bool
    indexing_frequency_minutes: int | None


@router.post("/link-token", response_model=CreateLinkTokenResponse)
async def create_link_token(
    request: CreateLinkTokenRequest,
    user: User = Depends(current_active_user),
) -> CreateLinkTokenResponse:
    """
    Create a Plaid Link token for initiating OAuth flow.

    This token is used by the frontend to open Plaid Link UI.
    """
    try:
        plaid_service = PlaidService()

        # Get institution ID from connector type
        # Validate connector type
        if request.connector_type not in CONNECTOR_INDEXERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported connector type: {request.connector_type}",
            )

        # In sandbox, don't specify institution_id - let user select from all test institutions
        institution_id = None  # Allow user to select any sandbox institution

        # Create link token
        response = await plaid_service.create_link_token(
            user_id=str(user.id), institution_id=institution_id
        )

        return CreateLinkTokenResponse(
            link_token=response["link_token"], 
            expiration=response["expiration"].isoformat() if isinstance(response["expiration"], datetime) else str(response["expiration"])
        )

    except Exception as e:
        logger.error("Error creating link token: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link token: {e!s}",
        ) from e


@router.post("/exchange-token", response_model=PlaidConnectorResponse)
async def exchange_public_token(
    request: ExchangePublicTokenRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> PlaidConnectorResponse:
    """
    Exchange public token for access token and create connector.

    After user completes Plaid Link flow, frontend sends the public token here.
    We exchange it for an access token, store it, and trigger initial indexing.
    """
    try:
        plaid_service = PlaidService()

        # Exchange public token for access token
        token_data = await plaid_service.exchange_public_token(request.public_token)
        access_token = token_data["access_token"]
        item_id = token_data["item_id"]

        # Get accounts to display in connector name
        accounts_data = await plaid_service.get_accounts(access_token)
        
        # Convert Plaid response to JSON-serializable format
        # Plaid returns enums like AccountType which aren't JSON serializable
        accounts = [
            {
                "account_id": acc["account_id"],
                "name": acc["name"],
                "mask": acc.get("mask"),
                "type": acc["type"].value if hasattr(acc["type"], "value") else str(acc["type"]),
                "subtype": acc["subtype"].value if acc.get("subtype") and hasattr(acc["subtype"], "value") else str(acc.get("subtype")) if acc.get("subtype") else None,
                "balances": {
                    "current": acc["balances"]["current"],
                    "available": acc["balances"].get("available"),
                    "limit": acc["balances"].get("limit"),
                } if acc.get("balances") else None,
            }
            for acc in accounts_data
        ]

        # Get indexer for connector type
        indexer_class = CONNECTOR_INDEXERS.get(request.connector_type)
        if not indexer_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported connector type: {request.connector_type}",
            )

        indexer = indexer_class()

        # Create connector name
        if request.connector_name:
            connector_name = request.connector_name
        else:
            account_names = ", ".join([acc["name"] for acc in accounts[:3]])
            connector_name = f"{indexer.connector_name} ({account_names})"

        # Check if connector already exists for this item
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.user_id == user.id,
            SearchSourceConnector.search_space_id == request.search_space_id,
            SearchSourceConnector.connector_type == request.connector_type,
        )
        result = await session.execute(stmt)
        existing_connector = result.scalar_one_or_none()

        if existing_connector:
            # Update existing connector
            existing_connector.config = {
                "access_token": access_token,
                "item_id": item_id,
                "accounts": accounts,
            }
            existing_connector.is_indexable = True
            existing_connector.periodic_indexing_enabled = True
            existing_connector.indexing_frequency_minutes = 1440  # Daily
            await session.commit()
            await session.refresh(existing_connector)

            connector = existing_connector
        else:
            # Create new connector
            connector = SearchSourceConnector(
                name=connector_name,
                connector_type=request.connector_type,
                user_id=user.id,
                search_space_id=request.search_space_id,
                is_indexable=True,
                periodic_indexing_enabled=True,
                indexing_frequency_minutes=1440,  # Daily sync
                config={
                    "access_token": access_token,
                    "item_id": item_id,
                    "accounts": accounts,
                },
            )

            session.add(connector)
            await session.commit()
            await session.refresh(connector)

        # Trigger initial indexing asynchronously
        from app.tasks.celery_tasks.connector_tasks import index_plaid_transactions_task

        index_plaid_transactions_task.delay(connector.id)

        return PlaidConnectorResponse(
            id=connector.id,
            name=connector.name,
            connector_type=connector.connector_type,
            is_indexable=connector.is_indexable,
            last_indexed_at=connector.last_indexed_at.isoformat()
            if connector.last_indexed_at
            else None,
            periodic_indexing_enabled=connector.periodic_indexing_enabled,
            indexing_frequency_minutes=connector.indexing_frequency_minutes,
        )

    except Exception as e:
        logger.error("Error exchanging public token: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange token: {e!s}",
        ) from e


@router.get("/connectors/{connector_id}/accounts")
async def get_connector_accounts(
    connector_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Get all accounts for a Plaid connector.
    
    Returns the accounts stored in the connector config along with current balances.
    """
    try:
        # Get connector
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
        )
        result = await session.execute(stmt)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found"
            )

        # Get accounts from config
        accounts = connector.config.get("accounts", [])
        access_token = connector.config.get("access_token")
        
        # Optionally refresh account balances from Plaid
        if access_token:
            try:
                plaid_service = PlaidService()
                fresh_accounts = await plaid_service.get_accounts(access_token)
                
                # Merge fresh data with stored accounts
                account_map = {acc["account_id"]: acc for acc in fresh_accounts}
                for account in accounts:
                    if account["account_id"] in account_map:
                        fresh = account_map[account["account_id"]]
                        account["balances"] = {
                            "current": fresh["balance"]["current"],
                            "available": fresh["balance"].get("available"),
                            "limit": fresh["balance"].get("limit"),
                        }
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to refresh account balances: %s", e)

        return {
            "connector_id": connector.id,
            "connector_name": connector.name,
            "connector_type": connector.connector_type,
            "accounts": accounts,
            "last_indexed_at": connector.last_indexed_at.isoformat() if connector.last_indexed_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting connector accounts: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get accounts: {e!s}",
        ) from e


@router.post("/link-token-update")
async def create_update_link_token(
    connector_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> CreateLinkTokenResponse:
    """
    Create a Plaid Link token for updating an existing connection.
    
    This allows users to add/remove accounts from an existing institution connection.
    """
    try:
        # Get connector
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
        )
        result = await session.execute(stmt)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found"
            )

        access_token = connector.config.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token found for connector"
            )

        # Create link token in update mode
        plaid_service = PlaidService()
        response = await plaid_service.create_update_link_token(  # type: ignore[attr-defined]
            user_id=str(user.id),
            access_token=access_token
        )

        return CreateLinkTokenResponse(
            link_token=response["link_token"],
            expiration=response["expiration"].isoformat() if isinstance(response["expiration"], datetime) else str(response["expiration"])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating update link token: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create update link token: {e!s}",
        ) from e


@router.post("/connectors/{connector_id}/accounts/refresh")
async def refresh_connector_accounts(
    connector_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Refresh the accounts list for a connector after user updates via Plaid Link.
    
    This should be called after a successful Plaid Link update flow.
    """
    try:
        # Get connector
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
        )
        result = await session.execute(stmt)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found"
            )

        access_token = connector.config.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token found"
            )

        # Fetch fresh accounts from Plaid
        plaid_service = PlaidService()
        accounts_data = await plaid_service.get_accounts(access_token)
        
        # Convert to our format
        accounts = [
            {
                "account_id": acc["account_id"],
                "name": acc["name"],
                "mask": acc.get("mask"),
                "type": acc["type"].value if hasattr(acc["type"], "value") else str(acc["type"]),
                "subtype": acc["subtype"].value if acc.get("subtype") and hasattr(acc["subtype"], "value") else str(acc.get("subtype")) if acc.get("subtype") else None,
                "balances": {
                    "current": acc["balances"]["current"],
                    "available": acc["balances"].get("available"),
                    "limit": acc["balances"].get("limit"),
                } if acc.get("balances") else None,
            }
            for acc in accounts_data
        ]

        # Update connector config
        connector.config["accounts"] = accounts
        await session.commit()

        return {
            "status": "success",
            "accounts": accounts,
            "message": f"Refreshed {len(accounts)} accounts"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error refreshing accounts: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh accounts: {e!s}",
        ) from e


@router.post("/connectors/{connector_id}/sync")
async def sync_connector(
    connector_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Manually trigger sync for a Plaid connector.

    Useful for testing or forcing an immediate update.
    """
    try:
        # Get connector
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user.id,
        )
        result = await session.execute(stmt)
        connector = result.scalar_one_or_none()

        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found"
            )

        # Trigger indexing
        from app.tasks.celery_tasks.connector_tasks import index_plaid_transactions_task

        task = index_plaid_transactions_task.delay(connector_id)

        return {
            "status": "syncing",
            "task_id": task.id,
            "message": "Sync started in background",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error syncing connector: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync connector: {e!s}",
        ) from e
