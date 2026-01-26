"""
SearchSourceConnector routes for CRUD operations:
POST /search-source-connectors/ - Create a new connector
GET /search-source-connectors/ - List all connectors for the current user (optionally filtered by search space)
GET /search-source-connectors/{connector_id} - Get a specific connector
PUT /search-source-connectors/{connector_id} - Update a specific connector
DELETE /search-source-connectors/{connector_id} - Delete a specific connector
POST /search-source-connectors/{connector_id}/index - Index content from a connector to a search space

MCP (Model Context Protocol) Connector routes:
POST /connectors/mcp - Create a new MCP connector with custom API tools
GET /connectors/mcp - List all MCP connectors for the current user's search space
GET /connectors/mcp/{connector_id} - Get a specific MCP connector with tools config
PUT /connectors/mcp/{connector_id} - Update an MCP connector's tools config
DELETE /connectors/mcp/{connector_id} - Delete an MCP connector

Note: OAuth connectors (Gmail, Drive, Slack, etc.) support multiple accounts per search space.
Non-OAuth connectors (BookStack, GitHub, etc.) are limited to one per search space.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Permission,
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    async_session_maker,
    get_async_session,
)
from app.schemas import (
    MCPConnectorCreate,
    MCPConnectorRead,
    MCPConnectorUpdate,
    SearchSourceConnectorBase,
    SearchSourceConnectorCreate,
    SearchSourceConnectorRead,
    SearchSourceConnectorUpdate,
)
from app.services.notification_service import NotificationService
from app.users import current_active_user
from app.utils.periodic_scheduler import (
    create_periodic_schedule,
    delete_periodic_schedule,
    update_periodic_schedule,
)
from app.utils.rbac import check_permission

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search-source-connectors", response_model=SearchSourceConnectorRead)
async def create_search_source_connector(
    connector: SearchSourceConnectorCreate,
    search_space_id: int = Query(
        ..., description="ID of the search space to associate the connector with"
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new search source connector.
    Requires CONNECTORS_CREATE permission.

    Each search space can have only one connector of each type (based on search_space_id and connector_type).
    The config must contain the appropriate keys for the connector type.
    """
    try:
        # Check if user has permission to create connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_CREATE.value,
            "You don't have permission to create connectors in this search space",
        )

        # Check if a connector with the same type already exists for this search space
        # (for non-OAuth connectors that don't support multiple accounts)
        # Exception: MCP_CONNECTOR can have multiple instances with different names
        if connector.connector_type != SearchSourceConnectorType.MCP_CONNECTOR:
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id == search_space_id,
                    SearchSourceConnector.connector_type == connector.connector_type,
                )
            )
            existing_connector = result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail=f"A connector with type {connector.connector_type} already exists in this search space.",
                )

        # Prepare connector data
        connector_data = connector.model_dump()

        # Automatically set next_scheduled_at if periodic indexing is enabled
        if (
            connector.periodic_indexing_enabled
            and connector.indexing_frequency_minutes
            and connector.next_scheduled_at is None
        ):
            connector_data["next_scheduled_at"] = datetime.now(UTC) + timedelta(
                minutes=connector.indexing_frequency_minutes
            )

        db_connector = SearchSourceConnector(
            **connector_data, search_space_id=search_space_id, user_id=user.id
        )
        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        # Create periodic schedule if periodic indexing is enabled
        if (
            db_connector.periodic_indexing_enabled
            and db_connector.indexing_frequency_minutes
        ):
            success = create_periodic_schedule(
                connector_id=db_connector.id,
                search_space_id=search_space_id,
                user_id=str(user.id),
                connector_type=db_connector.connector_type,
                frequency_minutes=db_connector.indexing_frequency_minutes,
            )
            if not success:
                logger.warning(
                    f"Failed to create periodic schedule for connector {db_connector.id}"
                )

        return db_connector
    except ValidationError as e:
        await session.rollback()
        raise HTTPException(status_code=422, detail=f"Validation error: {e!s}") from e
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Integrity error: A connector with this type already exists in this search space. {e!s}",
        ) from e
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        logger.error(f"Failed to create search source connector: {e!s}")
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create search source connector: {e!s}",
        ) from e


