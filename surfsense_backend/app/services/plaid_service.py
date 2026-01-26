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
from plaid.model.investments_holdings_get_request import (
    InvestmentsHoldingsGetRequest,
)
from plaid.model.investments_transactions_get_request import (
    InvestmentsTransactionsGetRequest,
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
        env_map = {
            "sandbox": plaid.Environment.Sandbox,
            "development": plaid.Environment.Sandbox,  # Development uses Sandbox
            "production": plaid.Environment.Production,
        }
        return env_map.get(config.PLAID_ENV.lower(), plaid.Environment.Sandbox)

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
                products=[Products("transactions"), Products("auth"), Products("investments")],
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
            logger.error("Error creating link token: %s", e)
            raise

    async def create_update_link_token(
        self, user_id: str, access_token: str
    ) -> dict[str, Any]:
        """
        Create a Plaid Link token for updating an existing connection.
        
        This allows users to add/remove accounts or fix connection issues.

        Args:
            user_id: User ID for tracking
            access_token: Existing Plaid access token to update

        Returns:
            Link token response with token and expiration
        """
        try:
            request = LinkTokenCreateRequest(
                products=[Products("transactions"), Products("auth"), Products("investments")],
                client_name="FinanceGPT",
                country_codes=[CountryCode("US")],
                language="en",
                user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
                access_token=access_token,  # This enables update mode
            )

            response = self.client.link_token_create(request)
            return response.to_dict()

        except ApiException as e:
            logger.error("Error creating update link token: %s", e)
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
            logger.error("Error exchanging public token: %s", e)
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
                        "type": str(account["type"]) if account["type"] else None,
                        "subtype": str(account["subtype"]) if account["subtype"] else None,
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
            logger.error("Error getting accounts: %s", e)
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
                    "Paginating to get all %d transactions", total_transactions
                )
                # Plaid may require multiple calls for large datasets
                # For now, we return what we got - implement pagination if needed

            return transactions

        except ApiException as e:
            logger.error("Error getting transactions: %s", e)
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

    async def get_investment_holdings(
        self, access_token: str
    ) -> dict[str, Any]:
        """
        Get investment holdings (stocks, bonds, funds) for all investment accounts.

        Args:
            access_token: Plaid access token

        Returns:
            Dictionary with accounts, holdings, and securities information
        """
        try:
            request = InvestmentsHoldingsGetRequest(access_token=access_token)
            response = self.client.investments_holdings_get(request)

            # Parse response
            holdings_data = {
                "accounts": [],
                "holdings": [],
                "securities": [],
            }

            # Extract accounts
            for account in response.get("accounts", []):
                holdings_data["accounts"].append(
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

            # Extract holdings (positions)
            for holding in response.get("holdings", []):
                holdings_data["holdings"].append(
                    {
                        "account_id": holding["account_id"],
                        "security_id": holding["security_id"],
                        "quantity": holding["quantity"],
                        "institution_price": holding["institution_price"],
                        "institution_value": holding["institution_value"],
                        "cost_basis": holding.get("cost_basis"),
                        "iso_currency_code": holding.get("iso_currency_code"),
                    }
                )

            # Extract securities (stock/fund details)
            for security in response.get("securities", []):
                holdings_data["securities"].append(
                    {
                        "security_id": security["security_id"],
                        "name": security.get("name"),
                        "ticker_symbol": security.get("ticker_symbol"),
                        "type": security.get("type"),
                        "close_price": security.get("close_price"),
                        "close_price_as_of": security.get("close_price_as_of"),
                        "isin": security.get("isin"),
                        "cusip": security.get("cusip"),
                    }
                )

            return holdings_data

        except ApiException as e:
            # Check if it's a consent/permission issue (common for non-investment accounts)
            error_code = getattr(e, 'error_code', None) if hasattr(e, 'error_code') else None
            if error_code == 'ADDITIONAL_CONSENT_REQUIRED':
                logger.info(
                    "Investment holdings not available - account doesn't have investment product access (this is normal for checking/savings accounts)"
                )
            else:
                logger.error("Error getting investment holdings: %s", e)
            # Not all accounts support investments - return empty data
            return {"accounts": [], "holdings": [], "securities": []}

    async def get_investment_transactions(
        self,
        access_token: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get investment transactions (buys, sells, dividends, etc.).

        Args:
            access_token: Plaid access token
            start_date: Start date
            end_date: End date

        Returns:
            List of investment transaction dictionaries
        """
        try:
            request = InvestmentsTransactionsGetRequest(
                access_token=access_token,
                start_date=start_date.date(),
                end_date=end_date.date(),
            )

            response = self.client.investments_transactions_get(request)

            transactions = []
            for txn in response.get("investment_transactions", []):
                transactions.append(
                    {
                        "investment_transaction_id": txn["investment_transaction_id"],
                        "account_id": txn["account_id"],
                        "security_id": txn.get("security_id"),
                        "date": txn["date"],
                        "name": txn["name"],
                        "amount": txn["amount"],
                        "quantity": txn["quantity"],
                        "price": txn["price"],
                        "type": txn["type"],  # buy, sell, dividend, etc.
                        "subtype": txn.get("subtype"),
                        "iso_currency_code": txn.get("iso_currency_code"),
                    }
                )

            return transactions

        except ApiException as e:
            logger.error("Error getting investment transactions: %s", e)
            return []
