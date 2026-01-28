"""
Credit card rewards fetcher utility.

Fetches credit card rewards information from the web and extracts rewards structure using LLM.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType
from app.utils.credit_card_rewards_database import get_card_rewards, normalize_card_name

logger = logging.getLogger(__name__)


class CreditCardRewardsFetcher:
    """Fetches and caches credit card rewards information."""

    def __init__(self, llm_service):
        """
        Initialize the rewards fetcher.

        Args:
            llm_service: LLM service for extracting rewards structure
        """
        self.llm_service = llm_service

    async def fetch_rewards_structure(
        self,
        session: AsyncSession,
        card_name: str,
        search_space_id: int,
        user_id: str,
    ) -> dict[str, Any] | None:
        """
        Fetch credit card rewards structure from the web with caching.

        Args:
            session: Database session
            card_name: Credit card name (e.g., "Chase Sapphire Preferred")
            search_space_id: Search space ID for caching
            user_id: User ID

        Returns:
            Dictionary with rewards structure or None if failed
            Example: {
                "card_name": "Chase Sapphire Preferred",
                "rewards": {
                    "dining": 3.0,
                    "travel": 2.0,
                    "default": 1.0
                },
                "annual_fee": 95,
                "currency": "points",
                "fetched_at": "2026-01-27"
            }
        """
        # 1. Check database first (20+ popular cards)
        db_rewards = get_card_rewards(card_name)
        if db_rewards:
            logger.info(f"Using rewards database for {card_name}")
            db_rewards["fetched_at"] = datetime.now(UTC).strftime("%Y-%m-%d")
            db_rewards["source"] = "database"
            return db_rewards

        # 2. Check cache (valid for 7 days)
        cached = await self._get_cached_rewards(session, card_name, search_space_id)
        if cached:
            logger.info(f"Using cached rewards for {card_name}")
            return cached

        # 3. Fetch from web as fallback (for cards not in our database)
        logger.info(f"Card not in database, fetching rewards for {card_name} from web")
        web_content = await self._search_and_fetch_card_info(card_name)

        if not web_content:
            logger.warning(f"Failed to fetch web content for {card_name}")
            return None

        # Extract rewards structure using LLM
        rewards_structure = await self._extract_rewards_with_llm(card_name, web_content)

        if rewards_structure:
            # Cache the result
            await self._cache_rewards(
                session=session,
                card_name=card_name,
                rewards_structure=rewards_structure,
                search_space_id=search_space_id,
                user_id=user_id,
            )

        return rewards_structure

    async def _get_cached_rewards(
        self,
        session: AsyncSession,
        card_name: str,
        search_space_id: int,
    ) -> dict[str, Any] | None:
        """Check if rewards data is cached and still valid (7 days)."""
        # Look for cached document
        stmt = select(Document).where(
            Document.search_space_id == search_space_id,
            Document.document_type == DocumentType.FILE,
            Document.title == f"Credit Card Rewards: {card_name}",
        )

        result = await session.execute(stmt)
        cached_doc = result.scalar_one_or_none()

        if not cached_doc:
            return None

        # Check if cache is still valid (7 days)
        cache_age = datetime.now(UTC) - cached_doc.created_at
        if cache_age > timedelta(days=7):
            logger.info(f"Cache expired for {card_name} (age: {cache_age.days} days)")
            return None

        # Extract rewards from metadata
        rewards_data = cached_doc.metadata.get("rewards_structure")
        if rewards_data:
            rewards_data["fetched_at"] = cached_doc.created_at.strftime("%Y-%m-%d")

        return rewards_data

    async def _search_and_fetch_card_info(self, card_name: str) -> str | None:
        """
        Search for credit card rewards information and fetch webpage content.

        Args:
            card_name: Credit card name

        Returns:
            Webpage content as text or None if failed
        """
        # Strategy: Use Google search to find the best result, then scrape that page
        search_query = f"{card_name} credit card rewards categories 2026"
        
        try:
            # Step 1: Perform Google search to find the best page
            google_search_url = "https://www.google.com/search"
            params = {
                "q": search_query,
                "num": 3,  # Get top 3 results
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                # Search Google
                search_response = await client.get(
                    google_search_url, 
                    params=params,
                    headers=headers
                )
                
                if search_response.status_code != 200:
                    logger.warning(f"Google search failed with status {search_response.status_code}")
                    return None
                
                # Parse search results to extract URLs
                # Simple regex to find result URLs (not perfect but works)
                import re
                url_pattern = r'<a href="(/url\?q=https?://[^&]+)&amp;'
                matches = re.findall(url_pattern, search_response.text)
                
                # Extract clean URLs from Google's /url?q= format
                result_urls = []
                for match in matches[:3]:  # Top 3 results
                    # Extract actual URL from /url?q=ACTUAL_URL&...
                    clean_url = match.replace("/url?q=", "").split("&")[0]
                    # Prioritize known reliable sources
                    if any(domain in clean_url for domain in ["nerdwallet.com", "thepointsguy.com", "bankrate.com", "creditcards.com"]):
                        result_urls.insert(0, clean_url)  # Put trusted sources first
                    else:
                        result_urls.append(clean_url)
                
                logger.info(f"Found {len(result_urls)} URLs from Google for {card_name}")
                
                # Step 2: Try to fetch content from the top results
                for url in result_urls[:3]:
                    try:
                        logger.info(f"Attempting to fetch {url}")
                        page_response = await client.get(url, headers=headers, timeout=10.0)
                        
                        if page_response.status_code == 200:
                            # Extract text from HTML
                            html_content = page_response.text
                            
                            # Simple text extraction (remove HTML tags)
                            # This is basic - in production use BeautifulSoup
                            text_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
                            text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL)
                            text_content = re.sub(r'<[^>]+>', ' ', text_content)
                            text_content = re.sub(r'\s+', ' ', text_content)
                            
                            # Take first 8000 chars (enough for rewards info)
                            clean_content = text_content[:8000]
                            
                            logger.info(f"Successfully fetched {len(clean_content)} chars from {url}")
                            return clean_content
                            
                    except Exception as e:
                        logger.debug(f"Failed to fetch {url}: {e}")
                        continue
                
                logger.warning(f"Could not fetch content from any of the {len(result_urls)} URLs found")
                return None
                
        except Exception as e:
            logger.error(f"Error searching/fetching rewards for {card_name}: {e}")
            return None

    async def _extract_rewards_with_llm(
        self, card_name: str, web_content: str
    ) -> dict[str, Any] | None:
        """
        Use LLM to extract rewards structure from web content.

        Args:
            card_name: Credit card name
            web_content: Webpage content

        Returns:
            Rewards structure dictionary or None if extraction failed
        """
        extraction_prompt = f"""You are analyzing credit card rewards information.

