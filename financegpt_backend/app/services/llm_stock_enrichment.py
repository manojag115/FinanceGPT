"""LLM-based stock price enrichment service using web search."""
import logging
import os
import re
import ssl
from decimal import Decimal

# Monkey-patch SSL to disable certificate verification globally
# This is needed for corporate proxies with self-signed certificates
_original_create_default_context = ssl.create_default_context

def _create_unverified_context(*args, **kwargs):
    context = _original_create_default_context(*args, **kwargs)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

ssl.create_default_context = _create_unverified_context
ssl._create_default_https_context = _create_unverified_context

from linkup import LinkupClient

from app.schemas.investments import AssetType, InvestmentHoldingEnriched

logger = logging.getLogger(__name__)


class LLMStockEnrichmentService:
    """Service to enrich investment holdings using Linkup web search."""
    
    @staticmethod
    async def enrich_holding(
        symbol: str,
        quantity: Decimal,
        cost_basis: Decimal,
        average_cost_basis: Decimal | None = None,
    ) -> InvestmentHoldingEnriched:
        """
        Enrich a holding with current data using Linkup web search.
        
        Args:
            symbol: Stock ticker symbol
            quantity: Number of shares
            cost_basis: Total cost basis
            average_cost_basis: Average cost per share
            
        Returns:
            Enriched holding with current prices and performance
        """
        # Ensure all inputs are Decimal type
        quantity = Decimal(str(quantity))
        cost_basis = Decimal(str(cost_basis))
        if average_cost_basis is not None:
            average_cost_basis = Decimal(str(average_cost_basis))
        
        try:
            # Get Linkup API key from environment
            api_key = os.getenv("LINKUP_API_KEY")
            if not api_key:
                raise ValueError("LINKUP_API_KEY not set in environment")
            
            # Initialize Linkup client (SSL verification disabled via monkey-patch above)
            client = LinkupClient(api_key=api_key)
            
            # Search for current stock price - use sourcedAnswer for better extraction
            query = f"Current stock price of {symbol} ticker symbol. Provide exact numeric price value."
            
            # Perform search with sourcedAnswer to get structured response
            response = client.search(
                query=query,
                depth="standard",
                output_type="sourcedAnswer"  # Get structured answer instead of raw results
            )
            
            # Extract the answer text
            answer_text = ""
            if hasattr(response, 'answer'):
                answer_text = str(response.answer)
            elif hasattr(response, 'text'):
                answer_text = str(response.text)
            else:
                answer_text = str(response)
            
            logger.info(f"Linkup answer for {symbol}: {answer_text}")
            
            # Try to extract current price using improved regex
            # Look for patterns like "$123.45", "123.45 USD", "price: 123.45", etc.
            price_patterns = [
                r'\$(\d+\.?\d*)',  # $123.45
                r'(\d+\.\d{2})\s*(?:USD|dollars?)',  # 123.45 USD
                r'price[:\s]+\$?(\d+\.\d{2})',  # price: $123.45 or price 123.45
                r'(\d{1,4}\.\d{2})',  # Any number with 2 decimals (last resort)
            ]
            
            current_price = Decimal("0")
            for pattern in price_patterns:
                matches = re.findall(pattern, answer_text, re.IGNORECASE)
                if matches:
                    # Take the first match and try to validate it's reasonable
                    price_candidate = Decimal(matches[0])
                    # Basic validation: stock prices typically between $0.01 and $10,000
                    if Decimal("0.01") <= price_candidate <= Decimal("10000"):
                        current_price = price_candidate
                        break
            
            if current_price == 0:
                raise ValueError(f"Could not extract valid price from Linkup answer: {answer_text}")
            
            # For now, use current price as previous close (no day change data from search)
            previous_close = current_price
            
            # Calculate market value and performance
            market_value = quantity * current_price
            day_change = current_price - previous_close
            day_change_pct = (day_change / previous_close * 100) if previous_close > 0 else Decimal("0")
            
            unrealized_gain_loss = market_value - cost_basis
            unrealized_gain_loss_pct = (unrealized_gain_loss / cost_basis * 100) if cost_basis > 0 else Decimal("0")
            
            return InvestmentHoldingEnriched(
                symbol=symbol,
                description=symbol,
                quantity=quantity,
                cost_basis=cost_basis,
                average_cost_basis=average_cost_basis or (cost_basis / quantity if quantity > 0 else Decimal("0")),
                current_price=current_price,
                market_value=market_value,
                day_change=day_change,
                day_change_pct=day_change_pct,
                unrealized_gain_loss=unrealized_gain_loss,
                unrealized_gain_loss_pct=unrealized_gain_loss_pct,
                sector=None,
                industry=None,
                geographic_region="US",
                asset_type=AssetType.STOCK,
            )
            
        except Exception as e:
            logger.error(f"Linkup enrichment failed for {symbol}: {e}")
            # Return basic data without enrichment
            market_value = cost_basis  # Use cost basis as fallback
            return InvestmentHoldingEnriched(
                symbol=symbol,
                description=symbol,
                quantity=quantity,
                cost_basis=cost_basis,
                average_cost_basis=average_cost_basis or (cost_basis / quantity if quantity > 0 else Decimal("0")),
                current_price=Decimal("0"),
                market_value=market_value,
                day_change=Decimal("0"),
                day_change_pct=Decimal("0"),
                unrealized_gain_loss=Decimal("0"),
                unrealized_gain_loss_pct=Decimal("0"),
                sector=None,
                industry=None,
                geographic_region="US",
                asset_type=AssetType.STOCK,
            )
