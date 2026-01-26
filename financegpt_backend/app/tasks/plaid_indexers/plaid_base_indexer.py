"""
Base indexer for Plaid-powered bank connectors.

All bank-specific connectors (Chase, Fidelity, etc.) inherit from this base class.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, SearchSourceConnector
from app.parsers.base_financial_parser import BankTransaction, TransactionType
from app.services.llm_service import get_user_long_context_llm
from app.services.plaid_service import PlaidService
from app.utils.document_converters import (
    create_document_chunks,
    generate_document_summary,
)

logger = logging.getLogger(__name__)


def get_current_timestamp() -> datetime:
    """Get the current timestamp with timezone for updated_at field."""
    return datetime.now(UTC)

logger = logging.getLogger(__name__)


class PlaidBaseIndexer:
    """
    Base class for all Plaid-powered bank connectors.

    Subclasses should define:
    - connector_name: Human-readable name (e.g., "Chase Bank")
    - institution_id: Plaid institution ID (e.g., "ins_3" for Chase)
    """

    connector_name: str = "Bank"
    institution_id: str | None = None  # Plaid institution ID

    def __init__(self):
        """Initialize Plaid service."""
        self.plaid_service = PlaidService()

    async def index_transactions(
        self,
        session: AsyncSession,
        connector: SearchSourceConnector,
        user_id: str,
        days_back: int = 90,
    ) -> dict[str, Any]:
        """
        Fetch and index transactions, account balances, and investment holdings from Plaid.

        Args:
            session: Database session
            connector: Search source connector with Plaid access token
            user_id: User ID
            days_back: Number of days to fetch (default 90)

        Returns:
            Indexing result with transaction count and documents created
        """
        try:
            # Get access token from connector config
            access_token = connector.config.get("access_token")
            if not access_token:
                raise ValueError(f"No access token found for {self.connector_name}")

            # Fetch accounts first (for balances and account info)
            accounts = await self.plaid_service.get_accounts(access_token)
            account_map = {acc["account_id"]: acc for acc in accounts}

            documents_created = 0

            # 1. Create account summary document with current balances
            account_doc_created = await self._create_account_summary_document(
                session=session,
                accounts=accounts,
                search_space_id=connector.search_space_id,
                user_id=user_id,
                connector_id=connector.id,
            )
            if account_doc_created:
                documents_created += 1

            # 2. Try to fetch investment holdings (if supported by the institution)
            holdings_data = await self.plaid_service.get_investment_holdings(
                access_token
            )
            if holdings_data["holdings"]:
                holdings_doc_created = await self._create_investment_holdings_document(
                    session=session,
                    holdings_data=holdings_data,
                    search_space_id=connector.search_space_id,
                    user_id=user_id,
                    connector_id=connector.id,
                )
                if holdings_doc_created:
                    documents_created += 1

            # 3. Fetch regular transactions from Plaid
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            transactions = await self.plaid_service.get_transactions(
                access_token=access_token,
                start_date=start_date,
                end_date=end_date,
            )

            transaction_count = len(transactions) if transactions else 0

            if transactions:
                # Group transactions by month for better organization
                transactions_by_month = self._group_by_month(transactions)

                for month_key, month_transactions in transactions_by_month.items():
                    # Convert Plaid transactions to BankTransaction format
                    bank_transactions = []
                    for txn in month_transactions:
                        account = account_map.get(txn["account_id"], {})
                        bank_transactions.append(
                            self._convert_plaid_transaction(txn, account)
                        )

                    # Create document for this month's transactions
                    doc_created = await self._create_transaction_document(
                        session=session,
                        transactions=bank_transactions,
                        month_key=month_key,
                        search_space_id=connector.search_space_id,
                        user_id=user_id,
                        connector_id=connector.id,
                    )

                    if doc_created:
                        documents_created += 1

            return {
                "transaction_count": transaction_count,
                "documents_created": documents_created,
                "accounts_indexed": len(accounts),
                "holdings_indexed": len(holdings_data.get("holdings", [])),
            }

        except Exception as e:
            logger.error(f"Error indexing {self.connector_name} data: {e}")
            raise

    def _group_by_month(
        self, transactions: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group transactions by month (YYYY-MM)."""
        grouped = {}
        for txn in transactions:
            date_str = str(txn["date"])  # Format: YYYY-MM-DD
            month_key = date_str[:7]  # Get YYYY-MM
            if month_key not in grouped:
                grouped[month_key] = []
            grouped[month_key].append(txn)
        return grouped

    def _convert_plaid_transaction(
        self, plaid_txn: dict[str, Any], account: dict[str, Any]
    ) -> BankTransaction:
        """Convert Plaid transaction format to BankTransaction."""
        # Plaid amounts are positive for outflows (expenses), negative for inflows (income)
        # We'll keep that convention
        amount = float(plaid_txn["amount"])

        # Determine transaction type from category
        if amount > 0:
            trans_type = TransactionType.PURCHASE
        elif amount < 0:
            trans_type = TransactionType.DEPOSIT
        else:
            trans_type = TransactionType.OTHER

        # Parse date
        txn_date = datetime.fromisoformat(str(plaid_txn["date"]))

        return BankTransaction(
            date=txn_date,
            description=plaid_txn["name"],
            amount=amount,
            transaction_type=trans_type,
            category=plaid_txn.get("category", []),
            balance=None,  # Plaid doesn't provide running balance in transactions
            raw_data={
                "plaid_transaction_id": plaid_txn["transaction_id"],
                "account_id": plaid_txn["account_id"],
                "account_name": account.get("name"),
                "merchant_name": plaid_txn.get("merchant_name"),
                "pending": plaid_txn.get("pending", False),
                "payment_channel": plaid_txn.get("payment_channel"),
            },
        )

    async def _create_transaction_document(
        self,
        session: AsyncSession,
        transactions: list[BankTransaction],
        month_key: str,
        search_space_id: int,
        user_id: str,
        connector_id: int,
    ) -> bool:
        """
        Create a document from transactions.

        Args:
            session: Database session
            transactions: List of BankTransaction objects
            month_key: Month identifier (YYYY-MM)
            search_space_id: Search space ID
            user_id: User ID
            connector_id: Connector ID

        Returns:
            True if document was created
        """
        # Build markdown content
        markdown_parts = []
        markdown_parts.append(
            f"# {self.connector_name} - Transactions for {month_key}\n\n"
        )
        markdown_parts.append(f"**Total Transactions:** {len(transactions)}\n\n")

        # Calculate totals
        total_spent = sum(t.amount for t in transactions if t.amount > 0)
        total_received = sum(abs(t.amount) for t in transactions if t.amount < 0)

        markdown_parts.append(f"**Total Spent:** ${total_spent:.2f}\n")
        markdown_parts.append(f"**Total Received:** ${total_received:.2f}\n\n")

        # Add transactions
        markdown_parts.append("## Transactions\n\n")
        for txn in sorted(transactions, key=lambda t: t.date):
            date_str = txn.date.strftime("%Y-%m-%d")
            amount_str = f"${abs(txn.amount):.2f}"
            if txn.amount > 0:
                amount_str = f"-{amount_str}"  # Expense
            else:
                amount_str = f"+{amount_str}"  # Income

            category_str = (
                " | ".join(txn.category) if txn.category else txn.transaction_type
            )
            markdown_parts.append(
                f"- **{date_str}** - {txn.description}: {amount_str} ({category_str})\n"
            )

        markdown_content = "".join(markdown_parts)

        # Check for duplicate
        from hashlib import sha256

        content_hash = sha256(markdown_content.encode()).hexdigest()

        stmt = select(Document).where(Document.content_hash == content_hash)
        result = await session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            logger.info(
                f"Document for {self.connector_name} {month_key} already exists"
            )
            return False

        # Get LLM for embeddings
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

        # Generate summary and embedding
        summary, summary_embedding = await generate_document_summary(
            markdown_content,
            user_llm,
            {
                "connector": self.connector_name,
                "month": month_key,
                "transaction_count": len(transactions),
            },
        )

        # Create chunks
        chunks = await create_document_chunks(content=markdown_content)

        # Create document
        doc = Document(
            search_space_id=search_space_id,
            title=f"{self.connector_name} - {month_key}",
            document_type=DocumentType.FILE,  # Use FILE type so it's searchable
            document_metadata={
                "connector_id": connector_id,
                "connector_name": self.connector_name,
                "month": month_key,
                "transaction_count": len(transactions),
                "total_spent": total_spent,
                "total_received": total_received,
                "is_plaid_document": True,
            },
            content=markdown_content,
            content_hash=content_hash,
            unique_identifier_hash=content_hash,  # Use content hash as unique ID
            embedding=summary_embedding,
            chunks=chunks,
            updated_at=get_current_timestamp(),
        )

        session.add(doc)
        await session.commit()

        logger.info(
            f"Created document for {self.connector_name} {month_key} with {len(chunks)} chunks"
        )
        return True

    async def _create_account_summary_document(
        self,
        session: AsyncSession,
        accounts: list[dict[str, Any]],
        search_space_id: int,
        user_id: str,
        connector_id: int,
    ) -> bool:
        """
        Create a searchable document summarizing all account balances.

        Args:
            session: Database session
            accounts: List of account dictionaries from Plaid
            search_space_id: Search space ID
            user_id: User ID
            connector_id: Connector ID

        Returns:
            True if document was created
        """
        if not accounts:
            return False

        # Build markdown content
        markdown_parts = []
        markdown_parts.append(f"# {self.connector_name} - Account Summary\n\n")
        markdown_parts.append(
            f"**Last Updated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        )
        markdown_parts.append(f"**Total Accounts:** {len(accounts)}\n\n")

        # Calculate total across all accounts
        total_balance = sum(
            acc["balance"]["current"] for acc in accounts if acc["balance"]["current"]
        )
        markdown_parts.append(f"**Total Balance:** ${total_balance:,.2f}\n\n")

        # Group by account type
        accounts_by_type = {}
        for acc in accounts:
            acc_type = str(acc["type"]) if acc["type"] else "unknown"
            if acc_type not in accounts_by_type:
                accounts_by_type[acc_type] = []
            accounts_by_type[acc_type].append(acc)

        # Add accounts grouped by type
        for acc_type, type_accounts in accounts_by_type.items():
            markdown_parts.append(f"## {acc_type.replace('_', ' ').title()} Accounts\n\n")

            for acc in type_accounts:
                account_name = acc.get("official_name") or acc["name"]
                current_balance = acc["balance"]["current"]
                available_balance = acc["balance"].get("available")
                subtype = acc.get("subtype", "").replace("_", " ").title()

                markdown_parts.append(f"### {account_name}\n\n")
                markdown_parts.append(f"- **Type:** {subtype}\n")
                markdown_parts.append(
                    f"- **Current Balance:** ${current_balance:,.2f}\n"
                )

                if available_balance is not None:
                    markdown_parts.append(
                        f"- **Available Balance:** ${available_balance:,.2f}\n"
                    )

                if acc["balance"].get("limit"):
                    markdown_parts.append(
                        f"- **Credit Limit:** ${acc['balance']['limit']:,.2f}\n"
                    )

                markdown_parts.append("\n")

        markdown_content = "".join(markdown_parts)

        # Generate unique identifier
        from hashlib import sha256

        # Use current date + connector ID for uniqueness (updates daily)
        unique_id = f"{connector_id}_accounts_{datetime.now(UTC).date()}"
        content_hash = sha256(unique_id.encode()).hexdigest()

        # Check for existing document (delete old one to update)
        stmt = select(Document).where(
            Document.search_space_id == search_space_id,
            Document.document_metadata["connector_id"].as_string() == str(connector_id),
            Document.document_metadata["document_subtype"].as_string()
            == "account_summary",
        )
        result = await session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            await session.delete(existing_doc)
            await session.commit()
            logger.info(
                f"Deleted old account summary for {self.connector_name} before creating new one"
            )

        # Get LLM for embeddings
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

        # Generate summary and embedding
        summary, summary_embedding = await generate_document_summary(
            markdown_content,
            user_llm,
            {
                "connector": self.connector_name,
                "total_balance": total_balance,
                "account_count": len(accounts),
            },
        )

        # Create chunks
        chunks = await create_document_chunks(content=markdown_content)

        # Create document
        doc = Document(
            search_space_id=search_space_id,
            title=f"{self.connector_name} - Account Summary",
            document_type=DocumentType.FILE,
            document_metadata={
                "connector_id": connector_id,
                "connector_name": self.connector_name,
                "document_subtype": "account_summary",
                "total_balance": total_balance,
                "account_count": len(accounts),
                "is_plaid_document": True,
            },
            content=markdown_content,
            content_hash=content_hash,
            unique_identifier_hash=content_hash,
            embedding=summary_embedding,
            chunks=chunks,
            updated_at=get_current_timestamp(),
        )

        session.add(doc)
        await session.commit()

        logger.info(
            f"Created account summary for {self.connector_name} with {len(accounts)} accounts"
        )
        return True

    async def _create_investment_holdings_document(
        self,
        session: AsyncSession,
        holdings_data: dict[str, Any],
        search_space_id: int,
        user_id: str,
        connector_id: int,
    ) -> bool:
        """
        Create a searchable document for investment holdings (stocks, bonds, funds).

        Args:
            session: Database session
            holdings_data: Holdings data from Plaid (accounts, holdings, securities)
            search_space_id: Search space ID
            user_id: User ID
            connector_id: Connector ID

        Returns:
            True if document was created
        """
        holdings = holdings_data.get("holdings", [])
        securities = holdings_data.get("securities", [])
        accounts = holdings_data.get("accounts", [])

        if not holdings:
            return False

        # Build security lookup map
        security_map = {sec["security_id"]: sec for sec in securities}

        # Build markdown content
        markdown_parts = []
        markdown_parts.append(f"# {self.connector_name} - Investment Holdings\n\n")
        markdown_parts.append(
            f"**Last Updated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        )

        # Calculate total portfolio value
        total_value = sum(h["institution_value"] for h in holdings)
        markdown_parts.append(f"**Total Portfolio Value:** ${total_value:,.2f}\n\n")
        markdown_parts.append(f"**Total Positions:** {len(holdings)}\n\n")

        # Group holdings by account
        holdings_by_account = {}
        for holding in holdings:
            acc_id = holding["account_id"]
            if acc_id not in holdings_by_account:
                holdings_by_account[acc_id] = []
            holdings_by_account[acc_id].append(holding)

        # Add holdings grouped by account
        for acc_id, account_holdings in holdings_by_account.items():
            # Find account info
            account = next((a for a in accounts if a["account_id"] == acc_id), None)
            account_name = account["name"] if account else acc_id

            markdown_parts.append(f"## {account_name}\n\n")

            account_value = sum(h["institution_value"] for h in account_holdings)
            markdown_parts.append(f"**Account Value:** ${account_value:,.2f}\n\n")

            markdown_parts.append("### Holdings:\n\n")

            # Sort by value (largest first)
            sorted_holdings = sorted(
                account_holdings, key=lambda h: h["institution_value"], reverse=True
            )

            for holding in sorted_holdings:
                security = security_map.get(holding["security_id"], {})

                security_name = security.get("name", "Unknown Security")
                ticker = security.get("ticker_symbol")
                security_type = security.get("type", "").replace("_", " ").title()

                quantity = holding["quantity"]
                price = holding["institution_price"]
                value = holding["institution_value"]
                cost_basis = holding.get("cost_basis")

                # Calculate gain/loss if cost basis available
                gain_loss_text = ""
                if cost_basis and cost_basis > 0:
                    gain_loss = value - cost_basis
                    gain_loss_pct = (gain_loss / cost_basis) * 100
                    sign = "+" if gain_loss >= 0 else ""
                    gain_loss_text = f" | **Gain/Loss:** {sign}${gain_loss:,.2f} ({sign}{gain_loss_pct:.2f}%)"

                ticker_text = f" ({ticker})" if ticker else ""

                markdown_parts.append(f"#### {security_name}{ticker_text}\n\n")
                markdown_parts.append(f"- **Type:** {security_type}\n")
                markdown_parts.append(f"- **Quantity:** {quantity:,.4f} shares\n")
                markdown_parts.append(f"- **Price:** ${price:,.2f} per share\n")
                markdown_parts.append(f"- **Value:** ${value:,.2f}{gain_loss_text}\n")
                markdown_parts.append("\n")

        markdown_content = "".join(markdown_parts)

        # Generate unique identifier
        from hashlib import sha256

        # Use current date + connector ID for uniqueness (updates daily)
        unique_id = f"{connector_id}_holdings_{datetime.now(UTC).date()}"
        content_hash = sha256(unique_id.encode()).hexdigest()

        # Check for existing document (delete old one to update)
        stmt = select(Document).where(
            Document.search_space_id == search_space_id,
            Document.document_metadata["connector_id"].as_string() == str(connector_id),
            Document.document_metadata["document_subtype"].as_string()
            == "investment_holdings",
        )
        result = await session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            await session.delete(existing_doc)
            await session.commit()
            logger.info(
                f"Deleted old holdings document for {self.connector_name} before creating new one"
            )

        # Get LLM for embeddings
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)

        # Generate summary and embedding
        summary, summary_embedding = await generate_document_summary(
            markdown_content,
            user_llm,
            {
                "connector": self.connector_name,
                "total_value": total_value,
                "positions_count": len(holdings),
            },
        )

        # Create chunks
        chunks = await create_document_chunks(content=markdown_content)

        # Create document
        doc = Document(
            search_space_id=search_space_id,
            title=f"{self.connector_name} - Investment Holdings",
            document_type=DocumentType.FILE,
            document_metadata={
                "connector_id": connector_id,
                "connector_name": self.connector_name,
                "document_subtype": "investment_holdings",
                "total_value": total_value,
                "positions_count": len(holdings),
                "is_plaid_document": True,
            },
            content=markdown_content,
            content_hash=content_hash,
            unique_identifier_hash=content_hash,
            embedding=summary_embedding,
            chunks=chunks,
            updated_at=get_current_timestamp(),
        )

        session.add(doc)
        await session.commit()

        logger.info(
            f"Created investment holdings document for {self.connector_name} with {len(holdings)} positions"
        )
        return True
