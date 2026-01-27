"""
Subscription detection and merchant normalization utilities.

This module provides utilities for detecting recurring subscriptions
and normalizing merchant names for better matching.
"""

import re
from typing import Any


def normalize_merchant(merchant_name: str | None) -> str:
    """
    Normalize merchant names for consistent matching across transactions.
    
    Examples:
        - "NETFLIX.COM*123456" -> "netflix"
        - "SPOTIFY AB*789" -> "spotify"
        - "AMZN PRIME*456" -> "amazon prime"
        - "SQ *DOORDASH" -> "doordash"
        - "PAYPAL *HULU" -> "hulu"
    
    Args:
        merchant_name: Raw merchant name from transaction
        
    Returns:
        Normalized merchant name in lowercase
    """
    if not merchant_name:
        return "unknown"
    
    merchant = merchant_name.lower().strip()
    
    # Remove common prefixes
    prefixes_to_remove = [
        "sq *",  # Square
        "paypal *",
        "venmo *",
        "tst* ",  # Test
        "pos ",  # Point of sale
        "recurring ",
        "subscription ",
    ]
    
    for prefix in prefixes_to_remove:
        if merchant.startswith(prefix):
            merchant = merchant[len(prefix):]
    
    # Remove special characters except spaces
    merchant = re.sub(r'[^a-z0-9\s]', ' ', merchant)
    
    # Remove transaction IDs and numbers
    merchant = re.sub(r'\b\d+\b', '', merchant)
    
    # Remove extra whitespace
    merchant = re.sub(r'\s+', ' ', merchant).strip()
    
    # Known subscription patterns
    subscription_patterns = {
        'netflix': ['netflix'],
        'spotify': ['spotify'],
        'amazon prime': ['amzn prime', 'amazon prime', 'prime video'],
        'hulu': ['hulu'],
        'disney plus': ['disney', 'disneyplus', 'disney plus'],
        'hbo max': ['hbo', 'hbomax'],
        'apple music': ['apple com bill', 'apple music'],
        'apple tv': ['apple tv'],
        'youtube premium': ['youtube premium', 'google youtube'],
        'paramount plus': ['paramount'],
        'peacock': ['peacock'],
        'discovery plus': ['discovery'],
        
        # Software/SaaS
        'adobe': ['adobe'],
        'microsoft 365': ['microsoft', 'msft', 'office 365'],
        'google workspace': ['google workspace', 'google apps'],
        'dropbox': ['dropbox'],
        'evernote': ['evernote'],
        'notion': ['notion'],
        'slack': ['slack'],
        'zoom': ['zoom'],
        'github': ['github'],
        'chatgpt': ['openai', 'chat gpt'],
        'claude': ['anthropic'],
        
        # Fitness/Wellness
        'planet fitness': ['planet fit', 'planet fitness'],
        'la fitness': ['la fitness'],
        'equinox': ['equinox'],
        'peloton': ['peloton'],
        'calm': ['calm'],
        'headspace': ['headspace'],
        
        # Delivery/Food
        'doordash': ['doordash', 'door dash'],
        'uber eats': ['uber eats'],
        'grubhub': ['grubhub'],
        'instacart': ['instacart'],
        'hellofresh': ['hellofresh', 'hello fresh'],
        'blue apron': ['blue apron'],
        
        # News/Magazines
        'new york times': ['nytimes', 'ny times', 'new york times'],
        'washington post': ['wash post', 'washington post'],
        'wall street journal': ['wsj', 'wall street'],
        
        # Gaming
        'playstation plus': ['playstation', 'ps plus'],
        'xbox game pass': ['xbox', 'microsoft xbox'],
        'nintendo online': ['nintendo'],
        
        # Cloud storage
        'icloud': ['icloud', 'apple icloud'],
        'google one': ['google one', 'google storage'],
        'onedrive': ['onedrive'],
    }
    
    # Match against known patterns
    for normalized, patterns in subscription_patterns.items():
        for pattern in patterns:
            if pattern in merchant:
                return normalized
    
    return merchant


def create_merchant_amount_key(merchant_name: str | None, amount: float) -> str:
    """
    Create a composite key for grouping recurring charges.
    
    This key combines normalized merchant name with rounded amount
    to identify potential subscription patterns.
    
    Args:
        merchant_name: Raw merchant name
        amount: Transaction amount
        
    Returns:
        Composite key like "netflix_16" or "spotify_11"
    """
    normalized = normalize_merchant(merchant_name)
    # Round amount to nearest dollar for grouping
    rounded_amount = round(abs(amount), 0)
    return f"{normalized}_{int(rounded_amount)}"


def detect_subscription_metadata(transaction: dict[str, Any]) -> dict[str, Any]:
    """
    Enhance transaction metadata with subscription detection fields.
    
    Args:
        transaction: Transaction dictionary from Plaid
        
    Returns:
        Enhanced metadata dictionary
    """
    merchant_name = transaction.get("merchant_name") or transaction.get("name", "")
    amount = float(transaction.get("amount", 0))
    category = transaction.get("category", [])
    
    # Detect potential subscription indicators
    subscription_indicators = {
        'has_merchant': bool(transaction.get("merchant_name")),
        'is_recurring_category': any(
            cat.lower() in ['subscription', 'recurring', 'membership']
            for cat in (category if isinstance(category, list) else [])
        ),
        'payment_channel': transaction.get("payment_channel"),
        'is_pending': transaction.get("pending", False),
    }
    
    # Enhanced metadata
    metadata = {
        'merchant_raw': merchant_name,
        'merchant_normalized': normalize_merchant(merchant_name),
        'merchant_amount_key': create_merchant_amount_key(merchant_name, amount),
        'amount': abs(amount),
        'is_debit': amount > 0,  # Plaid convention: positive = outflow
        'category': category if isinstance(category, list) else [category] if category else [],
        'subscription_indicators': subscription_indicators,
        'plaid_transaction_id': transaction.get("transaction_id"),
        'account_id': transaction.get("account_id"),
    }
    
    return metadata