Card Name: {card_name}

Webpage Content:
{web_content}

Extract the rewards structure and return ONLY a valid JSON object with this exact format:
{{
    "card_name": "{card_name}",
    "rewards": {{
        "dining": 3.0,
        "travel": 2.0,
        "groceries": 1.5,
        "gas": 1.0,
        "default": 1.0
    }},
    "annual_fee": 95,
    "currency": "points",
    "notes": "Brief summary of special categories or restrictions"
}}

Rules:
- Use category names like: dining, travel, groceries, gas, online_shopping, streaming, default
- Rewards should be percentages for cash back (e.g., 2.0 for 2%) or points multipliers (e.g., 3.0 for 3x points)
- Always include a "default" category for all other purchases
- Set currency to "cashback", "points", or "miles"
- If annual fee not found, use 0
- Return ONLY the JSON object, no other text

JSON:"""

        try:
            # Call LLM using LiteLLM's invoke method
            from langchain_core.messages import HumanMessage

            messages = [HumanMessage(content=extraction_prompt)]
            llm_response = await self.llm_service.ainvoke(messages)

            # Extract text from response
            response_text = llm_response.content if hasattr(llm_response, "content") else str(llm_response)

            # Parse JSON from response
            import json

            # Try to extract JSON from response (it might have markdown formatting)
            json_str = response_text.strip()
            if json_str.startswith("```"):
                # Remove markdown code blocks
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str

            rewards_structure = json.loads(json_str)

            # Validate structure
            if "rewards" not in rewards_structure or "default" not in rewards_structure["rewards"]:
                logger.error(f"Invalid rewards structure extracted for {card_name}")
                return None

            logger.info(f"Successfully extracted rewards structure for {card_name}")
            return rewards_structure

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON for {card_name}: {e}")
            logger.debug(f"LLM response was: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error extracting rewards with LLM for {card_name}: {e}")
            return None

    async def _cache_rewards(
        self,
        session: AsyncSession,
        card_name: str,
        rewards_structure: dict[str, Any],
        search_space_id: int,
        user_id: str,
    ) -> None:
        """
        Cache rewards structure in the database.

        Args:
            session: Database session
            card_name: Credit card name
            rewards_structure: Rewards structure dictionary
            search_space_id: Search space ID
            user_id: User ID
        """
        try:
            from hashlib import sha256

            # Create markdown content for caching
            rewards_text = rewards_structure.get("rewards", {})
            markdown_content = f"# {card_name} - Rewards Structure\n\n"
            markdown_content += f"**Annual Fee:** ${rewards_structure.get('annual_fee', 0)}\n"
            markdown_content += f"**Currency:** {rewards_structure.get('currency', 'points')}\n\n"
            markdown_content += "## Rewards Categories\n\n"

            for category, rate in sorted(rewards_text.items()):
                if category != "default":
                    markdown_content += f"- **{category.replace('_', ' ').title()}:** {rate}%\n"

            markdown_content += f"- **All Other Purchases:** {rewards_text.get('default', 1.0)}%\n\n"

            if "notes" in rewards_structure:
                markdown_content += f"\n**Notes:** {rewards_structure['notes']}\n"

            # Create document
            content_hash = sha256(markdown_content.encode()).hexdigest()

            new_doc = Document(
                title=f"Credit Card Rewards: {card_name}",
                content=markdown_content,
                content_hash=content_hash,
                search_space_id=search_space_id,
                user_id=user_id,
                document_type=DocumentType.FILE,
                metadata={
                    "rewards_structure": rewards_structure,
                    "card_name": card_name,
                    "cached_at": datetime.now(UTC).isoformat(),
                    "cache_ttl_days": 7,
                },
            )

            session.add(new_doc)
            await session.flush()

            logger.info(f"Cached rewards structure for {card_name}")

        except Exception as e:
            logger.error(f"Error caching rewards for {card_name}: {e}")
            # Don't raise - caching failure shouldn't break the flow
