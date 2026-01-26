"""
Utility functions for managing periodic connector indexing schedules.

This module uses a meta-scheduler pattern instead of RedBeat's dynamic schedule creation.
Instead of creating individual Beat schedules for each connector, we:
1. Store schedule configuration in the database (next_scheduled_at, frequency)
2. Have ONE Beat task that runs every minute checking for due connectors
3. Trigger indexing tasks for connectors whose next_scheduled_at has passed

This avoids RedBeat's limitation where new schedules aren't discovered without restart.
"""

import logging

from app.db import SearchSourceConnectorType

logger = logging.getLogger(__name__)

# Mapping of connector types to their corresponding Celery task names
CONNECTOR_TASK_MAP = {
    SearchSourceConnectorType.CHASE_BANK: "index_plaid_transactions",
    SearchSourceConnectorType.FIDELITY_INVESTMENTS: "index_plaid_transactions",
    SearchSourceConnectorType.BANK_OF_AMERICA: "index_plaid_transactions",
}


def create_periodic_schedule(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    connector_type: SearchSourceConnectorType,
    frequency_minutes: int,
) -> bool:
    """
    Trigger the first indexing run immediately when periodic indexing is enabled.

    Note: The periodic schedule is managed by the database (next_scheduled_at field)
    and checked by the meta-scheduler task that runs every minute.
    This function just triggers the first run for immediate feedback.

    Args:
        connector_id: ID of the connector
        search_space_id: ID of the search space
        user_id: User ID
        connector_type: Type of connector
        frequency_minutes: Frequency in minutes (used for logging)

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(
            f"Periodic indexing enabled for connector {connector_id} "
            f"(frequency: {frequency_minutes} minutes). Triggering first run..."
        )

        # Import Plaid indexing task
        from app.tasks.celery_tasks.connector_tasks import (
            index_plaid_transactions_task,
        )

        # Map connector type to task
        task_map = {
            SearchSourceConnectorType.CHASE_BANK: index_plaid_transactions_task,
            SearchSourceConnectorType.FIDELITY_INVESTMENTS: index_plaid_transactions_task,
            SearchSourceConnectorType.BANK_OF_AMERICA: index_plaid_transactions_task,
        }

        # Trigger the first run immediately
        task = task_map.get(connector_type)
        if task:
            # Plaid tasks only need connector_id (not search_space_id, user_id, dates)
            task.delay(connector_id)
            logger.info(
                f"✓ First indexing run triggered for connector {connector_id}. "
                f"Periodic indexing will continue automatically every {frequency_minutes} minutes."
            )
        else:
            logger.error(f"No task mapping found for connector type: {connector_type}")
            return False

        return True

    except Exception as e:
        logger.error(
            f"Failed to trigger initial indexing for connector {connector_id}: {e!s}",
            exc_info=True,
        )
        return False


def delete_periodic_schedule(connector_id: int) -> bool:
    """
    Handle deletion of periodic schedule for a connector.

    Note: With the meta-scheduler pattern, the schedule is managed in the database.
    The next_scheduled_at field being set to None effectively disables it.
    This function just logs the action.

    Args:
        connector_id: ID of the connector

    Returns:
        True (always successful since database handles the state)
    """
    logger.info(f"Periodic indexing disabled for connector {connector_id}")
    return True


def update_periodic_schedule(
    connector_id: int,
    search_space_id: int,
    user_id: str,
    connector_type: SearchSourceConnectorType,
    frequency_minutes: int,
) -> bool:
    """
    Update an existing periodic schedule for a connector.

    Note: With the meta-scheduler pattern, updates are handled by the database.
    This function logs the update and optionally triggers an immediate run.

    Args:
        connector_id: ID of the connector
        search_space_id: ID of the search space
        user_id: User ID
        connector_type: Type of connector
        frequency_minutes: New frequency in minutes

    Returns:
        True if successful, False otherwise
    """
    logger.info(
        f"Periodic indexing schedule updated for connector {connector_id} "
        f"(new frequency: {frequency_minutes} minutes)"
    )
    # Optionally trigger an immediate run with the new schedule
    # Uncomment the line below if you want immediate execution on schedule update
    # return create_periodic_schedule(connector_id, search_space_id, user_id, connector_type, frequency_minutes)
    return True
