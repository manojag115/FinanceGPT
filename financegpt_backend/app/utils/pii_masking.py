"""PII masking utilities for tax forms.

This module provides functions to mask personally identifiable information (PII)
before sending tax form data to LLMs or external services.
"""

import hashlib
import re
from typing import Any


def mask_ssn(ssn: str | None, keep_last: int = 4) -> str:
    """Mask SSN, keeping only the last N digits.
    
    Args:
        ssn: Social Security Number (any format: 123-45-6789, 123456789, etc.)
        keep_last: Number of digits to keep unmasked (default 4)
        
    Returns:
        Masked SSN like "***-**-6789" or "[SSN_REDACTED]" if invalid
        
    Examples:
        >>> mask_ssn("123-45-6789")
        "***-**-6789"
        >>> mask_ssn("123456789")
        "*****6789"
        >>> mask_ssn("invalid")
        "[SSN_REDACTED]"
    """
    if not ssn:
        return "[SSN_REDACTED]"
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', ssn)
    
    # SSN must be exactly 9 digits
    if len(digits_only) != 9:
        return "[SSN_REDACTED]"
    
    # Determine format based on original string
    if '-' in ssn:
        # Format: 123-45-6789 -> ***-**-6789
        last_digits = digits_only[-keep_last:]
        return f"***-**-{last_digits}"
    else:
        # Format: 123456789 -> *****6789
        last_digits = digits_only[-keep_last:]
        mask_count = 9 - keep_last
        return ('*' * mask_count) + last_digits


def hash_tin(tin: str | None) -> str:
    """Hash Tax Identification Number (SSN or EIN) using SHA-256.
    
    Args:
        tin: SSN or EIN to hash
        
    Returns:
        SHA-256 hash of the TIN (64 hex characters)
        
    Examples:
        >>> hash_tin("123-45-6789")
        "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
    """
    if not tin:
        return ""
    
    # Remove all non-digit characters for consistent hashing
    digits_only = re.sub(r'\D', '', tin)
    
    # Hash using SHA-256
    return hashlib.sha256(digits_only.encode('utf-8')).hexdigest()


def mask_ein(ein: str | None) -> str:
    """Mask Employer Identification Number.
    
    Args:
        ein: EIN in format XX-XXXXXXX
        
    Returns:
        Hashed EIN (never shows plaintext for privacy)
        
    Examples:
        >>> mask_ein("12-3456789")
        (returns SHA-256 hash)
    """
    return hash_tin(ein)


def mask_name(name: str | None, replacement: str = "[NAME_REDACTED]") -> str:
    """Mask a person's name.
    
    Args:
        name: Full name to mask
        replacement: Replacement text (default: "[NAME_REDACTED]")
        
    Returns:
        Replacement text
        
    Examples:
        >>> mask_name("John Smith")
        "[NAME_REDACTED]"
        >>> mask_name("John Smith", "[EMPLOYEE]")
        "[EMPLOYEE]"
    """
    if not name:
        return replacement
    
    return replacement


def mask_address(address: str | None, replacement: str = "[ADDRESS_REDACTED]") -> str:
    """Mask a full address.
    
    Args:
        address: Full address to mask
        replacement: Replacement text (default: "[ADDRESS_REDACTED]")
        
    Returns:
        Replacement text
        
    Examples:
        >>> mask_address("123 Main St, New York, NY 10001")
        "[ADDRESS_REDACTED]"
    """
    if not address:
        return replacement
    
    return replacement


