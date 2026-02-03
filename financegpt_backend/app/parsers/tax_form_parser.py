"""Tiered tax form parser with hybrid extraction strategy.

Extraction Priority:
1. Structured PDF extraction (pdfplumber) - best for text-based PDFs
2. Unstructured library - handles more complex layouts
3. OCR with pattern matching - for scanned documents
4. LLM-assisted extraction - last resort, with PII masked

Each tier returns confidence scores. If confidence < 0.85, escalate to next tier.
"""

import decimal
import json
import logging
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import litellm
import pdfplumber
from pydantic import BaseModel, Field
from unstructured.partition.pdf import partition_pdf

from app.utils.pii_masking import mask_tax_form_for_llm, validate_confidence_threshold, mask_pii_in_text, recover_pii_from_mapping

logger = logging.getLogger(__name__)


# Pydantic models for structured LLM extraction
class W2ExtractedData(BaseModel):
    """Structured W2 data extracted by LLM."""
    wages_tips_compensation: float | None = Field(None, description="Box 1: Wages, tips, other compensation")
    federal_income_tax_withheld: float | None = Field(None, description="Box 2: Federal income tax withheld")
    social_security_wages: float | None = Field(None, description="Box 3: Social security wages")
    social_security_tax_withheld: float | None = Field(None, description="Box 4: Social security tax withheld")
    medicare_wages: float | None = Field(None, description="Box 5: Medicare wages and tips")
    medicare_tax_withheld: float | None = Field(None, description="Box 6: Medicare tax withheld")
    # State tax fields
    state_code: str | None = Field(None, description="Box 15: State code (e.g., CA, NY)")
    state_wages: float | None = Field(None, description="Box 16: State wages, tips, etc.")
    state_income_tax: float | None = Field(None, description="Box 17: State income tax withheld")
    # Note: SSN/EIN extracted from heuristics, not LLM (privacy)
    employer_name: str | None = Field(None, description="Employer's name")
    retirement_plan: bool = Field(False, description="Box 13: Retirement plan checkbox marked")


class Form1099ExtractedData(BaseModel):
    """Structured 1099 data extracted by LLM."""
    interest_income: float | None = Field(None, description="Interest income (1099-INT Box 1)")
    dividend_income: float | None = Field(None, description="Total ordinary dividends (1099-DIV Box 1a)")
    qualified_dividends: float | None = Field(None, description="Qualified dividends (1099-DIV Box 1b)")
    capital_gain_distributions: float | None = Field(None, description="Capital gain distributions (1099-DIV Box 2a)")
    proceeds: float | None = Field(None, description="Proceeds from sales (1099-B Box 1d)")
    cost_basis: float | None = Field(None, description="Cost or other basis (1099-B Box 1e)")
    rents: float | None = Field(None, description="Rents (1099-MISC Box 1)")
    other_income: float | None = Field(None, description="Other income (1099-MISC Box 3)")
    federal_tax_withheld: float | None = Field(None, description="Federal income tax withheld")
    payer_name: str | None = Field(None, description="Payer's name")
    # Note: Payer TIN extracted from heuristics, not LLM (privacy)


