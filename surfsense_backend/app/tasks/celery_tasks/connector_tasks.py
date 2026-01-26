"""Celery tasks for connector indexing."""

import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """
    Create a new async session maker for Celery tasks.
    This is necessary because Celery tasks run in a new event loop,
    and the default session maker is bound to the main app's event loop.
    """
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,  # Don't use connection pooling for Celery tasks
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="index_plaid_transactions", bind=True)
def index_plaid_transactions_task(
    self,
    connector_id: int,
):
    """Celery task to index Plaid bank transactions."""
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_index_plaid_transactions(connector_id))
    finally:
        loop.close()


async def _index_plaid_transactions(
    connector_id: int,
):
    """Index Plaid transactions with new session."""
    from sqlalchemy import select

    from app.db import SearchSourceConnector, SearchSourceConnectorType
    from app.tasks.plaid_indexers.bank_of_america_plaid_indexer import (
        BankOfAmericaPlaidIndexer,
    )
    from app.tasks.plaid_indexers.chase_plaid_indexer import ChasePlaidIndexer
    from app.tasks.plaid_indexers.fidelity_plaid_indexer import FidelityPlaidIndexer

    # Map connector types to indexers
    INDEXER_MAP = {
        SearchSourceConnectorType.CHASE_BANK: ChasePlaidIndexer,
        SearchSourceConnectorType.FIDELITY_INVESTMENTS: FidelityPlaidIndexer,
        SearchSourceConnectorType.BANK_OF_AMERICA: BankOfAmericaPlaidIndexer,
    }

    async with get_celery_session_maker()() as session:
        # Get connector
        stmt = select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id
        )
        result = await session.execute(stmt)
        connector = result.scalar_one_or_none()

        if not connector:
            logger.error(f"Connector {connector_id} not found")
            return

        # Get indexer class for connector type
        indexer_class = INDEXER_MAP.get(connector.connector_type)
        if not indexer_class:
            logger.error(
                f"No indexer found for connector type: {connector.connector_type}"
            )
            return

        # Create indexer and run
        indexer = indexer_class()
        try:
            result = await indexer.index_transactions(
                session=session,
                connector=connector,
                user_id=str(connector.user_id),
                days_back=90,  # Fetch last 90 days
            )

            # Update last indexed timestamp
            from datetime import UTC, datetime

            connector.last_indexed_at = datetime.now(UTC)
            await session.commit()

            logger.info(
                f"Successfully indexed {connector.name}: "
                f"{result['transaction_count']} transactions, "
                f"{result['documents_created']} documents created"
            )

        except Exception as e:
            logger.error(f"Error indexing {connector.name}: {e}", exc_info=True)
            raise