@router.get("/search-source-connectors", response_model=list[SearchSourceConnectorRead])
async def read_search_source_connectors(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all search source connectors for a search space.
    Requires CONNECTORS_READ permission.
    """
    try:
        if search_space_id is None:
            raise HTTPException(
                status_code=400,
                detail="search_space_id is required",
            )

        # Check if user has permission to read connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view connectors in this search space",
        )

        query = select(SearchSourceConnector).filter(
            SearchSourceConnector.search_space_id == search_space_id
        )

        result = await session.execute(query.offset(skip).limit(limit))
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch search source connectors: {e!s}",
        ) from e


@router.get(
    "/search-source-connectors/{connector_id}", response_model=SearchSourceConnectorRead
)
async def read_search_source_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific search source connector by ID.
    Requires CONNECTORS_READ permission.
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check permission
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view this connector",
        )

        return connector
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search source connector: {e!s}"
        ) from e


@router.put(
    "/search-source-connectors/{connector_id}", response_model=SearchSourceConnectorRead
)
async def update_search_source_connector(
    connector_id: int,
    connector_update: SearchSourceConnectorUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a search source connector.
    Requires CONNECTORS_UPDATE permission.
    Handles partial updates, including merging changes into the 'config' field.
    """
    # Get the connector first
    result = await session.execute(
        select(SearchSourceConnector).filter(SearchSourceConnector.id == connector_id)
    )
    db_connector = result.scalars().first()

    if not db_connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Check permission
    await check_permission(
        session,
        user,
        db_connector.search_space_id,
        Permission.CONNECTORS_UPDATE.value,
        "You don't have permission to update this connector",
    )

    # Convert the sparse update data (only fields present in request) to a dict
    update_data = connector_update.model_dump(exclude_unset=True)

    # Validate periodic indexing fields
    # Get the effective values after update
    effective_is_indexable = update_data.get("is_indexable", db_connector.is_indexable)
    effective_periodic_enabled = update_data.get(
        "periodic_indexing_enabled", db_connector.periodic_indexing_enabled
    )
    effective_frequency = update_data.get(
        "indexing_frequency_minutes", db_connector.indexing_frequency_minutes
    )

    # Validate periodic indexing configuration
    if effective_periodic_enabled:
        if not effective_is_indexable:
            raise HTTPException(
                status_code=422,
                detail="periodic_indexing_enabled can only be True for indexable connectors",
            )
        if effective_frequency is None:
            raise HTTPException(
                status_code=422,
                detail="indexing_frequency_minutes is required when periodic_indexing_enabled is True",
            )
        if effective_frequency <= 0:
            raise HTTPException(
                status_code=422,
                detail="indexing_frequency_minutes must be greater than 0",
            )

        # Automatically set next_scheduled_at if not provided and periodic indexing is being enabled
        if (
            "periodic_indexing_enabled" in update_data
            or "indexing_frequency_minutes" in update_data
        ) and "next_scheduled_at" not in update_data:
            # Schedule the next indexing based on the frequency
            update_data["next_scheduled_at"] = datetime.now(UTC) + timedelta(
                minutes=effective_frequency
            )
    elif (
        effective_periodic_enabled is False
        and "periodic_indexing_enabled" in update_data
    ):
        # If disabling periodic indexing, clear the next_scheduled_at
        update_data["next_scheduled_at"] = None

    # Special handling for 'config' field
    if "config" in update_data:
        incoming_config = update_data["config"]  # Config data from the request
        existing_config = (
            db_connector.config if db_connector.config else {}
        )  # Current config from DB

        # Merge incoming config into existing config
        # This preserves existing keys (like GITHUB_PAT) if they are not in the incoming data
        merged_config = existing_config.copy()
        merged_config.update(incoming_config)

        # -- Validation after merging --
        # Validate the *merged* config based on the connector type
        # We need the connector type - use the one from the update if provided, else the existing one
        current_connector_type = (
            connector_update.connector_type
            if connector_update.connector_type is not None
            else db_connector.connector_type
        )

        try:
            # We can reuse the base validator by creating a temporary base model instance
            # Note: This assumes 'name' and 'is_indexable' are not crucial for config validation itself
            temp_data_for_validation = {
                "name": db_connector.name,  # Use existing name
                "connector_type": current_connector_type,
                "is_indexable": db_connector.is_indexable,  # Use existing value
                "last_indexed_at": db_connector.last_indexed_at,  # Not used by validator
                "config": merged_config,
            }
            SearchSourceConnectorBase.model_validate(temp_data_for_validation)
        except ValidationError as e:
            # Raise specific validation error for the merged config
            raise HTTPException(
                status_code=422, detail=f"Validation error for merged config: {e!s}"
            ) from e

        # If validation passes, update the main update_data dict with the merged config
        update_data["config"] = merged_config

    # Apply all updates (including the potentially merged config)
    for key, value in update_data.items():
        # Prevent changing connector_type if it causes a duplicate (check moved here)
        if key == "connector_type" and value != db_connector.connector_type:
            check_result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.search_space_id
                    == db_connector.search_space_id,
                    SearchSourceConnector.connector_type == value,
                    SearchSourceConnector.id != connector_id,
                )
            )
            existing_connector = check_result.scalars().first()
            if existing_connector:
                raise HTTPException(
                    status_code=409,
                    detail=f"A connector with type {value} already exists in this search space.",
                )

        setattr(db_connector, key, value)

    try:
        await session.commit()
        await session.refresh(db_connector)

        # Handle periodic schedule updates
        if (
            "periodic_indexing_enabled" in update_data
            or "indexing_frequency_minutes" in update_data
        ):
            if (
                db_connector.periodic_indexing_enabled
                and db_connector.indexing_frequency_minutes
            ):
                # Create or update the periodic schedule
                success = update_periodic_schedule(
                    connector_id=db_connector.id,
                    search_space_id=db_connector.search_space_id,
                    user_id=str(user.id),
                    connector_type=db_connector.connector_type,
                    frequency_minutes=db_connector.indexing_frequency_minutes,
                )
                if not success:
                    logger.warning(
                        f"Failed to update periodic schedule for connector {db_connector.id}"
                    )
            else:
                # Delete the periodic schedule if disabled
                success = delete_periodic_schedule(db_connector.id)
                if not success:
                    logger.warning(
                        f"Failed to delete periodic schedule for connector {db_connector.id}"
                    )

        return db_connector
    except IntegrityError as e:
        await session.rollback()
        # This might occur if connector_type constraint is violated somehow after the check
        raise HTTPException(
            status_code=409, detail=f"Database integrity error during update: {e!s}"
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to update search source connector {connector_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update search source connector: {e!s}",
        ) from e


@router.delete("/search-source-connectors/{connector_id}", response_model=dict)
async def delete_search_source_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a search source connector.
    Requires CONNECTORS_DELETE permission.
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        db_connector = result.scalars().first()

        if not db_connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check permission
        await check_permission(
            session,
            user,
            db_connector.search_space_id,
            Permission.CONNECTORS_DELETE.value,
            "You don't have permission to delete this connector",
        )

        # Delete any periodic schedule associated with this connector
        if db_connector.periodic_indexing_enabled:
            success = delete_periodic_schedule(connector_id)
            if not success:
                logger.warning(
                    f"Failed to delete periodic schedule for connector {connector_id}"
                )

        await session.delete(db_connector)
        await session.commit()
        return {"message": "Search source connector deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete search source connector: {e!s}",
        ) from e


@router.post(
    "/search-source-connectors/{connector_id}/index", response_model=dict[str, Any]
)
async def index_connector_content(
    connector_id: int,
    search_space_id: int = Query(
        ..., description="ID of the search space to store indexed content"
    ),
    start_date: str = Query(
        None,
        description="Start date for indexing (YYYY-MM-DD format). If not provided, uses last_indexed_at or defaults to 365 days ago",
    ),
    end_date: str = Query(
        None,
        description="End date for indexing (YYYY-MM-DD format). If not provided, uses today's date.",
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Index content from a connector to a search space.
    Requires CONNECTORS_UPDATE permission (to trigger indexing).

    Currently supports:
    - COMPOSIO_CONNECTOR: Indexes content from Composio-connected apps
    - CHASE_BANK: Indexes bank transactions from Chase
    - FIDELITY_INVESTMENTS: Indexes investment transactions from Fidelity  
    - BANK_OF_AMERICA: Indexes bank transactions from Bank of America

    Args:
        connector_id: ID of the connector to use
        search_space_id: ID of the search space to store indexed content

    Returns:
        Dictionary with indexing status
    """
    try:
        # Get the connector first
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")

        # Check if user has permission to update connectors (indexing is an update operation)
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_UPDATE.value,
            "You don't have permission to index content in this search space",
        )

        # Handle different connector types
        response_message = ""
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Determine the actual date range to use
        if start_date is None:
            # Use last_indexed_at or default to 365 days ago
            if connector.last_indexed_at:
                today = datetime.now().date()
                if connector.last_indexed_at.date() == today:
                    # If last indexed today, go back 1 day to ensure we don't miss anything
                    indexing_from = (today - timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    indexing_from = connector.last_indexed_at.strftime("%Y-%m-%d")
            else:
                indexing_from = (datetime.now() - timedelta(days=365)).strftime(
                    "%Y-%m-%d"
                )
        else:
            indexing_from = start_date

        # Default to today if no end_date provided
        indexing_to = end_date if end_date else today_str

        if connector.connector_type == SearchSourceConnectorType.COMPOSIO_CONNECTOR:
            from app.tasks.celery_tasks.connector_tasks import (
                index_composio_connector_task,
            )

            logger.info(
                f"Triggering Composio connector indexing for connector {connector_id} into search space {search_space_id} from {indexing_from} to {indexing_to}"
            )
            index_composio_connector_task.delay(
                connector_id, search_space_id, str(user.id), indexing_from, indexing_to
            )
            response_message = "Composio connector indexing started in the background."

        elif connector.connector_type in (
            SearchSourceConnectorType.CHASE_BANK,
            SearchSourceConnectorType.FIDELITY_INVESTMENTS,
            SearchSourceConnectorType.BANK_OF_AMERICA,
        ):
            from app.tasks.celery_tasks.connector_tasks import (
                index_plaid_transactions_task,
            )

            logger.info(
                f"Triggering Plaid transactions indexing for connector {connector_id} into search space {search_space_id}"
            )
            index_plaid_transactions_task.delay(connector_id)
            response_message = "Bank transactions indexing started in the background."

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Indexing not supported for connector type: {connector.connector_type}",
            )

        return {
            "message": response_message,
            "connector_id": connector_id,
            "search_space_id": search_space_id,
            "indexing_from": indexing_from,
            "indexing_to": indexing_to,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to initiate indexing for connector {connector_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate indexing: {e!s}"
        ) from e


async def _update_connector_timestamp_by_id(session: AsyncSession, connector_id: int):
    """
    Update the last_indexed_at timestamp for a connector by its ID.
    Internal helper function for routes.

    Args:
        session: Database session
        connector_id: ID of the connector to update
    """
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id
            )
        )
        connector = result.scalars().first()

        if connector:
            connector.last_indexed_at = datetime.now()
            await session.commit()
            logger.info(f"Updated last_indexed_at for connector {connector_id}")
    except Exception as e:
        logger.error(
            f"Failed to update last_indexed_at for connector {connector_id}: {e!s}"
        )
        await session.rollback()


# =============================================================================
# MCP Connector Routes
# =============================================================================


@router.post("/connectors/mcp", response_model=MCPConnectorRead, status_code=201)
async def create_mcp_connector(
    connector_data: MCPConnectorCreate,
    search_space_id: int = Query(..., description="Search space ID"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new MCP (Model Context Protocol) connector.

    MCP connectors allow users to connect to MCP servers (like in Cursor).
    Tools are auto-discovered from the server - no manual configuration needed.

    Args:
        connector_data: MCP server configuration (command, args, env)
        search_space_id: ID of the search space to attach the connector to
        session: Database session
        user: Current authenticated user

    Returns:
        Created MCP connector with server configuration

    Raises:
        HTTPException: If search space not found or permission denied
    """
    try:
        # Check user has permission to create connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_CREATE.value,
            "You don't have permission to create connectors in this search space",
        )

        # Create the connector with single server config
        db_connector = SearchSourceConnector(
            name=connector_data.name,
            connector_type=SearchSourceConnectorType.MCP_CONNECTOR,
            is_indexable=False,  # MCP connectors are not indexable
            config={"server_config": connector_data.server_config.model_dump()},
            periodic_indexing_enabled=False,
            indexing_frequency_minutes=None,
            search_space_id=search_space_id,
            user_id=user.id,
        )

        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        logger.info(
            f"Created MCP connector {db_connector.id} "
            f"for user {user.id} in search space {search_space_id}"
        )

        # Convert to read schema
        connector_read = SearchSourceConnectorRead.model_validate(db_connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create MCP connector: {e!s}"
        ) from e


@router.get("/connectors/mcp", response_model=list[MCPConnectorRead])
async def list_mcp_connectors(
    search_space_id: int = Query(..., description="Search space ID"),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all MCP connectors for a search space.

    Args:
        search_space_id: ID of the search space
        session: Database session
        user: Current authenticated user

    Returns:
        List of MCP connectors with their tool configurations
    """
    try:
        # Check user has permission to read connectors
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view connectors in this search space",
        )

        # Fetch MCP connectors
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
                SearchSourceConnector.search_space_id == search_space_id,
            )
        )

        connectors = result.scalars().all()
        return [
            MCPConnectorRead.from_connector(SearchSourceConnectorRead.model_validate(c))
            for c in connectors
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list MCP connectors: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list MCP connectors: {e!s}"
        ) from e


@router.get("/connectors/mcp/{connector_id}", response_model=MCPConnectorRead)
async def get_mcp_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific MCP connector by ID.

    Args:
        connector_id: ID of the connector
        session: Database session
        user: Current authenticated user

    Returns:
        MCP connector with tool configurations
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to read connectors
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_READ.value,
            "You don't have permission to view this connector",
        )

        connector_read = SearchSourceConnectorRead.model_validate(connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to get MCP connector: {e!s}"
        ) from e


@router.put("/connectors/mcp/{connector_id}", response_model=MCPConnectorRead)
async def update_mcp_connector(
    connector_id: int,
    connector_update: MCPConnectorUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update an MCP connector.

    Args:
        connector_id: ID of the connector to update
        connector_update: Updated connector data
        session: Database session
        user: Current authenticated user

    Returns:
        Updated MCP connector
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to update connectors
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_UPDATE.value,
            "You don't have permission to update this connector",
        )

        # Update fields
        if connector_update.name is not None:
            connector.name = connector_update.name

        if connector_update.server_config is not None:
            connector.config = {
                "server_config": connector_update.server_config.model_dump()
            }

        connector.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(connector)

        logger.info(f"Updated MCP connector {connector_id}")

        connector_read = SearchSourceConnectorRead.model_validate(connector)
        return MCPConnectorRead.from_connector(connector_read)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update MCP connector: {e!s}"
        ) from e


@router.delete("/connectors/mcp/{connector_id}", status_code=204)
async def delete_mcp_connector(
    connector_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete an MCP connector.

    Args:
        connector_id: ID of the connector to delete
        session: Database session
        user: Current authenticated user
    """
    try:
        # Fetch connector
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.id == connector_id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.MCP_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(status_code=404, detail="MCP connector not found")

        # Check user has permission to delete connectors
        await check_permission(
            session,
            user,
            connector.search_space_id,
            Permission.CONNECTORS_DELETE.value,
            "You don't have permission to delete this connector",
        )

        await session.delete(connector)
        await session.commit()

        logger.info(f"Deleted MCP connector {connector_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP connector: {e!s}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete MCP connector: {e!s}"
        ) from e


@router.post("/connectors/mcp/test")
async def test_mcp_server_connection(
    server_config: dict = Body(...),
    user: User = Depends(current_active_user),
):
    """
    Test connection to an MCP server and fetch available tools.

    This endpoint allows users to test their MCP server configuration
    before saving it, similar to Cursor's flow.

    Supports two transport types:
    - stdio: Local process with command, args, env
    - streamable-http/http/sse: Remote HTTP server with url, headers

    Args:
        server_config: Server configuration
        user: Current authenticated user

    Returns:
        Connection status and list of available tools
    """
    try:
        from app.agents.new_chat.tools.mcp_client import (
            test_mcp_connection,
            test_mcp_http_connection,
        )

        transport = server_config.get("transport", "stdio")

        # HTTP transport (streamable-http, http, sse)
        if transport in ("streamable-http", "http", "sse"):
            url = server_config.get("url")
            headers = server_config.get("headers", {})

            if not url:
                raise HTTPException(
                    status_code=400, detail="Server URL is required for HTTP transport"
                )

            result = await test_mcp_http_connection(url, headers, transport)
            return result

        # stdio transport (default)
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not command:
            raise HTTPException(
                status_code=400, detail="Server command is required for stdio transport"
            )

        # Test the connection
        result = await test_mcp_connection(command, args, env)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test MCP connection: {e!s}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to test connection: {e!s}",
            "tools": [],
        }
