"""Tiered tax form parser with hybrid extraction strategy.

Extraction Priority:
1. Structured PDF extraction (pdfplumber) - best for text-based PDFs
2. Unstructured library - handles more complex layouts
3. OCR with pattern matching - for scanned documents
4. LLM-assisted extraction - last resort, with PII masked

Each tier returns confidence scores. If confidence < 0.85, escalate to next tier.
"""

import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pdfplumber
from unstructured.partition.pdf import partition_pdf

from app.utils.pii_masking import mask_tax_form_for_llm, validate_confidence_threshold

logger = logging.getLogger(__name__)


class TaxFormParser:
    """Hybrid tax form parser with tiered extraction."""
    
    CONFIDENCE_THRESHOLD = 0.85
    
    # Common patterns for tax form fields
    PATTERNS = {
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "ein": r"\b\d{2}-\d{7}\b",
        "money": r"\$?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?",
        "date": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        "percentage": r"\d+(?:\.\d+)?%",
    }
    
    def __init__(self):
        """Initialize parser."""
        self.extraction_history: list[dict[str, Any]] = []
    
    async def parse_tax_form(
        self,
        file_path: str | Path,
        form_type: Literal["W2", "1099-MISC", "1099-INT", "1099-DIV", "1099-B"],
        tax_year: int,
    ) -> dict[str, Any]:
        """Parse tax form using tiered extraction strategy.
        
        Args:
            file_path: Path to PDF file
            form_type: Type of tax form
            tax_year: Tax year for the form
            
        Returns:
            Dictionary containing:
                - extracted_data: Parsed form fields
                - confidence_scores: Per-field confidence
                - extraction_method: Method used (structured_pdf, unstructured, ocr, llm_assisted)
                - needs_review: True if confidence < threshold
                - raw_extraction_data: Full extraction details
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Tax form file not found: {file_path}")
        
        # Tier 1: Structured PDF extraction (fastest, most accurate for text PDFs)
        logger.info(f"Tier 1: Attempting structured PDF extraction for {form_type}")
        result = await self._extract_structured_pdf(file_path, form_type, tax_year)
        
        if result and result["confidence_scores"]:
            avg_confidence = sum(result["confidence_scores"].values()) / len(result["confidence_scores"])
            logger.info(f"Tier 1 average confidence: {avg_confidence:.2f}")
            
            if avg_confidence >= self.CONFIDENCE_THRESHOLD:
                logger.info(f"Tier 1 succeeded with {avg_confidence:.2f} confidence")
                return result
        
        # Tier 2: Unstructured library (better layout analysis)
        logger.info(f"Tier 2: Attempting unstructured library extraction for {form_type}")
        result = await self._extract_unstructured(file_path, form_type, tax_year)
        
        if result and result["confidence_scores"]:
            avg_confidence = sum(result["confidence_scores"].values()) / len(result["confidence_scores"])
            logger.info(f"Tier 2 average confidence: {avg_confidence:.2f}")
            
            if avg_confidence >= self.CONFIDENCE_THRESHOLD:
                logger.info(f"Tier 2 succeeded with {avg_confidence:.2f} confidence")
                return result
        
        # Tier 3: OCR with pattern matching
        logger.info(f"Tier 3: Attempting OCR extraction for {form_type}")
        result = await self._extract_ocr(file_path, form_type, tax_year)
        
        if result and result["confidence_scores"]:
            avg_confidence = sum(result["confidence_scores"].values()) / len(result["confidence_scores"])
            logger.info(f"Tier 3 average confidence: {avg_confidence:.2f}")
            
            if avg_confidence >= self.CONFIDENCE_THRESHOLD:
                logger.info(f"Tier 3 succeeded with {avg_confidence:.2f} confidence")
                return result
        
        # Tier 4: LLM-assisted extraction (last resort, with PII masked)
        logger.warning(f"Tier 4: Escalating to LLM-assisted extraction for {form_type}")
        result = await self._extract_llm_assisted(file_path, form_type, tax_year, previous_result=result)
        
        return result
    
    async def _extract_structured_pdf(
        self,
        file_path: Path,
        form_type: str,
        tax_year: int,
    ) -> dict[str, Any]:
        """Extract data using pdfplumber (structured PDF).
        
        Best for: Text-based PDFs with clear structure.
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                # Extract text from all pages
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"
                
                # Extract based on form type
                if form_type == "W2":
                    extracted_data = self._parse_w2_text(full_text)
                elif form_type == "1099-MISC":
                    extracted_data = self._parse_1099_misc_text(full_text)
                elif form_type == "1099-INT":
                    extracted_data = self._parse_1099_int_text(full_text)
                elif form_type == "1099-DIV":
                    extracted_data = self._parse_1099_div_text(full_text)
                elif form_type == "1099-B":
                    extracted_data = self._parse_1099_b_text(full_text)
                else:
                    raise ValueError(f"Unsupported form type: {form_type}")
                
                # Calculate confidence scores based on field population
                confidence_scores = self._calculate_confidence_scores(extracted_data)
                
                return {
                    "extracted_data": extracted_data,
                    "confidence_scores": confidence_scores,
                    "extraction_method": "structured_pdf",
                    "needs_review": not self._meets_confidence_threshold(confidence_scores),
                    "raw_extraction_data": {"full_text": full_text},
                }
        
        except Exception as e:
            logger.error(f"Structured PDF extraction failed: {e}")
            return {
                "extracted_data": {},
                "confidence_scores": {},
                "extraction_method": "structured_pdf",
                "needs_review": True,
                "raw_extraction_data": {"error": str(e)},
            }
    
    async def _extract_unstructured(
        self,
        file_path: Path,
        form_type: str,
        tax_year: int,
    ) -> dict[str, Any]:
        """Extract data using unstructured library.
        
        Best for: PDFs with complex layouts, tables, multiple columns.
        """
        try:
            # Use unstructured to partition the PDF
            elements = partition_pdf(str(file_path), strategy="hi_res")
            
            # Combine all text elements
            full_text = "\n".join([str(el) for el in elements])
            
            # Extract based on form type (same parsers as structured PDF)
            if form_type == "W2":
                extracted_data = self._parse_w2_text(full_text)
            elif form_type == "1099-MISC":
                extracted_data = self._parse_1099_misc_text(full_text)
            elif form_type == "1099-INT":
                extracted_data = self._parse_1099_int_text(full_text)
            elif form_type == "1099-DIV":
                extracted_data = self._parse_1099_div_text(full_text)
            elif form_type == "1099-B":
                extracted_data = self._parse_1099_b_text(full_text)
            else:
                raise ValueError(f"Unsupported form type: {form_type}")
            
            confidence_scores = self._calculate_confidence_scores(extracted_data)
            
            return {
                "extracted_data": extracted_data,
                "confidence_scores": confidence_scores,
                "extraction_method": "unstructured",
                "needs_review": not self._meets_confidence_threshold(confidence_scores),
                "raw_extraction_data": {
                    "full_text": full_text,
                    "num_elements": len(elements),
                },
            }
        
        except Exception as e:
            logger.error(f"Unstructured extraction failed: {e}")
            return {
                "extracted_data": {},
                "confidence_scores": {},
                "extraction_method": "unstructured",
                "needs_review": True,
                "raw_extraction_data": {"error": str(e)},
            }
    
    async def _extract_ocr(
        self,
        file_path: Path,
        form_type: str,
        tax_year: int,
    ) -> dict[str, Any]:
        """Extract data using OCR with pattern matching.
        
        Best for: Scanned documents, images of tax forms.
        Note: This is a placeholder - would use pytesseract or similar in production.
        """
        # TODO: Implement OCR extraction with pytesseract
        # For now, return empty result to trigger LLM escalation
        logger.warning("OCR extraction not yet implemented")
        return {
            "extracted_data": {},
            "confidence_scores": {},
            "extraction_method": "ocr",
            "needs_review": True,
            "raw_extraction_data": {"status": "not_implemented"},
        }
    
    async def _extract_llm_assisted(
        self,
        file_path: Path,
        form_type: str,
        tax_year: int,
        previous_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract/verify data using LLM (with PII masked).
        
        Best for: Verification of low-confidence fields, unusual layouts.
        IMPORTANT: All PII is masked before sending to LLM.
        """
        # TODO: Implement LLM-assisted extraction using instructor
        # This would:
        # 1. Convert PDF to image or extract text
        # 2. Mask any PII found in previous extraction
        # 3. Send to LLM with structured output schema
        # 4. Return verified/extracted data
        
        logger.warning("LLM-assisted extraction not yet implemented")
        
        # For now, return previous result marked as needs_review
        if previous_result:
            previous_result["extraction_method"] = "llm_assisted"
            previous_result["needs_review"] = True
            return previous_result
        
        return {
            "extracted_data": {},
            "confidence_scores": {},
            "extraction_method": "llm_assisted",
            "needs_review": True,
            "raw_extraction_data": {"status": "not_implemented"},
        }
    
    def _parse_w2_text(self, text: str) -> dict[str, Any]:
        """Parse W2 form from extracted text."""
        data: dict[str, Any] = {}
        
        # Box 1: Wages, tips, other compensation
        wages_match = re.search(r"(?:Wages|Box 1).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if wages_match:
            data["wages_tips_compensation"] = self._parse_money(wages_match.group(1))
        
        # Box 2: Federal income tax withheld
        fed_tax_match = re.search(r"(?:Federal.*?tax.*?withheld|Box 2).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if fed_tax_match:
            data["federal_income_tax_withheld"] = self._parse_money(fed_tax_match.group(1))
        
        # Box 3: Social security wages
        ss_wages_match = re.search(r"(?:Social security wages|Box 3).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if ss_wages_match:
            data["social_security_wages"] = self._parse_money(ss_wages_match.group(1))
        
        # Box 4: Social security tax withheld
        ss_tax_match = re.search(r"(?:Social security tax|Box 4).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if ss_tax_match:
            data["social_security_tax_withheld"] = self._parse_money(ss_tax_match.group(1))
        
        # Box 5: Medicare wages
        medicare_wages_match = re.search(r"(?:Medicare wages|Box 5).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if medicare_wages_match:
            data["medicare_wages"] = self._parse_money(medicare_wages_match.group(1))
        
        # Box 6: Medicare tax withheld
        medicare_tax_match = re.search(r"(?:Medicare tax|Box 6).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if medicare_tax_match:
            data["medicare_tax_withheld"] = self._parse_money(medicare_tax_match.group(1))
        
        # Extract SSN (will be hashed before storage)
        ssn_match = re.search(self.PATTERNS["ssn"], text)
        if ssn_match:
            data["employee_ssn"] = ssn_match.group(0)
        
        # Extract EIN
        ein_match = re.search(self.PATTERNS["ein"], text)
        if ein_match:
            data["employer_ein"] = ein_match.group(0)
        
        # Box 13: Retirement plan checkbox
        data["retirement_plan"] = bool(re.search(r"Retirement plan.*?[Xx✓]", text, re.IGNORECASE))
        
        return data
    
    def _parse_1099_misc_text(self, text: str) -> dict[str, Any]:
        """Parse 1099-MISC form from extracted text."""
        data: dict[str, Any] = {}
        
        # Box 1: Rents
        rents_match = re.search(r"(?:Rents|Box 1).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if rents_match:
            data["rents"] = self._parse_money(rents_match.group(1))
        
        # Box 2: Royalties
        royalties_match = re.search(r"(?:Royalties|Box 2).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if royalties_match:
            data["royalties"] = self._parse_money(royalties_match.group(1))
        
        # Box 3: Other income
        other_match = re.search(r"(?:Other income|Box 3).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if other_match:
            data["other_income"] = self._parse_money(other_match.group(1))
        
        # Box 4: Federal income tax withheld
        fed_tax_match = re.search(r"(?:Federal.*?tax.*?withheld|Box 4).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if fed_tax_match:
            data["federal_income_tax_withheld"] = self._parse_money(fed_tax_match.group(1))
        
        return data
    
    def _parse_1099_int_text(self, text: str) -> dict[str, Any]:
        """Parse 1099-INT form from extracted text."""
        data: dict[str, Any] = {}
        
        # Box 1: Interest income
        interest_match = re.search(r"(?:Interest income|Box 1).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if interest_match:
            data["interest_income"] = self._parse_money(interest_match.group(1))
        
        # Box 2: Early withdrawal penalty
        penalty_match = re.search(r"(?:Early withdrawal|Box 2).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if penalty_match:
            data["early_withdrawal_penalty"] = self._parse_money(penalty_match.group(1))
        
        # Box 4: Federal income tax withheld
        fed_tax_match = re.search(r"(?:Federal.*?tax.*?withheld|Box 4).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if fed_tax_match:
            data["federal_income_tax_withheld"] = self._parse_money(fed_tax_match.group(1))
        
        return data
    
    def _parse_1099_div_text(self, text: str) -> dict[str, Any]:
        """Parse 1099-DIV form from extracted text."""
        data: dict[str, Any] = {}
        
        # Box 1a: Total ordinary dividends
        dividends_match = re.search(r"(?:Total ordinary dividends|Box 1a).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if dividends_match:
            data["total_ordinary_dividends"] = self._parse_money(dividends_match.group(1))
        
        # Box 1b: Qualified dividends
        qualified_match = re.search(r"(?:Qualified dividends|Box 1b).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if qualified_match:
            data["qualified_dividends"] = self._parse_money(qualified_match.group(1))
        
        # Box 2a: Total capital gain distributions
        cap_gains_match = re.search(r"(?:Total capital gain|Box 2a).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if cap_gains_match:
            data["total_capital_gain_distributions"] = self._parse_money(cap_gains_match.group(1))
        
        return data
    
    def _parse_1099_b_text(self, text: str) -> dict[str, Any]:
        """Parse 1099-B form from extracted text."""
        data: dict[str, Any] = {}
        
        # Box 1d: Proceeds
        proceeds_match = re.search(r"(?:Proceeds|Box 1d).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if proceeds_match:
            data["proceeds"] = self._parse_money(proceeds_match.group(1))
        
        # Box 1e: Cost or other basis
        basis_match = re.search(r"(?:Cost.*?basis|Box 1e).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if basis_match:
            data["cost_basis"] = self._parse_money(basis_match.group(1))
        
        # Short-term vs long-term
        data["short_term"] = bool(re.search(r"short.?term", text, re.IGNORECASE))
        data["long_term"] = bool(re.search(r"long.?term", text, re.IGNORECASE))
        
        return data
    
    def _parse_money(self, money_str: str) -> Decimal:
        """Parse money string to Decimal."""
        # Remove $, spaces, commas
        clean = re.sub(r"[$,\s]", "", money_str)
        return Decimal(clean)
    
    def _calculate_confidence_scores(self, data: dict[str, Any]) -> dict[str, float]:
        """Calculate confidence scores for extracted fields.
        
        For structured/unstructured extraction, confidence is based on:
        - Field population (present vs missing)
        - Format validation (valid Decimal, SSN format, etc.)
        """
        scores: dict[str, float] = {}
        
        for field, value in data.items():
            if value is None:
                scores[field] = 0.0
            elif isinstance(value, Decimal):
                # Money fields: high confidence if non-zero
                scores[field] = 0.95 if value > 0 else 0.5
            elif isinstance(value, str):
                # String fields: high confidence if non-empty
                scores[field] = 0.90 if value else 0.0
            elif isinstance(value, bool):
                # Boolean fields: medium confidence
                scores[field] = 0.75
            else:
                scores[field] = 0.85  # Default confidence
        
        return scores
    
    def _meets_confidence_threshold(self, scores: dict[str, float]) -> bool:
        """Check if confidence scores meet threshold."""
        if not scores:
            return False
        
        avg_score = sum(scores.values()) / len(scores)
        return avg_score >= self.CONFIDENCE_THRESHOLD