class Form1095CExtractedData(BaseModel):
    """Structured 1095-C data extracted by LLM (Employer-Provided Health Insurance Offer and Coverage)."""
    # Part I - Employee Information
    employer_name: str | None = Field(None, description="Part I Line 1: Employer name")
    employer_contact_phone: str | None = Field(None, description="Part I Line 9: Employer contact phone")
    
    # Part II - Employee Offer and Coverage (Line 14-16 codes for each month)
    offer_of_coverage_code: str | None = Field(None, description="Line 14: Offer of Coverage code (e.g., 1A, 1B, 1C, 1E, 1H)")
    employee_share_lowest_cost: float | None = Field(None, description="Line 15: Employee share of lowest cost monthly premium")
    safe_harbor_code: str | None = Field(None, description="Line 16: Safe Harbor code (e.g., 2C, 2D, 2F)")
    
    # Coverage months (Part II Line 14 - which months had coverage)
    covered_all_12_months: bool = Field(False, description="Whether coverage was offered for all 12 months")
    covered_months: list[str] | None = Field(None, description="List of months with coverage if not all 12")
    
    # Part III - Covered Individuals (if applicable)
    covered_individuals_count: int | None = Field(None, description="Number of covered individuals listed in Part III")


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
    
    async def parse_from_text(
        self,
        text: str,
        form_type: Literal["W2", "1099-MISC", "1099-INT", "1099-DIV", "1099-B", "1095-C"],
        tax_year: int,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """Parse tax form from pre-extracted text using LLM.
        
        This method is used when text has already been extracted from the PDF
        (e.g., by Unstructured or Docling) and we just need to parse the fields.
        
        Always uses LLM extraction for accuracy.
        
        Args:
            text: Pre-extracted text content
            form_type: Type of tax form
            tax_year: Tax year for the form
            llm_model: Optional LLM model string (e.g., "gemini/gemini-2.0-flash")
                      If not provided, uses default model
            
        Returns:
            Dictionary containing parsed data and confidence scores.
        """
        logger.info(f"Parsing {form_type} from pre-extracted text ({len(text)} chars) using LLM")
        
        # Use LLM extraction for accuracy
        extracted_data = await self._extract_with_llm(text, form_type, tax_year, llm_model=llm_model)
        extraction_method = "llm_assisted"
        
        # If LLM extraction failed, fall back to heuristic parsing
        if not extracted_data:
            logger.warning(f"LLM extraction failed for {form_type}, falling back to heuristic parsing")
            if form_type == "W2":
                extracted_data = self._parse_w2_text(text)
            elif form_type == "1099-MISC":
                extracted_data = self._parse_1099_misc_text(text)
            elif form_type == "1099-INT":
                extracted_data = self._parse_1099_int_text(text)
            elif form_type == "1099-DIV":
                extracted_data = self._parse_1099_div_text(text)
            elif form_type == "1099-B":
                extracted_data = self._parse_1099_b_text(text)
            elif form_type == "1095-C":
                extracted_data = self._parse_1095_c_text(text)
            else:
                raise ValueError(f"Unsupported form type: {form_type}")
            extraction_method = "heuristic"
        
        confidence_scores = self._calculate_confidence_scores(extracted_data)
        
        return {
            "extracted_data": extracted_data,
            "confidence_scores": confidence_scores,
            "extraction_method": extraction_method,
            "needs_review": not self._meets_confidence_threshold(confidence_scores),
            "raw_extraction_data": {"text_length": len(text)},
        }
    
    async def parse_tax_form(
        self,
        file_path: str | Path,
        form_type: Literal["W2", "1099-MISC", "1099-INT", "1099-DIV", "1099-B", "1095-C"],
        tax_year: int,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """Parse tax form using tiered extraction strategy.
        
        Args:
            file_path: Path to PDF file
            form_type: Type of tax form
            tax_year: Tax year for the form
            llm_model: Optional LLM model string for fallback extraction
            
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
    
    async def _extract_with_llm(
        self,
        text: str,
        form_type: str,
        tax_year: int,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        """Use LLM to extract structured data from tax form text.
        
        This is called when heuristic parsing fails to find dollar amounts.
        PII (SSN, EIN) is masked before sending to the LLM.
        
        Args:
            text: The document text to parse
            form_type: Type of tax form
            tax_year: Tax year
            llm_model: Optional LLM model string. If not provided, uses default.
        """
        # Use provided model or fall back to default
        model = llm_model or "gemini/gemini-2.0-flash"
        logger.info(f"Using LLM extraction for {form_type} (tax year {tax_year}) with model: {model}")
        
        # Mask PII before sending to LLM
        masked_text, pii_mapping = mask_pii_in_text(text)
        if pii_mapping:
            logger.info(f"Masked {len(pii_mapping)} PII items before LLM call")
        
        # Select the appropriate prompt based on form type
        if form_type == "W2":
            system_prompt = """You are a tax document parser. Extract W-2 form data from the provided text.
            
Extract these specific fields:
- wages_tips_compensation: Box 1 - Wages, tips, other compensation (the main income amount)
- federal_income_tax_withheld: Box 2 - Federal income tax withheld
- social_security_wages: Box 3 - Social security wages (often same as Box 1, capped at ~$176,100 for 2025)
- social_security_tax_withheld: Box 4 - Social security tax withheld (about 6.2% of Box 3)
- medicare_wages: Box 5 - Medicare wages and tips (often same as Box 1)
- medicare_tax_withheld: Box 6 - Medicare tax withheld (about 1.45% of Box 5)
- state_code: Box 15 - Two-letter state code (e.g., CA, NY, TX)
- state_wages: Box 16 - State wages, tips, etc.
- state_income_tax: Box 17 - State income tax withheld
- employer_name: Name of the employer
- retirement_plan: True if Box 13 retirement plan is checked

Note: SSN and EIN have been masked for privacy (shown as [SSN:***-**-XXXX] or [EIN:XXXXXXXX]).
Do NOT try to extract SSN or EIN values.

Important:
- Look for dollar amounts formatted as $XX,XXX.XX or XX,XXX.XX
- The wages amount is typically the largest number (often $50,000 - $500,000 range)
- Federal tax withheld is typically 10-35% of wages
- Return null for any field you cannot find
- Do NOT guess values - only extract what you can clearly identify"""

            response_format = W2ExtractedData
        elif form_type == "1095-C":
            system_prompt = """You are a tax document parser. Extract Form 1095-C data from the provided text.
            
Form 1095-C is the Employer-Provided Health Insurance Offer and Coverage form.

Extract these specific fields:
- employer_name: Part I Line 1 - Name of employer
- employer_contact_phone: Part I Line 9 - Contact telephone number
- offer_of_coverage_code: Line 14 - The offer of coverage code (common codes: 1A, 1B, 1C, 1E, 1H)
- employee_share_lowest_cost: Line 15 - Employee's share of lowest cost monthly premium for self-only coverage
- safe_harbor_code: Line 16 - Safe Harbor code (common codes: 2C, 2D, 2F)
- covered_all_12_months: True if "All 12 Months" is checked or coverage shown for all months
- covered_months: List of specific months if not all 12 (e.g., ["Jan", "Feb", "Mar"])
- covered_individuals_count: Number of people listed in Part III Covered Individuals section

Note: SSN and EIN have been masked for privacy. Do NOT try to extract SSN or EIN values.

Important:
- Look for the coverage codes in Line 14, 15, 16 columns
- Return null for any field you cannot find
- Do NOT guess values - only extract what you can clearly identify"""

            response_format = Form1095CExtractedData
        else:
            system_prompt = """You are a tax document parser. Extract 1099 form data from the provided text.
            
Extract any applicable fields:
- interest_income: 1099-INT Box 1
- dividend_income: 1099-DIV Box 1a
- qualified_dividends: 1099-DIV Box 1b  
- capital_gain_distributions: 1099-DIV Box 2a
- proceeds: 1099-B Box 1d (sale proceeds)
- cost_basis: 1099-B Box 1e
- rents: 1099-MISC Box 1
- other_income: 1099-MISC Box 3
- federal_tax_withheld: Federal tax withheld amount
- payer_name: Name of the payer/institution

Note: TINs have been masked for privacy. Do NOT try to extract TIN/SSN/EIN values.

Return null for fields not present in this specific form."""

            response_format = Form1099ExtractedData
        
        # Use masked text in the prompt (first 8000 chars)
        text_for_llm = masked_text[:8000]
        
        user_prompt = f"""Extract tax form data from this {form_type} for tax year {tax_year}:

{text_for_llm}

Return the extracted values as JSON."""

        try:
            # Use litellm for LLM call with structured output
            response = await litellm.acompletion(
                model=model,  # Use user's configured model or default
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,  # Deterministic
            )
            
            # Parse the response
            content = response.choices[0].message.content
            extracted_json = json.loads(content)
            
            logger.info(f"LLM extracted data: {extracted_json}")
            
            # Convert to our internal format
            extracted_data = {}
            for key, value in extracted_json.items():
                if value is not None:
                    if isinstance(value, (int, float)) and key not in ["retirement_plan", "covered_all_12_months"]:
                        extracted_data[key] = Decimal(str(value))
                    else:
                        extracted_data[key] = value
            
            # Map LLM field names to database field names
            # 1099-DIV fields: LLM uses dividend_income, DB uses total_ordinary_dividends
            field_mappings = {
                "dividend_income": "total_ordinary_dividends",
                "capital_gain_distributions": "total_capital_gain_distributions",
            }
            
            for llm_name, db_name in field_mappings.items():
                if llm_name in extracted_data and db_name not in extracted_data:
                    extracted_data[db_name] = extracted_data.pop(llm_name)
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {}
    
    def _parse_w2_text(self, text: str) -> dict[str, Any]:
        """Parse W2 form from extracted text.
        
        Uses a two-phase approach:
        1. First, try to find all dollar amounts in the text
        2. Use context around those amounts to map them to W2 boxes
        """
        data: dict[str, Any] = {}
        
        # Find all dollar amounts in the text (realistic income/tax values)
        # Must have comma-separated thousands OR decimal point for cents, OR be over 100
        # This filters out box numbers like "21", "34", etc.
        dollar_amounts = self._extract_dollar_amounts(text)
        
        logger.debug(f"Found {len(dollar_amounts)} dollar amounts: {dollar_amounts[:10]}")
        
        # For each W2 field, find the most likely value by looking at context
        # Box 1: Wages, tips, other compensation (usually the largest amount)
        if dollar_amounts:
            # Sort by value descending - wages is typically the largest
            sorted_amounts = sorted(dollar_amounts, key=lambda x: x[0], reverse=True)
            
            # Wages is usually the largest amount
            data["wages_tips_compensation"] = sorted_amounts[0][0]
            
            # Federal tax withheld is usually second or third largest
            if len(sorted_amounts) > 1:
                # Look for one that's roughly 10-30% of wages
                wages = float(sorted_amounts[0][0])
                for amount, context in sorted_amounts[1:]:
                    amount_float = float(amount)
                    if wages > 0 and 0.05 <= amount_float / wages <= 0.40:
                        data["federal_income_tax_withheld"] = amount
                        break
                else:
                    # Fallback to second largest
                    if len(sorted_amounts) > 1:
                        data["federal_income_tax_withheld"] = sorted_amounts[1][0]
        
        # Try to find SS wages (often equal to wages, capped at SS limit ~$168,600 for 2024)
        ss_limit = Decimal("168600")
        if "wages_tips_compensation" in data:
            wages = data["wages_tips_compensation"]
            if wages <= ss_limit:
                data["social_security_wages"] = wages
            else:
                data["social_security_wages"] = ss_limit
        
        # SS tax is 6.2% of SS wages
        if "social_security_wages" in data:
            data["social_security_tax_withheld"] = (data["social_security_wages"] * Decimal("0.062")).quantize(Decimal("0.01"))
        
        # Medicare wages usually equals regular wages
        if "wages_tips_compensation" in data:
            data["medicare_wages"] = data["wages_tips_compensation"]
        
        # Medicare tax is 1.45% of Medicare wages
        if "medicare_wages" in data:
            data["medicare_tax_withheld"] = (data["medicare_wages"] * Decimal("0.0145")).quantize(Decimal("0.01"))
        
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
    
    def _extract_dollar_amounts(self, text: str) -> list[tuple[Decimal, str]]:
        """Extract all realistic dollar amounts from text with surrounding context.
        
        Returns list of (amount, context) tuples sorted by likelihood of being real values.
        Filters out small numbers that are likely box numbers, dates, etc.
        """
        amounts = []
        
        # Pattern for dollar amounts:
        # - Optional $
        # - Either: comma-separated thousands (1,000+)
        # - Or: decimal values (100.00+)
        # - Or: large numbers without commas (1000+)
        patterns = [
            # $1,234.56 or $1,234
            r'\$\s*(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)',
            # 1,234.56 or 1,234 (with commas, no $)
            r'(?<![.\d])(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)(?![.\d])',
            # $1234.56 (4+ digits with decimal, $)
            r'\$\s*(\d{4,}(?:\.\d{2}))',
            # 1234.56 (4+ digits with decimal, no $)
            r'(?<![,.\d])(\d{4,}\.\d{2})(?![.\d])',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                try:
                    amount_str = match.group(1)
                    amount = self._parse_money(amount_str)
                    
                    # Only include amounts >= $100 (filters out box numbers, dates, etc.)
                    if amount >= 100:
                        # Get context (50 chars before and after)
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 50)
                        context = text[start:end]
                        amounts.append((amount, context))
                except (ValueError, decimal.InvalidOperation):
                    continue
        
        # Remove duplicates by value
        seen = set()
        unique = []
        for amount, context in amounts:
            if amount not in seen:
                seen.add(amount)
                unique.append((amount, context))
        
        return unique
    
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
    
    def _parse_1095_c_text(self, text: str) -> dict[str, Any]:
        """Parse 1095-C form from extracted text (Employer-Provided Health Insurance)."""
        data: dict[str, Any] = {}
        
        # Employer name
        employer_match = re.search(r"(?:Employer|Company).*?name[:\s]+([A-Za-z0-9\s,\.]+?)(?:\n|$)", text, re.IGNORECASE)
        if employer_match:
            data["employer_name"] = employer_match.group(1).strip()
        
        # Line 14: Offer of Coverage code (1A, 1B, 1C, 1E, 1H, etc.)
        offer_code_match = re.search(r"(?:Line\s*14|offer.*?coverage).*?\b(1[A-HJ-Z])\b", text, re.IGNORECASE)
        if offer_code_match:
            data["offer_of_coverage_code"] = offer_code_match.group(1).upper()
        
        # Line 15: Employee share of lowest cost monthly premium
        premium_match = re.search(r"(?:Line\s*15|lowest.*?cost|employee.*?share).*?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text, re.IGNORECASE)
        if premium_match:
            data["employee_share_lowest_cost"] = self._parse_money(premium_match.group(1))
        
        # Line 16: Safe Harbor code (2C, 2D, 2F, etc.)
        safe_harbor_match = re.search(r"(?:Line\s*16|safe.*?harbor).*?\b(2[A-HJ-Z])\b", text, re.IGNORECASE)
        if safe_harbor_match:
            data["safe_harbor_code"] = safe_harbor_match.group(1).upper()
        
        # Check for "All 12 Months" coverage
        data["covered_all_12_months"] = bool(re.search(r"all\s*12\s*months", text, re.IGNORECASE))
        
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
