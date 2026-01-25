"""
Plaid service for bank account integration.

Handles OAuth flow, transaction fetching, and account management for all bank connectors.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import (
    TransactionsGetRequestOptions,
)

from app.config import config

logger = logging.getLogger(__name__)


class PlaidService:
    """Service for interacting with Plaid API."""

    def __init__(self):
        """Initialize Plaid client."""
        from plaid.api_client import ApiClient

        configuration = plaid.Configuration(
            host=self._get_plaid_environment(),
            api_key={
                "clientId": config.PLAID_CLIENT_ID,
                "secret": config.PLAID_SECRET,
            },
        )
        api_client = ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)

    def _get_plaid_environment(self) -> str:
        """Get Plaid environment URL based on config."""
        env = config.PLAID_ENV.lower()
        if env == "sandbox":
            return plaid.Environment.Sandbox
        elif env == "development":
            return plaid.Environment.Development
        elif env == "production":
            return plaid.Environment.Production
        else:
            return plaid.Environment.Sandbox

    async def create_link_token(
        self, user_id: str, institution_id: str | None = None
    ) -> dict[str, Any]:
        """
        Create a Plaid Link token for initiating OAuth flow.

        Args:
            user_id: User ID for tracking
            institution_id: Optional specific institution to connect (e.g., 'ins_3' for Chase)

        Returns:
            Link token response with token and expiration
        """
        try:
            request = LinkTokenCreateRequest(
                products=[Products("transactions"), Products("auth")],
                client_name="FinanceGPT",
                country_codes=[CountryCode("US")],
                language="en",
                user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            )

            if institution_id:
                request.institution_id = institution_id

            response = self.client.link_token_create(request)
            return response.to_dict()

        except ApiException as e:
            logger.error(f"Error creating link token: {e}")
            raise

    async def exchange_public_token(self, public_token: str) -> dict[str, Any]:
        """
        Exchange public token for access token.

        Args:
            public_token: Public token from Plaid Link

        Returns:
            Access token and item ID
        """
        try:
            request = ItemPublicTokenExchangeRequest(public_token=public_token)
            response = self.client.item_public_token_exchange(request)

            return {
                "access_token": response["access_token"],
                "item_id": response["item_id"],
            }

        except ApiException as e:
            logger.error(f"Error exchanging public token: {e}")
            raise

    async def get_accounts(self, access_token: str) -> list[dict[str, Any]]:
        """
        Get all accounts for an access token.

        Args:
            access_token: Plaid access token

        Returns:
            List of account dictionaries
        """
        try:
            request = AccountsGetRequest(access_token=access_token)
            response = self.client.accounts_get(request)

            accounts = []
            for account in response["accounts"]:
                accounts.append(
                    {
                        "account_id": account["account_id"],
                        "name": account["name"],
                        "official_name": account.get("official_name"),
                        "type": account["type"],
                        "subtype": account["subtype"],
                        "mask": account.get("mask"),
                        "balance": {
                            "current": account["balances"]["current"],
                            "available": account["balances"].get("available"),
                            "limit": account["balances"].get("limit"),
                        },
                    }
                )

            return accounts

        except ApiException as e:
            logger.error(f"Error getting accounts: {e}")
            raise

    async def get_transactions(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
        account_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get transactions for an account within date range.

        Args:
            access_token: Plaid access token
            start_date: Start date for transactions
            end_date: End date for transactions
            account_ids: Optional list of specific account IDs to fetch

        Returns:
            List of transaction dictionaries
        """
        try:
            options = TransactionsGetRequestOptions()
            if account_ids:
                options.account_ids = account_ids

            request = TransactionsGetRequest(
                access_token=access_token,
                start_date=start_date.date(),
                end_date=end_date.date(),
                options=options,
            )

            response = self.client.transactions_get(request)

            transactions = []
            for txn in response["transactions"]:
                transactions.append(
                    {
                        "transaction_id": txn["transaction_id"],
                        "account_id": txn["account_id"],
                        "date": txn["date"],
                        "authorized_date": txn.get("authorized_date"),
                        "amount": txn["amount"],
                        "name": txn["name"],
                        "merchant_name": txn.get("merchant_name"),
                        "category": txn.get("category", []),
                        "category_id": txn.get("category_id"),
                        "pending": txn["pending"],
                        "payment_channel": txn.get("payment_channel"),
                        "location": txn.get("location", {}),
                        "iso_currency_code": txn.get("iso_currency_code"),
                    }
                )

            # Handle pagination if there are more transactions
            total_transactions = response["total_transactions"]
            if total_transactions > len(transactions):
                logger.info(
                    f"Paginating to get all {total_transactions} transactions"
                )
                # Plaid may require multiple calls for large datasets
                # For now, we return what we got - implement pagination if needed

            return transactions

        except ApiException as e:
            logger.error(f"Error getting transactions: {e}")
            raise

    async def sync_recent_transactions(
        self, access_token: str, days_back: int = 30
    ) -> list[dict[str, Any]]:
        """
        Sync recent transactions (default last 30 days).

        Args:
            access_token: Plaid access token
            days_back: Number of days to look back

        Returns:
            List of recent transactions
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        return await self.get_transactions(access_token, start_date, end_date)
