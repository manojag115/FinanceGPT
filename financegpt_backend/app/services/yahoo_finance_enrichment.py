"""Yahoo Finance enrichment service for investment holdings."""
import asyncio
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

# Disable SSL verification for curl_cffi before importing yfinance
# Set environment variables that curl_cffi checks
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["SSL_CERT_FILE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

import yfinance as yf
from app.schemas.investments import (
    AssetType,
    InvestmentHoldingEnriched,
)

# Try to patch yfinance's session to disable SSL verification
try:
    from curl_cffi import requests as curl_requests
    
    # Create a custom session with SSL verification disabled
    _original_session_init = curl_requests.Session.__init__
    
    def _patched_session_init(self, *args, **kwargs):
        _original_session_init(self, *args, **kwargs)
        # Disable SSL verification
        self.verify = False
    
    curl_requests.Session.__init__ = _patched_session_init
except Exception:
    pass  # If patching fails, continue anyway

yf.set_tz_cache_location("/tmp/yfinance-tz-cache")  # Use temp dir for cache


class YahooFinanceEnrichmentService:
    """Service to enrich investment holdings with Yahoo Finance data."""
    
    @staticmethod
    def _map_quote_type_to_asset_type(quote_type: str) -> AssetType:
        """Map Yahoo Finance quoteType to our AssetType enum."""
        mapping = {
            "EQUITY": AssetType.STOCK,
            "ETF": AssetType.ETF,
            "MUTUALFUND": AssetType.MUTUAL_FUND,
            "CRYPTOCURRENCY": AssetType.CRYPTO,
            "INDEX": AssetType.OTHER,
        }
        return mapping.get(quote_type, AssetType.STOCK)
    
    @staticmethod
    async def enrich_holding(
        symbol: str,
        quantity: Decimal,
        cost_basis: Decimal,
        average_cost_basis: Decimal | None = None,
    ) -> InvestmentHoldingEnriched:
        """
        Enrich a holding with real-time data from Yahoo Finance.
        
        Args:
            symbol: Stock ticker symbol
            quantity: Number of shares
            cost_basis: Total cost basis
            average_cost_basis: Average cost per share
            
        Returns:
            Enriched holding with current prices, performance, and metadata
        """
        # Run Yahoo Finance API in thread pool (it's blocking)
        loop = asyncio.get_event_loop()
        # Let yfinance handle the session internally with curl_cffi
        ticker = await loop.run_in_executor(None, lambda: yf.Ticker(symbol))
        
        try:
            # Get current quote data
            info: dict[str, Any] = await loop.run_in_executor(None, lambda: ticker.info)
            
            # Extract price data
            current_price = Decimal(str(info.get("currentPrice") or info.get("regularMarketPrice", 0)))
            previous_close = Decimal(str(info.get("previousClose", current_price)))
            
            # Calculate market value and performance
            market_value = quantity * current_price
            day_change = current_price - previous_close
            day_change_pct = (day_change / previous_close * 100) if previous_close > 0 else Decimal("0")
            
            unrealized_gain_loss = market_value - cost_basis
            unrealized_gain_loss_pct = (unrealized_gain_loss / cost_basis * 100) if cost_basis > 0 else Decimal("0")
            
            # Extract classification data
            quote_type = info.get("quoteType", "EQUITY")
            asset_type = YahooFinanceEnrichmentService._map_quote_type_to_asset_type(quote_type)
            
            sector = info.get("sector")
            industry = info.get("industry")
            
            # Infer geographic region from exchange
            exchange = info.get("exchange", "")
            if exchange in ["NMS", "NYQ", "PCX", "NAS"]:  # US exchanges
                geographic_region = "US"
            elif exchange in ["TOR"]:
                geographic_region = "Canada"
            elif exchange in ["LON"]:
                geographic_region = "UK"
            else:
                geographic_region = info.get("country", "Unknown")
            
            return InvestmentHoldingEnriched(
                symbol=symbol,
                description=info.get("longName") or info.get("shortName"),
                quantity=quantity,
                cost_basis=cost_basis,
                average_cost_basis=average_cost_basis or (cost_basis / quantity if quantity > 0 else Decimal("0")),
                current_price=current_price,
                market_value=market_value,
                previous_close=previous_close,
                day_change=day_change,
                day_change_pct=day_change_pct,
                unrealized_gain_loss=unrealized_gain_loss,
                unrealized_gain_loss_pct=unrealized_gain_loss_pct,
                asset_type=asset_type,
                sector=sector,
                industry=industry,
                geographic_region=geographic_region,
                price_as_of_timestamp=datetime.now(),
                extraction_confidence=Decimal("0.95"),  # High confidence for API data
            )
            
        except (KeyError, ValueError, TypeError) as e:
            # Fallback with minimal data if API fails
            return InvestmentHoldingEnriched(
                symbol=symbol,
                description=None,
                quantity=quantity,
                cost_basis=cost_basis,
                average_cost_basis=average_cost_basis,
                current_price=None,
                market_value=None,
                extraction_confidence=Decimal("0.0"),  # Low confidence when enrichment fails
            )
    
    @staticmethod
    async def batch_enrich_holdings(
        holdings: list[tuple[str, Decimal, Decimal, Decimal | None]]
    ) -> list[InvestmentHoldingEnriched]:
        """
        Enrich multiple holdings in parallel.
        
        Args:
            holdings: List of (symbol, quantity, cost_basis, average_cost_basis) tuples
            
        Returns:
            List of enriched holdings
        """
        tasks = [
            YahooFinanceEnrichmentService.enrich_holding(symbol, qty, cost, avg_cost)
            for symbol, qty, cost, avg_cost in holdings
        ]
        return await asyncio.gather(*tasks)
    
    @staticmethod
    async def refresh_holding_prices(
        holdings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Refresh just the price data for existing holdings.
        
        Args:
            holdings: List of holding dicts with symbol and quantity
            
        Returns:
            Updated holdings with latest prices
        """
        updated_holdings = []
        
        for holding in holdings:
            symbol = holding["symbol"]
            quantity = Decimal(str(holding["quantity"]))
            
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(None, yf.Ticker, symbol)
            
            try:
                info: dict[str, Any] = await loop.run_in_executor(None, lambda: ticker.info)
                current_price = Decimal(str(info.get("currentPrice") or info.get("regularMarketPrice", 0)))
                previous_close = Decimal(str(info.get("previousClose", current_price)))
                
                holding["current_price"] = current_price
                holding["market_value"] = quantity * current_price
                holding["day_change"] = current_price - previous_close
                holding["day_change_pct"] = (holding["day_change"] / previous_close * 100) if previous_close > 0 else Decimal("0")
                holding["price_as_of_timestamp"] = datetime.now()
                
            except Exception:
                # Keep existing data if refresh fails
                pass
            
            updated_holdings.append(holding)
        
        return updated_holdings
