"""
Credit card rewards database for top US credit cards.

This database contains manually curated rewards structures for the most popular
US credit cards. Update this quarterly or when major changes occur.

Last updated: January 2026
"""

from typing import Any

# Database of credit card rewards
# Key: Normalized card name (lowercase, no special chars)
# Value: Rewards structure
CREDIT_CARD_REWARDS_DATABASE: dict[str, dict[str, Any]] = {
    # =========================================================================
    # TRAVEL CARDS
    # =========================================================================
    "chase sapphire preferred": {
        "card_name": "Chase Sapphire Preferred",
        "rewards": {
            "travel": 5.0,  # 5x on travel through Chase portal
            "dining": 3.0,
            "online_groceries": 3.0,
            "streaming": 3.0,
            "default": 1.0,
        },
        "annual_fee": 95,
        "currency": "points",
        "notes": "5x travel booked through Chase, 3x dining/online groceries/streaming, 1x everything else",
    },
    "chase sapphire reserve": {
        "card_name": "Chase Sapphire Reserve",
        "rewards": {
            "travel": 10.0,  # 10x on hotels/car rentals through Chase, 5x flights
            "dining": 3.0,
            "default": 1.0,
        },
        "annual_fee": 550,
        "currency": "points",
        "notes": "10x hotels/cars through Chase, 5x flights through Chase, 3x dining, 1x everything else",
    },
    "capital one venture": {
        "card_name": "Capital One Venture",
        "rewards": {
            "travel": 5.0,  # 5x on hotels/rentals through Capital One
            "default": 2.0,
        },
        "annual_fee": 95,
        "currency": "miles",
        "notes": "5x on hotels/rentals booked through Capital One, 2x everything else",
    },
    "capital one venture x": {
        "card_name": "Capital One Venture X",
        "rewards": {
            "travel": 10.0,  # 10x on hotels/rentals through Capital One, 5x flights
            "default": 2.0,
        },
        "annual_fee": 395,
        "currency": "miles",
        "notes": "10x hotels/rentals, 5x flights through Capital One, 2x everything else",
    },
    "american express platinum": {
        "card_name": "American Express Platinum",
        "rewards": {
            "travel": 5.0,  # 5x on flights/prepaid hotels through Amex
            "default": 1.0,
        },
        "annual_fee": 695,
        "currency": "points",
        "notes": "5x flights and prepaid hotels booked through Amex, 1x everything else",
    },
    "american express gold": {
        "card_name": "American Express Gold",
        "rewards": {
            "dining": 4.0,
            "groceries": 4.0,  # 4x at US supermarkets (up to $25k/year)
            "default": 1.0,
        },
        "annual_fee": 250,
        "currency": "points",
        "notes": "4x dining worldwide, 4x US supermarkets (up to $25k/year), 1x everything else",
    },
    
    # =========================================================================
    # CASH BACK CARDS
    # =========================================================================
    "citi double cash": {
        "card_name": "Citi Double Cash",
        "rewards": {
            "default": 2.0,  # 1% when you buy, 1% when you pay
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "2% cash back on everything (1% when you buy, 1% when you pay)",
    },
    "chase freedom unlimited": {
        "card_name": "Chase Freedom Unlimited",
        "rewards": {
            "travel": 5.0,  # 5x on travel through Chase
            "dining": 3.0,
            "drugstore": 3.0,
            "default": 1.5,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "5x travel through Chase, 3x dining/drugstores, 1.5% everything else",
    },
    "chase freedom flex": {
        "card_name": "Chase Freedom Flex",
        "rewards": {
            "travel": 5.0,  # 5x on travel through Chase
            "dining": 3.0,
            "drugstore": 3.0,
            "rotating": 5.0,  # 5% rotating categories (up to $1,500/quarter)
            "default": 1.0,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "5% rotating categories (up to $1,500/quarter), 5x travel through Chase, 3x dining/drugstores, 1% everything else",
    },
    "discover it cash back": {
        "card_name": "Discover it Cash Back",
        "rewards": {
            "rotating": 5.0,  # 5% rotating categories (up to $1,500/quarter)
            "default": 1.0,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "5% cash back on rotating categories (up to $1,500/quarter), 1% everything else",
    },
    "american express blue cash preferred": {
        "card_name": "American Express Blue Cash Preferred",
        "rewards": {
            "groceries": 6.0,  # 6% at US supermarkets (up to $6k/year)
            "streaming": 6.0,
            "transit": 3.0,
            "gas": 3.0,
            "default": 1.0,
        },
        "annual_fee": 95,
        "currency": "cashback",
        "notes": "6% US supermarkets (up to $6k/year) and streaming, 3% transit/gas, 1% everything else",
    },
    "american express blue cash everyday": {
        "card_name": "American Express Blue Cash Everyday",
        "rewards": {
            "groceries": 3.0,  # 3% at US supermarkets (up to $6k/year)
            "gas": 2.0,
            "online_shopping": 2.0,
            "default": 1.0,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "3% US supermarkets (up to $6k/year), 2% gas/online shopping, 1% everything else",
    },
    "wells fargo active cash": {
        "card_name": "Wells Fargo Active Cash",
        "rewards": {
            "default": 2.0,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "2% cash back on everything",
    },
    
    # =========================================================================
    # BUSINESS CARDS
    # =========================================================================
    "chase ink business preferred": {
        "card_name": "Chase Ink Business Preferred",
        "rewards": {
            "travel": 3.0,
            "shipping": 3.0,
            "advertising": 3.0,  # Internet, cable, phone
            "default": 1.0,
        },
        "annual_fee": 95,
        "currency": "points",
        "notes": "3x travel, shipping, internet/cable/phone advertising, 1x everything else",
    },
    "chase ink business unlimited": {
        "card_name": "Chase Ink Business Unlimited",
        "rewards": {
            "default": 1.5,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "1.5% cash back on everything",
    },
    "american express business gold": {
        "card_name": "American Express Business Gold",
        "rewards": {
            "top_categories": 4.0,  # 4x on top 2 categories (advertising, gas, restaurants, shipping, travel, tech)
            "default": 1.0,
        },
        "annual_fee": 295,
        "currency": "points",
        "notes": "4x on top 2 categories each billing cycle (advertising, gas, restaurants, shipping, travel, tech), 1x everything else",
    },
    "american express business platinum": {
        "card_name": "American Express Business Platinum",
        "rewards": {
            "travel": 5.0,  # 5x on flights/prepaid hotels through Amex
            "default": 1.5,
        },
        "annual_fee": 695,
        "currency": "points",
        "notes": "5x flights and prepaid hotels booked through Amex, 1.5x on purchases over $5k (up to $2M/year), 1x everything else",
    },
    
    # =========================================================================
    # STORE/SPECIALTY CARDS
    # =========================================================================
    "amazon prime rewards visa": {
        "card_name": "Amazon Prime Rewards Visa",
        "rewards": {
            "amazon": 5.0,  # 5% at Amazon and Whole Foods (Prime members)
            "gas": 2.0,
            "dining": 2.0,
            "drugstore": 2.0,
            "default": 1.0,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "5% at Amazon and Whole Foods (Prime members), 2% gas/dining/drugstores, 1% everything else",
    },
    "apple card": {
        "card_name": "Apple Card",
        "rewards": {
            "apple": 3.0,
            "default": 2.0,  # 2% with Apple Pay
            "physical_card": 1.0,  # 1% with physical card
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "3% at Apple, 2% with Apple Pay, 1% with physical card",
    },
    "target redcard": {
        "card_name": "Target RedCard",
        "rewards": {
            "target": 5.0,
            "default": 0.0,
        },
        "annual_fee": 0,
        "currency": "cashback",
        "notes": "5% at Target, 0% everywhere else",
    },
}


def normalize_card_name(card_name: str) -> str:
    """
    Normalize a credit card name for database lookup.
    
    Args:
        card_name: Raw card name (e.g., "Chase Sapphire Preferred®")
    
    Returns:
        Normalized name (e.g., "chase sapphire preferred")
    """
    # Remove special characters and normalize
    normalized = card_name.lower()
    normalized = normalized.replace("®", "").replace("™", "").replace("℠", "")
    normalized = normalized.replace("  ", " ").strip()
    
    # Handle common variations
    # "Chase Sapphire Preferred Card" -> "chase sapphire preferred"
    normalized = normalized.replace(" card", "").replace(" credit card", "")
    
    return normalized


def get_card_rewards(card_name: str) -> dict[str, Any] | None:
    """
    Get rewards structure for a credit card from the database.
    
    Args:
        card_name: Credit card name (will be normalized for lookup)
    
    Returns:
        Rewards structure dict or None if not found
    """
    normalized = normalize_card_name(card_name)
    return CREDIT_CARD_REWARDS_DATABASE.get(normalized)


def search_card_by_partial_name(partial_name: str) -> list[dict[str, Any]]:
    """
    Search for cards matching a partial name.
    
    Args:
        partial_name: Partial card name to search for
    
    Returns:
        List of matching card rewards structures
    """
    normalized_search = normalize_card_name(partial_name)
    matches = []
    
    for key, rewards in CREDIT_CARD_REWARDS_DATABASE.items():
        if normalized_search in key:
            matches.append(rewards)
    
    return matches