def mask_tax_form_for_llm(form_data: dict[str, Any], form_type: str) -> dict[str, Any]:
    """Mask all PII in a tax form before sending to LLM.
    
    This function removes or masks:
    - SSN (keep last 4 for display)
    - EIN (hash completely)
    - Names (replace with placeholders)
    - Addresses (replace with placeholders)
    
    Financial data (wages, taxes, etc.) is NOT masked.
    
    Args:
        form_data: Dictionary containing tax form data
        form_type: Type of form (W2, 1099-MISC, etc.)
        
    Returns:
        Dictionary with PII masked
        
    Examples:
        >>> w2_data = {
        ...     "employee_ssn": "123-45-6789",
        ...     "employer_ein": "12-3456789",
        ...     "employee_name": "John Smith",
        ...     "wages": 75000.00,
        ... }
        >>> masked = mask_tax_form_for_llm(w2_data, "W2")
        >>> masked["employee_ssn"]
        "***-**-6789"
        >>> masked["wages"]
        75000.0
    """
    masked_data = form_data.copy()
    
    # Mask SSNs (keep last 4 for context)
    if "employee_ssn" in masked_data:
        masked_data["employee_ssn"] = mask_ssn(masked_data["employee_ssn"])
    
    if "recipient_ssn" in masked_data:
        masked_data["recipient_ssn"] = mask_ssn(masked_data["recipient_ssn"])
    
    # Hash EINs (never show plaintext)
    if "employer_ein" in masked_data:
        masked_data["employer_ein_hash"] = hash_tin(masked_data["employer_ein"])
        del masked_data["employer_ein"]
    
    if "payer_tin" in masked_data:
        masked_data["payer_tin_hash"] = hash_tin(masked_data["payer_tin"])
        del masked_data["payer_tin"]
    
    if "recipient_tin" in masked_data:
        masked_data["recipient_tin_hash"] = hash_tin(masked_data["recipient_tin"])
        del masked_data["recipient_tin"]
    
    # Mask names
    if "employee_name" in masked_data:
        masked_data["employee_name"] = mask_name(masked_data["employee_name"], "[EMPLOYEE_NAME]")
    
    if "employer_name" in masked_data:
        # Keep employer name for context (helps LLM understand employment)
        # But could mask if user prefers
        pass
    
    if "payer_name" in masked_data:
        # Keep payer name (e.g., "Vanguard", "Chase Bank") - useful for context
        pass
    
    # Mask addresses
    if "employee_address" in masked_data:
        masked_data["employee_address"] = mask_address(masked_data["employee_address"])
    
    if "employer_address" in masked_data:
        masked_data["employer_address"] = mask_address(masked_data["employer_address"])
    
    if "payer_address" in masked_data:
        masked_data["payer_address"] = mask_address(masked_data["payer_address"])
    
    # Financial data is NOT masked - it's needed for analysis
    # This includes: wages, taxes withheld, interest income, dividends, etc.
    
    return masked_data


def prepare_tax_form_for_storage(form_data: dict[str, Any]) -> dict[str, Any]:
    """Prepare tax form data for database storage with proper hashing.
    
    This function:
    - Hashes SSNs/EINs (stores hash only, never plaintext)
    - Keeps financial data intact
    - Optionally masks names/addresses based on user preference
    
    Args:
        form_data: Dictionary containing raw tax form data
        
    Returns:
        Dictionary ready for database insertion
    """
    storage_data = form_data.copy()
    
    # Hash all TINs for storage (never store plaintext)
    if "employee_ssn" in storage_data:
        storage_data["employee_ssn_hash"] = hash_tin(storage_data["employee_ssn"])
        del storage_data["employee_ssn"]
    
    if "employer_ein" in storage_data:
        storage_data["employer_ein_hash"] = hash_tin(storage_data["employer_ein"])
        del storage_data["employer_ein"]
    
    if "payer_tin" in storage_data:
        storage_data["payer_tin_hash"] = hash_tin(storage_data["payer_tin"])
        del storage_data["payer_tin"]
    
    if "recipient_tin" in storage_data:
        storage_data["recipient_tin_hash"] = hash_tin(storage_data["recipient_tin"])
        del storage_data["recipient_tin"]
    
    # Mask employee name for storage
    if "employee_name" in storage_data:
        storage_data["employee_name_masked"] = "[EMPLOYEE_NAME]"
        del storage_data["employee_name"]
    
    # Keep employer/payer names (useful for queries)
    # Keep financial data (wages, taxes, etc.)
    
    return storage_data


def validate_confidence_threshold(
    confidence_scores: dict[str, float],
    threshold: float = 0.85
) -> tuple[bool, list[str]]:
    """Check if confidence scores meet threshold.
    
    Args:
        confidence_scores: Dictionary of field -> confidence score
        threshold: Minimum acceptable confidence (default 0.85)
        
    Returns:
        Tuple of (all_passed, list_of_failed_fields)
        
    Examples:
        >>> scores = {"wages": 0.95, "federal_tax": 0.80, "ssn": 0.90}
        >>> passed, failed = validate_confidence_threshold(scores, 0.85)
        >>> passed
        False
        >>> failed
        ['federal_tax']
    """
    failed_fields = []
    
    for field, score in confidence_scores.items():
        if score < threshold:
            failed_fields.append(field)
    
    all_passed = len(failed_fields) == 0
    return all_passed, failed_fields
