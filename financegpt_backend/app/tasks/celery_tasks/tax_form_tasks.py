"""Celery tasks for tax form parsing."""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.config import config

logger = logging.getLogger(__name__)


def get_celery_session_maker():
    """
    Create a new async session maker for Celery tasks.
    Uses NullPool to avoid connection pooling issues in Celery workers.
    """
    engine = create_async_engine(
        config.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    return async_sessionmaker(engine, expire_on_commit=False)


@celery_app.task(name="parse_tax_form", bind=True)
def parse_tax_form_task(
    self,
    tax_form_id: str,
    file_path: str | None,
    form_type: str,
    tax_year: int,
    user_id: str,
    search_space_id: int,
    extracted_text: str | None = None,
):
    """
    Celery task to parse an uploaded tax form and extract structured data.
    
    Args:
        tax_form_id: UUID of the tax_form record
        file_path: Path to the uploaded PDF file (optional if extracted_text provided)
        form_type: Type of tax form (W2, 1099-MISC, etc.)
        tax_year: Tax year for the form
        user_id: User ID who uploaded the form
        search_space_id: Search space ID for LLM config lookup
        extracted_text: Pre-extracted text content (used if file_path not available)
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            _parse_tax_form(
                tax_form_id=tax_form_id,
                file_path=file_path,
                form_type=form_type,
                tax_year=tax_year,
                user_id=user_id,
                search_space_id=search_space_id,
                extracted_text=extracted_text,
            )
        )
    finally:
        loop.close()


async def _parse_tax_form(
    tax_form_id: str,
    file_path: str | None,
    form_type: str,
    tax_year: int,
    user_id: str,
    search_space_id: int,
    extracted_text: str | None = None,
):
    """Parse tax form and save extracted data to database."""
    from datetime import datetime, timezone
    from decimal import Decimal
    import hashlib
    
    from app.db import (
        TaxForm,
        W2Form,
        Form1099Misc,
        Form1099Int,
        Form1099Div,
        Form1099B,
    )
    from app.parsers.tax_form_parser import TaxFormParser
    from app.services.llm_service import get_document_summary_llm
    
    async with get_celery_session_maker()() as session:
        try:
            # Get the user's configured LLM model string for document processing
            llm_model = None
            try:
                user_llm = await get_document_summary_llm(session, search_space_id)
                if user_llm:
                    llm_model = user_llm.model
                    logger.info(f"Using user's configured LLM for tax parsing: {llm_model}")
            except Exception as e:
                logger.warning(f"Could not get user LLM config, using default: {e}")
            
            # Get the tax form record
            result = await session.execute(
                select(TaxForm).where(TaxForm.id == UUID(tax_form_id))
            )
            tax_form = result.scalar_one_or_none()
            
            if not tax_form:
                logger.error(f"Tax form record not found: {tax_form_id}")
                return
            
            logger.info(f"Starting tax form parsing for {form_type} (ID: {tax_form_id})")
            
            # Initialize parser and parse the form
            parser = TaxFormParser()
            
            # If we have pre-extracted text, use it directly
            if extracted_text and not file_path:
                logger.info(f"Using pre-extracted text for {form_type} parsing")
                parse_result = await parser.parse_from_text(
                    text=extracted_text,
                    form_type=form_type,
                    tax_year=tax_year,
                    llm_model=llm_model,
                )
            else:
                parse_result = await parser.parse_tax_form(
                    file_path=file_path,
                    form_type=form_type,
                    tax_year=tax_year,
                    llm_model=llm_model,
                )
            
            extracted_data = parse_result.get("extracted_data", {})
            confidence_scores = parse_result.get("confidence_scores", {})
            extraction_method = parse_result.get("extraction_method", "unknown")
            needs_review = parse_result.get("needs_review", True)
            raw_data = parse_result.get("raw_extraction_data", {})
            
            logger.info(
                f"Parsed {form_type}: method={extraction_method}, "
                f"fields_extracted={len(extracted_data)}, needs_review={needs_review}"
            )
            
            # Save extracted data to the appropriate form table
            if form_type == "W2":
                await _save_w2_data(
                    session, tax_form.id, extracted_data, confidence_scores, raw_data
                )
            elif form_type == "1099-MISC":
                await _save_1099_misc_data(
                    session, tax_form.id, extracted_data, confidence_scores, raw_data
                )
            elif form_type == "1099-INT":
                await _save_1099_int_data(
                    session, tax_form.id, extracted_data, confidence_scores, raw_data
                )
            elif form_type == "1099-DIV":
                await _save_1099_div_data(
                    session, tax_form.id, extracted_data, confidence_scores, raw_data
                )
            elif form_type == "1099-B":
                await _save_1099_b_data(
                    session, tax_form.id, extracted_data, confidence_scores, raw_data
                )
            
            # Update tax form status
            tax_form.processing_status = "review_needed" if needs_review else "completed"
            tax_form.extraction_method = extraction_method
            tax_form.needs_review = needs_review
            tax_form.processed_at = datetime.now(timezone.utc)
            
            await session.commit()
            logger.info(f"Tax form parsing completed for {form_type} (ID: {tax_form_id})")
            
        except FileNotFoundError as e:
            logger.error(f"Tax form file not found: {file_path}")
            await _mark_tax_form_failed(session, tax_form_id, str(e))
            
        except Exception as e:
            logger.exception(f"Error parsing tax form {tax_form_id}: {e}")
            await _mark_tax_form_failed(session, tax_form_id, str(e))


async def _mark_tax_form_failed(session, tax_form_id: str, error_message: str):
    """Mark tax form as failed."""
    from app.db import TaxForm
    
    result = await session.execute(
        select(TaxForm).where(TaxForm.id == UUID(tax_form_id))
    )
    tax_form = result.scalar_one_or_none()
    
    if tax_form:
        tax_form.processing_status = "failed"
        # Store error in extraction_method field as fallback (truncate to fit VARCHAR(50))
        tax_form.extraction_method = f"error: {error_message[:40]}"
        await session.commit()
        logger.error(f"Marked tax form {tax_form_id} as failed: {error_message}")


def _hash_pii(value: Optional[str]) -> Optional[str]:
    """Hash PII values for secure storage."""
    if not value:
        return None
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


async def _save_w2_data(session, tax_form_id: UUID, data: dict, confidence: dict, raw_data: dict):
    """Save extracted W2 data to database."""
    from app.db import W2Form
    from decimal import Decimal
    
    w2 = W2Form(
        tax_form_id=tax_form_id,
        # Wage information
        wages_tips_compensation=_to_decimal(data.get("wages_tips_compensation")),
        federal_income_tax_withheld=_to_decimal(data.get("federal_income_tax_withheld")),
        social_security_wages=_to_decimal(data.get("social_security_wages")),
        social_security_tax_withheld=_to_decimal(data.get("social_security_tax_withheld")),
        medicare_wages=_to_decimal(data.get("medicare_wages")),
        medicare_tax_withheld=_to_decimal(data.get("medicare_tax_withheld")),
        social_security_tips=_to_decimal(data.get("social_security_tips")),
        allocated_tips=_to_decimal(data.get("allocated_tips")),
        dependent_care_benefits=_to_decimal(data.get("dependent_care_benefits")),
        nonqualified_plans=_to_decimal(data.get("nonqualified_plans")),
        # State/local
        state_wages=_to_decimal(data.get("state_wages")),
        state_income_tax=_to_decimal(data.get("state_income_tax")),
        local_wages=_to_decimal(data.get("local_wages")),
        local_income_tax=_to_decimal(data.get("local_income_tax")),
        state_code=data.get("state_code"),
        locality_name=data.get("locality_name"),
        # Checkboxes
        statutory_employee=data.get("statutory_employee", False),
        retirement_plan=data.get("retirement_plan", False),
        third_party_sick_pay=data.get("third_party_sick_pay", False),
        # Box 12 codes
        box_12_codes=data.get("box_12_codes"),
        # PII (hashed)
        employee_ssn_hash=_hash_pii(data.get("employee_ssn")),
        employer_ein_hash=_hash_pii(data.get("employer_ein")),
        employer_name=data.get("employer_name"),
        employer_address=data.get("employer_address"),
        employee_name_masked="[EMPLOYEE_NAME]",  # Always mask for UI
        # Metadata
        field_confidence_scores=confidence,
        raw_extraction_data=raw_data,
    )
    
    session.add(w2)
    await session.flush()
    logger.info(f"Saved W2 form data for tax_form_id={tax_form_id}")


async def _save_1099_misc_data(session, tax_form_id: UUID, data: dict, confidence: dict, raw_data: dict):
    """Save extracted 1099-MISC data to database."""
    from app.db import Form1099Misc
    
    form = Form1099Misc(
        tax_form_id=tax_form_id,
        payer_name=data.get("payer_name"),
        payer_tin_hash=_hash_pii(data.get("payer_tin")),
        payer_address=data.get("payer_address"),
        recipient_tin_hash=_hash_pii(data.get("recipient_tin")),
        rents=_to_decimal(data.get("rents")),
        royalties=_to_decimal(data.get("royalties")),
        other_income=_to_decimal(data.get("other_income")),
        federal_income_tax_withheld=_to_decimal(data.get("federal_income_tax_withheld")),
        fishing_boat_proceeds=_to_decimal(data.get("fishing_boat_proceeds")),
        medical_health_payments=_to_decimal(data.get("medical_health_payments")),
        substitute_payments=_to_decimal(data.get("substitute_payments")),
        crop_insurance_proceeds=_to_decimal(data.get("crop_insurance_proceeds")),
        gross_proceeds_attorney=_to_decimal(data.get("gross_proceeds_attorney")),
        section_409a_deferrals=_to_decimal(data.get("section_409a_deferrals")),
        state_tax_withheld=_to_decimal(data.get("state_tax_withheld")),
        state_payer_number=data.get("state_payer_number"),
        state_income=_to_decimal(data.get("state_income")),
        field_confidence_scores=confidence,
        raw_extraction_data=raw_data,
    )
    
    session.add(form)
    await session.flush()
    logger.info(f"Saved 1099-MISC data for tax_form_id={tax_form_id}")


async def _save_1099_int_data(session, tax_form_id: UUID, data: dict, confidence: dict, raw_data: dict):
    """Save extracted 1099-INT data to database."""
    from app.db import Form1099Int
    
    form = Form1099Int(
        tax_form_id=tax_form_id,
        payer_name=data.get("payer_name"),
        payer_tin_hash=_hash_pii(data.get("payer_tin")),
        payer_address=data.get("payer_address"),
        recipient_tin_hash=_hash_pii(data.get("recipient_tin")),
        interest_income=_to_decimal(data.get("interest_income")),
        early_withdrawal_penalty=_to_decimal(data.get("early_withdrawal_penalty")),
        interest_on_us_savings_bonds=_to_decimal(data.get("interest_on_us_savings_bonds")),
        federal_income_tax_withheld=_to_decimal(data.get("federal_income_tax_withheld")),
        investment_expenses=_to_decimal(data.get("investment_expenses")),
        foreign_tax_paid=_to_decimal(data.get("foreign_tax_paid")),
        foreign_country=data.get("foreign_country"),
        tax_exempt_interest=_to_decimal(data.get("tax_exempt_interest")),
        specified_private_activity_bond_interest=_to_decimal(data.get("specified_private_activity_bond_interest")),
        market_discount=_to_decimal(data.get("market_discount")),
        bond_premium=_to_decimal(data.get("bond_premium")),
        bond_premium_on_treasury=_to_decimal(data.get("bond_premium_on_treasury")),
        bond_premium_on_tax_exempt=_to_decimal(data.get("bond_premium_on_tax_exempt")),
        state_code=data.get("state_code"),
        state_id=data.get("state_id"),
        state_tax_withheld=_to_decimal(data.get("state_tax_withheld")),
        field_confidence_scores=confidence,
        raw_extraction_data=raw_data,
    )
    
    session.add(form)
    await session.flush()
    logger.info(f"Saved 1099-INT data for tax_form_id={tax_form_id}")


async def _save_1099_div_data(session, tax_form_id: UUID, data: dict, confidence: dict, raw_data: dict):
    """Save extracted 1099-DIV data to database."""
    from app.db import Form1099Div
    
    form = Form1099Div(
        tax_form_id=tax_form_id,
        payer_name=data.get("payer_name"),
        payer_tin_hash=_hash_pii(data.get("payer_tin")),
        payer_address=data.get("payer_address"),
        recipient_tin_hash=_hash_pii(data.get("recipient_tin")),
        total_ordinary_dividends=_to_decimal(data.get("total_ordinary_dividends")),
        qualified_dividends=_to_decimal(data.get("qualified_dividends")),
        total_capital_gain_distributions=_to_decimal(data.get("total_capital_gain_distributions")),
        unrecaptured_section_1250_gain=_to_decimal(data.get("unrecaptured_section_1250_gain")),
        section_1202_gain=_to_decimal(data.get("section_1202_gain")),
        collectibles_28_gain=_to_decimal(data.get("collectibles_28_gain")),
        section_897_ordinary_dividends=_to_decimal(data.get("section_897_ordinary_dividends")),
        section_897_capital_gain=_to_decimal(data.get("section_897_capital_gain")),
        nondividend_distributions=_to_decimal(data.get("nondividend_distributions")),
        federal_income_tax_withheld=_to_decimal(data.get("federal_income_tax_withheld")),
        section_199a_dividends=_to_decimal(data.get("section_199a_dividends")),
        investment_expenses=_to_decimal(data.get("investment_expenses")),
        foreign_tax_paid=_to_decimal(data.get("foreign_tax_paid")),
        foreign_country=data.get("foreign_country"),
        cash_liquidation_distributions=_to_decimal(data.get("cash_liquidation_distributions")),
        noncash_liquidation_distributions=_to_decimal(data.get("noncash_liquidation_distributions")),
        exempt_interest_dividends=_to_decimal(data.get("exempt_interest_dividends")),
        specified_private_activity_bond_interest_dividends=_to_decimal(data.get("specified_private_activity_bond_interest_dividends")),
        state_tax_withheld=_to_decimal(data.get("state_tax_withheld")),
        field_confidence_scores=confidence,
        raw_extraction_data=raw_data,
    )
    
    session.add(form)
    await session.flush()
    logger.info(f"Saved 1099-DIV data for tax_form_id={tax_form_id}")


async def _save_1099_b_data(session, tax_form_id: UUID, data: dict, confidence: dict, raw_data: dict):
    """Save extracted 1099-B data to database."""
    from app.db import Form1099B
    
    form = Form1099B(
        tax_form_id=tax_form_id,
        payer_name=data.get("broker_name") or data.get("payer_name"),
        payer_tin_hash=_hash_pii(data.get("broker_tin") or data.get("payer_tin")),
        payer_address=data.get("broker_address") or data.get("payer_address"),
        recipient_tin_hash=_hash_pii(data.get("recipient_tin")),
        description_of_property=data.get("description_of_property"),
        date_acquired=data.get("date_acquired"),
        date_sold=data.get("date_sold"),
        proceeds=_to_decimal(data.get("proceeds")),
        cost_basis=_to_decimal(data.get("cost_basis")),
        accrued_market_discount=_to_decimal(data.get("accrued_market_discount")),
        wash_sale_loss_disallowed=_to_decimal(data.get("wash_sale_loss_disallowed") or data.get("wash_sale_loss")),
        federal_income_tax_withheld=_to_decimal(data.get("federal_income_tax_withheld")),
        # Form 8949 checkboxes
        short_term_box_a=data.get("short_term_box_a", False),
        short_term_box_b=data.get("short_term_box_b", False),
        short_term_box_c=data.get("short_term_box_c", False),
        long_term_box_d=data.get("long_term_box_d", False),
        long_term_box_e=data.get("long_term_box_e", False),
        long_term_box_f=data.get("long_term_box_f", False),
        loss_not_allowed=data.get("loss_not_allowed", False),
        noncovered_security=data.get("noncovered_security", False),
        basis_reported_to_irs=data.get("basis_reported_to_irs", False),
        state_code=data.get("state_code"),
        state_id=data.get("state_id"),
        state_tax_withheld=_to_decimal(data.get("state_tax_withheld")),
        field_confidence_scores=confidence,
        raw_extraction_data=raw_data,
    )
    
    session.add(form)
    await session.flush()
    logger.info(f"Saved 1099-B data for tax_form_id={tax_form_id}")


def _to_decimal(value) -> Decimal | None:
    """Convert value to Decimal, handling various formats."""
    from decimal import InvalidOperation
    
    if value is None:
        return None
    
    if isinstance(value, Decimal):
        return value
    
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    
    if isinstance(value, str):
        # Remove currency symbols, commas, spaces
        cleaned = value.replace("$", "").replace(",", "").replace(" ", "").strip()
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    
    return None
