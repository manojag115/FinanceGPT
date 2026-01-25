"""Meta-scheduler task for FinanceGPT - checks for Plaid connectors needing periodic sync."""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config
from app.db import SearchSourceConnector, SearchSourceConnectorType

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """Create async session maker for Celery tasks."""
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="check_periodic_schedules")
def check_periodic_schedules_task():
    """
    Check Plaid bank connectors for periodic transaction syncing.
    This task runs periodically and triggers syncing for any connector
    whose next_scheduled_at time has passed.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_check_and_trigger_schedules())
    finally:
        loop.close()


async def _check_and_trigger_schedules():
    """Check database for Plaid connectors that need syncing and trigger their tasks."""
    async with get_celery_session_maker()() as session:
        try:
            # Find all Plaid connectors with periodic indexing enabled that are due
            now = datetime.now(UTC)
            result = await session.execute(
                select(SearchSourceConnector).filter(
                    SearchSourceConnector.periodic_indexing_enabled == True,  # noqa: E712
                    SearchSourceConnector.next_scheduled_at <= now,
                    SearchSourceConnector.connector_type.in_([
                        SearchSourceConnectorType.CHASE_BANK,
                        SearchSourceConnectorType.FIDELITY_INVESTMENTS,
                        SearchSourceConnectorType.BANK_OF_AMERICA,
                    ])
                )
            )
            due_connectors = result.scalars().all()

            if not due_connectors:
                logger.debug("No Plaid connectors due for periodic syncing")
                return

            logger.info(f"Found {len(due_connectors)} Plaid connectors due for transaction sync")

            # Import Plaid indexing task
            from app.tasks.celery_tasks.connector_tasks import index_plaid_transactions_task

            # Trigger syncing for each due connector
            for connector in due_connectors:
                logger.info(
                    f"Triggering periodic transaction sync for connector {connector.id} "
                    f"({connector.connector_type.value})"
                )
                
                index_plaid_transactions_task.delay(connector.id)

                # Update next_scheduled_at for next run
                from datetime import timedelta

                connector.next_scheduled_at = now + timedelta(
                    minutes=connector.indexing_frequency_minutes
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Error checking periodic schedules: {e!s}", exc_info=True)
            await session.rollback()
