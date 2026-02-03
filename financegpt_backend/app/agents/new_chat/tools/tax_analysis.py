"""Tax analysis tool for the agent.

This tool allows the agent to query structured tax form data to answer questions like:
- "How much did I earn in 2024?"
- "What was my total federal tax withheld?"
- "Did I have any interest income?"
- "What were my capital gains from stock sales?"
- "Can you estimate my tax refund?"
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import (
    TaxForm,
    W2Form,
    Form1099Misc,
    Form1099Int,
    Form1099Div,
    Form1099B,
)

logger = logging.getLogger(__name__)


# 2024 Federal Tax Brackets (Single Filers)
TAX_BRACKETS_2024_SINGLE = [
    (11600, Decimal("0.10")),    # 10% up to $11,600
    (47150, Decimal("0.12")),    # 12% up to $47,150
    (100525, Decimal("0.22")),   # 22% up to $100,525
    (191950, Decimal("0.24")),   # 24% up to $191,950
    (243725, Decimal("0.32")),   # 32% up to $243,725
    (609350, Decimal("0.35")),   # 35% up to $609,350
    (float('inf'), Decimal("0.37")),  # 37% above $609,350
]

# Standard Deduction 2024
STANDARD_DEDUCTION_2024 = Decimal("14600")


def create_tax_analysis_tool(user_id: str, search_space_id: int, db_session: AsyncSession):
    """Create the tax analysis tool for the agent.
    
    Args:
        user_id: User ID (UUID string)
        search_space_id: Search space ID
        db_session: Database session
        
    Returns:
        Configured tax analysis tool
    """
    
    @tool
    async def analyze_tax_data(
        query_type: str,
        tax_year: int | None = None,
        form_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Query uploaded tax forms to answer tax-related questions.
        
        Use this tool when users ask about income, taxes withheld, interest, dividends,
        capital gains, W2 employment information, or tax estimates/refunds from their 
        uploaded tax documents.
        
        Args:
            query_type: Type of tax analysis:
                - "income_summary": Total income across all sources
                - "tax_summary": Total taxes withheld from all sources
                - "interest_income": Interest income from 1099-INT forms
                - "dividends_income": Dividend income from 1099-DIV forms
                - "capital_gains": Capital gains from 1099-B forms
                - "w2_summary": W2 wage and withholding summary
                - "all_forms": List all tax forms
                - "tax_estimate": Estimate tax liability and potential refund
            tax_year: Specific tax year (e.g., 2024) or None for all years
            form_types: Optional list of form types to filter (e.g., ["W2", "1099-INT"])
            
        Returns:
            Dictionary with analysis results including totals, breakdowns, and details
        """
        return await _analyze_tax_data_impl(
            db_session=db_session,
            user_id=user_id,
            search_space_id=search_space_id,
            query_type=query_type,
            tax_year=tax_year,
            form_types=form_types,
        )
    
    return analyze_tax_data


async def _analyze_tax_data_impl(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    query_type: str,
    tax_year: int | None = None,
    form_types: list[str] | None = None,
) -> dict[str, Any]:
    """Implementation of tax data analysis."""
    
    if query_type == "income_summary":
        return await _get_income_summary(db_session, user_id, search_space_id, tax_year)
    elif query_type == "tax_summary":
        return await _get_tax_summary(db_session, user_id, search_space_id, tax_year)
    elif query_type == "interest_income":
        return await _get_interest_income(db_session, user_id, search_space_id, tax_year)
    elif query_type == "dividends_income":
        return await _get_dividends_income(db_session, user_id, search_space_id, tax_year)
    elif query_type == "capital_gains":
        return await _get_capital_gains(db_session, user_id, search_space_id, tax_year)
    elif query_type == "w2_summary":
        return await _get_w2_summary(db_session, user_id, search_space_id, tax_year)
    elif query_type == "all_forms":
        return await _get_all_forms(db_session, user_id, search_space_id, tax_year, form_types)
    elif query_type == "tax_estimate":
        return await _get_tax_estimate(db_session, user_id, search_space_id, tax_year)
    else:
        return {"error": f"Unknown query type: {query_type}"}


async def _get_w2_summary(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get W2 summary with actual database queries."""
    try:
        # Build query for tax forms with W2 data
        query = (
            select(TaxForm)
            .options(selectinload(TaxForm.w2_form))
            .where(
                and_(
                    TaxForm.user_id == UUID(user_id),
                    TaxForm.search_space_id == search_space_id,
                    TaxForm.form_type == "W2",
                )
            )
        )
        
        if tax_year:
            query = query.where(TaxForm.tax_year == tax_year)
        
        query = query.order_by(TaxForm.tax_year.desc())
        
        result = await db_session.execute(query)
        tax_forms = result.scalars().all()
        
        if not tax_forms:
            return {
                "query_type": "w2_summary",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No W2 forms found. Upload your W2s to see employment income and withholdings.",
            }
        
        # Aggregate data
        employers = []
        total_wages = Decimal("0.00")
        total_federal_withheld = Decimal("0.00")
        total_ss_withheld = Decimal("0.00")
        total_medicare_withheld = Decimal("0.00")
        total_state_withheld = Decimal("0.00")
        
        for form in tax_forms:
            w2 = form.w2_form
            if w2:
                employer_info = {
                    "employer_name": w2.employer_name or "Unknown Employer",
                    "tax_year": form.tax_year,
                    "wages": float(w2.wages_tips_compensation or 0),
                    "federal_withheld": float(w2.federal_income_tax_withheld or 0),
                    "social_security_withheld": float(w2.social_security_tax_withheld or 0),
                    "medicare_withheld": float(w2.medicare_tax_withheld or 0),
                    "state_withheld": float(w2.state_income_tax or 0),
                    "retirement_plan": w2.retirement_plan,
                    "processing_status": form.processing_status,
                    "needs_review": form.needs_review,
                }
                employers.append(employer_info)
                
                total_wages += w2.wages_tips_compensation or Decimal("0.00")
                total_federal_withheld += w2.federal_income_tax_withheld or Decimal("0.00")
                total_ss_withheld += w2.social_security_tax_withheld or Decimal("0.00")
                total_medicare_withheld += w2.medicare_tax_withheld or Decimal("0.00")
                total_state_withheld += w2.state_income_tax or Decimal("0.00")
        
        return {
            "query_type": "w2_summary",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "employers": employers,
            "total_wages": float(total_wages),
            "total_federal_withheld": float(total_federal_withheld),
            "total_social_security_withheld": float(total_ss_withheld),
            "total_medicare_withheld": float(total_medicare_withheld),
            "total_state_withheld": float(total_state_withheld),
            "total_w2_forms": len(employers),
        }
    except Exception as e:
        logger.exception("Error getting W2 summary")
        return {
            "query_type": "w2_summary",
            "error": str(e),
        }


async def _get_income_summary(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get total income across all sources."""
    try:
        w2_data = await _get_w2_summary(db_session, user_id, search_space_id, tax_year)
        interest_data = await _get_interest_income(db_session, user_id, search_space_id, tax_year)
        dividend_data = await _get_dividends_income(db_session, user_id, search_space_id, tax_year)
        capital_gains_data = await _get_capital_gains(db_session, user_id, search_space_id, tax_year)
        misc_data = await _get_misc_income(db_session, user_id, search_space_id, tax_year)
        
        total_w2_wages = w2_data.get("total_wages", 0) if w2_data.get("has_data") else 0
        total_interest = interest_data.get("total_interest", 0) if interest_data.get("has_data") else 0
        total_dividends = dividend_data.get("total_ordinary_dividends", 0) if dividend_data.get("has_data") else 0
        total_capital_gains = capital_gains_data.get("net_capital_gains", 0) if capital_gains_data.get("has_data") else 0
        total_misc = misc_data.get("total_misc_income", 0) if misc_data.get("has_data") else 0
        
        grand_total = total_w2_wages + total_interest + total_dividends + total_capital_gains + total_misc
        
        has_any_data = any([
            w2_data.get("has_data"),
            interest_data.get("has_data"),
            dividend_data.get("has_data"),
            capital_gains_data.get("has_data"),
            misc_data.get("has_data"),
        ])
        
        if not has_any_data:
            return {
                "query_type": "income_summary",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No tax forms uploaded yet. Please upload your W2 and 1099 forms to see income summary.",
            }
        
        return {
            "query_type": "income_summary",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "total_w2_wages": total_w2_wages,
            "total_interest_income": total_interest,
            "total_dividend_income": total_dividends,
            "total_capital_gains": total_capital_gains,
            "total_misc_income": total_misc,
            "grand_total_income": grand_total,
            "breakdown": {
                "w2": w2_data,
                "interest": interest_data,
                "dividends": dividend_data,
                "capital_gains": capital_gains_data,
                "misc": misc_data,
            },
        }
    except Exception as e:
        logger.exception("Error getting income summary")
        return {"query_type": "income_summary", "error": str(e)}


async def _get_tax_summary(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get total taxes withheld across all sources."""
    try:
        w2_data = await _get_w2_summary(db_session, user_id, search_space_id, tax_year)
        interest_data = await _get_interest_income(db_session, user_id, search_space_id, tax_year)
        dividend_data = await _get_dividends_income(db_session, user_id, search_space_id, tax_year)
        
        total_federal = w2_data.get("total_federal_withheld", 0) if w2_data.get("has_data") else 0
        total_federal += interest_data.get("total_federal_withheld", 0) if interest_data.get("has_data") else 0
        total_federal += dividend_data.get("total_federal_withheld", 0) if dividend_data.get("has_data") else 0
        
        total_ss = w2_data.get("total_social_security_withheld", 0) if w2_data.get("has_data") else 0
        total_medicare = w2_data.get("total_medicare_withheld", 0) if w2_data.get("has_data") else 0
        total_state = w2_data.get("total_state_withheld", 0) if w2_data.get("has_data") else 0
        
        has_data = w2_data.get("has_data") or interest_data.get("has_data") or dividend_data.get("has_data")
        
        if not has_data:
            return {
                "query_type": "tax_summary",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No tax forms uploaded yet. Please upload your W2 and 1099 forms to see tax withholdings.",
            }
        
        return {
            "query_type": "tax_summary",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "total_federal_withheld": total_federal,
            "total_social_security_withheld": total_ss,
            "total_medicare_withheld": total_medicare,
            "total_state_withheld": total_state,
            "grand_total_withheld": total_federal + total_ss + total_medicare + total_state,
        }
    except Exception as e:
        logger.exception("Error getting tax summary")
        return {"query_type": "tax_summary", "error": str(e)}


async def _get_interest_income(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get interest income from 1099-INT forms."""
    try:
        query = (
            select(TaxForm)
            .options(selectinload(TaxForm.form_1099_int))
            .where(
                and_(
                    TaxForm.user_id == UUID(user_id),
                    TaxForm.search_space_id == search_space_id,
                    TaxForm.form_type == "1099-INT",
                )
            )
        )
        
        if tax_year:
            query = query.where(TaxForm.tax_year == tax_year)
        
        result = await db_session.execute(query)
        tax_forms = result.scalars().all()
        
        if not tax_forms:
            return {
                "query_type": "interest_income",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No 1099-INT forms found. Upload your interest income statements to see details.",
            }
        
        sources = []
        total_interest = Decimal("0.00")
        total_federal_withheld = Decimal("0.00")
        
        for form in tax_forms:
            int_form = form.form_1099_int
            if int_form:
                source_info = {
                    "payer_name": int_form.payer_name or "Unknown Payer",
                    "tax_year": form.tax_year,
                    "interest_income": float(int_form.interest_income or 0),
                    "federal_withheld": float(int_form.federal_income_tax_withheld or 0),
                }
                sources.append(source_info)
                
                total_interest += int_form.interest_income or Decimal("0.00")
                total_federal_withheld += int_form.federal_income_tax_withheld or Decimal("0.00")
        
        return {
            "query_type": "interest_income",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "total_interest": float(total_interest),
            "total_federal_withheld": float(total_federal_withheld),
            "sources": sources,
        }
    except Exception as e:
        logger.exception("Error getting interest income")
        return {"query_type": "interest_income", "error": str(e)}


async def _get_dividends_income(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get dividend income from 1099-DIV forms."""
    try:
        query = (
            select(TaxForm)
            .options(selectinload(TaxForm.form_1099_div))
            .where(
                and_(
                    TaxForm.user_id == UUID(user_id),
                    TaxForm.search_space_id == search_space_id,
                    TaxForm.form_type == "1099-DIV",
                )
            )
        )
        
        if tax_year:
            query = query.where(TaxForm.tax_year == tax_year)
        
        result = await db_session.execute(query)
        tax_forms = result.scalars().all()
        
        if not tax_forms:
            return {
                "query_type": "dividends_income",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No 1099-DIV forms found. Upload your dividend income statements to see details.",
            }
        
        sources = []
        total_ordinary = Decimal("0.00")
        total_qualified = Decimal("0.00")
        total_capital_gain_dist = Decimal("0.00")
        total_federal_withheld = Decimal("0.00")
        
        for form in tax_forms:
            div_form = form.form_1099_div
            if div_form:
                source_info = {
                    "payer_name": div_form.payer_name or "Unknown Payer",
                    "tax_year": form.tax_year,
                    "ordinary_dividends": float(div_form.total_ordinary_dividends or 0),
                    "qualified_dividends": float(div_form.qualified_dividends or 0),
                    "capital_gain_distributions": float(div_form.total_capital_gain_distributions or 0),
                    "federal_withheld": float(div_form.federal_income_tax_withheld or 0),
                }
                sources.append(source_info)
                
                total_ordinary += div_form.total_ordinary_dividends or Decimal("0.00")
                total_qualified += div_form.qualified_dividends or Decimal("0.00")
                total_capital_gain_dist += div_form.total_capital_gain_distributions or Decimal("0.00")
                total_federal_withheld += div_form.federal_income_tax_withheld or Decimal("0.00")
        
        return {
            "query_type": "dividends_income",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "total_ordinary_dividends": float(total_ordinary),
            "total_qualified_dividends": float(total_qualified),
            "total_capital_gain_distributions": float(total_capital_gain_dist),
            "total_federal_withheld": float(total_federal_withheld),
            "sources": sources,
        }
    except Exception as e:
        logger.exception("Error getting dividends income")
        return {"query_type": "dividends_income", "error": str(e)}


async def _get_capital_gains(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get capital gains from 1099-B forms."""
    try:
        query = (
            select(TaxForm)
            .options(selectinload(TaxForm.form_1099_b))
            .where(
                and_(
                    TaxForm.user_id == UUID(user_id),
                    TaxForm.search_space_id == search_space_id,
                    TaxForm.form_type == "1099-B",
                )
            )
        )
        
        if tax_year:
            query = query.where(TaxForm.tax_year == tax_year)
        
        result = await db_session.execute(query)
        tax_forms = result.scalars().all()
        
        if not tax_forms:
            return {
                "query_type": "capital_gains",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No 1099-B forms found. Upload your brokerage statements to see capital gains.",
            }
        
        sources = []
        total_proceeds = Decimal("0.00")
        total_cost_basis = Decimal("0.00")
        
        for form in tax_forms:
            b_form = form.form_1099_b
            if b_form:
                proceeds = b_form.proceeds or Decimal("0.00")
                cost_basis = b_form.cost_basis or Decimal("0.00")
                gain_loss = proceeds - cost_basis
                
                source_info = {
                    "broker_name": b_form.payer_name or "Unknown Broker",
                    "tax_year": form.tax_year,
                    "proceeds": float(proceeds),
                    "cost_basis": float(cost_basis),
                    "gain_loss": float(gain_loss),
                }
                sources.append(source_info)
                
                total_proceeds += proceeds
                total_cost_basis += cost_basis
        
        net_gains = total_proceeds - total_cost_basis
        
        return {
            "query_type": "capital_gains",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "total_proceeds": float(total_proceeds),
            "total_cost_basis": float(total_cost_basis),
            "net_capital_gains": float(net_gains),
            "sources": sources,
        }
    except Exception as e:
        logger.exception("Error getting capital gains")
        return {"query_type": "capital_gains", "error": str(e)}


async def _get_misc_income(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Get miscellaneous income from 1099-MISC forms."""
    try:
        query = (
            select(TaxForm)
            .options(selectinload(TaxForm.form_1099_misc))
            .where(
                and_(
                    TaxForm.user_id == UUID(user_id),
                    TaxForm.search_space_id == search_space_id,
                    TaxForm.form_type == "1099-MISC",
                )
            )
        )
        
        if tax_year:
            query = query.where(TaxForm.tax_year == tax_year)
        
        result = await db_session.execute(query)
        tax_forms = result.scalars().all()
        
        if not tax_forms:
            return {
                "query_type": "misc_income",
                "tax_year": tax_year or "all years",
                "has_data": False,
            }
        
        sources = []
        total_misc = Decimal("0.00")
        
        for form in tax_forms:
            misc_form = form.form_1099_misc
            if misc_form:
                misc_income = (
                    (misc_form.rents or Decimal("0.00")) +
                    (misc_form.royalties or Decimal("0.00")) +
                    (misc_form.other_income or Decimal("0.00"))
                )
                
                source_info = {
                    "payer_name": misc_form.payer_name or "Unknown Payer",
                    "tax_year": form.tax_year,
                    "rents": float(misc_form.rents or 0),
                    "royalties": float(misc_form.royalties or 0),
                    "other_income": float(misc_form.other_income or 0),
                    "total": float(misc_income),
                }
                sources.append(source_info)
                total_misc += misc_income
        
        return {
            "query_type": "misc_income",
            "tax_year": tax_year or "all years",
            "has_data": True,
            "total_misc_income": float(total_misc),
            "sources": sources,
        }
    except Exception as e:
        logger.exception("Error getting misc income")
        return {"query_type": "misc_income", "error": str(e)}


async def _get_all_forms(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
    form_types: list[str] | None,
) -> dict[str, Any]:
    """Get all tax forms with optional filters."""
    try:
        query = (
            select(TaxForm)
            .where(
                and_(
                    TaxForm.user_id == UUID(user_id),
                    TaxForm.search_space_id == search_space_id,
                )
            )
            .order_by(TaxForm.tax_year.desc(), TaxForm.form_type)
        )
        
        if tax_year:
            query = query.where(TaxForm.tax_year == tax_year)
        
        if form_types:
            query = query.where(TaxForm.form_type.in_(form_types))
        
        result = await db_session.execute(query)
        tax_forms = result.scalars().all()
        
        if not tax_forms:
            return {
                "query_type": "all_forms",
                "tax_year": tax_year or "all years",
                "form_types_filter": form_types,
                "has_data": False,
                "total_forms": 0,
                "message": "No tax forms uploaded yet. Upload W2s and 1099s to get started.",
            }
        
        forms_list = [
            {
                "id": str(form.id),
                "form_type": form.form_type,
                "tax_year": form.tax_year,
                "processing_status": form.processing_status,
                "extraction_method": form.extraction_method,
                "needs_review": form.needs_review,
                "uploaded_at": form.uploaded_at.isoformat() if form.uploaded_at else None,
            }
            for form in tax_forms
        ]
        
        return {
            "query_type": "all_forms",
            "tax_year": tax_year or "all years",
            "form_types_filter": form_types,
            "has_data": True,
            "forms": forms_list,
            "total_forms": len(forms_list),
        }
    except Exception as e:
        logger.exception("Error getting all forms")
        return {"query_type": "all_forms", "error": str(e)}


async def _get_tax_estimate(
    db_session: AsyncSession,
    user_id: str,
    search_space_id: int,
    tax_year: int | None,
) -> dict[str, Any]:
    """Estimate tax liability and potential refund.
    
    This provides a simplified estimate based on single filer status.
    For accurate tax calculations, users should consult a tax professional.
    """
    try:
        # Get income summary first
        income_data = await _get_income_summary(db_session, user_id, search_space_id, tax_year)
        
        if not income_data.get("has_data"):
            return {
                "query_type": "tax_estimate",
                "tax_year": tax_year or "all years",
                "has_data": False,
                "message": "No tax forms uploaded yet. Please upload your W2 and 1099 forms to get a tax estimate.",
            }
        
        # Get withholdings
        tax_data = await _get_tax_summary(db_session, user_id, search_space_id, tax_year)
        
        # Calculate estimated tax
        gross_income = Decimal(str(income_data.get("grand_total_income", 0)))
        
        # Apply standard deduction
        taxable_income = max(Decimal("0.00"), gross_income - STANDARD_DEDUCTION_2024)
        
        # Calculate tax using brackets
        estimated_tax = _calculate_tax_from_brackets(taxable_income)
        
        # Get total withholdings
        total_withheld = Decimal(str(tax_data.get("total_federal_withheld", 0)))
        
        # Calculate refund/owed
        difference = total_withheld - estimated_tax
        
        if difference > 0:
            refund_or_owed = "refund"
            amount = float(difference)
        else:
            refund_or_owed = "owed"
            amount = float(abs(difference))
        
        return {
            "query_type": "tax_estimate",
            "tax_year": tax_year or 2024,
            "has_data": True,
            "disclaimer": "This is a simplified estimate assuming single filer status with standard deduction. For accurate calculations, please consult a tax professional.",
            "gross_income": float(gross_income),
            "standard_deduction": float(STANDARD_DEDUCTION_2024),
            "taxable_income": float(taxable_income),
            "estimated_federal_tax": float(estimated_tax),
            "total_federal_withheld": float(total_withheld),
            "estimate_result": refund_or_owed,
            "estimate_amount": amount,
            "breakdown": {
                "income": {
                    "w2_wages": income_data.get("total_w2_wages", 0),
                    "interest": income_data.get("total_interest_income", 0),
                    "dividends": income_data.get("total_dividend_income", 0),
                    "capital_gains": income_data.get("total_capital_gains", 0),
                    "misc_income": income_data.get("total_misc_income", 0),
                },
                "withholdings": {
                    "federal": tax_data.get("total_federal_withheld", 0),
                    "social_security": tax_data.get("total_social_security_withheld", 0),
                    "medicare": tax_data.get("total_medicare_withheld", 0),
                    "state": tax_data.get("total_state_withheld", 0),
                },
            },
        }
    except Exception as e:
        logger.exception("Error calculating tax estimate")
        return {"query_type": "tax_estimate", "error": str(e)}


def _calculate_tax_from_brackets(taxable_income: Decimal) -> Decimal:
    """Calculate federal tax using progressive brackets."""
    if taxable_income <= 0:
        return Decimal("0.00")
    
    tax = Decimal("0.00")
    prev_bracket = Decimal("0")
    
    for bracket_max, rate in TAX_BRACKETS_2024_SINGLE:
        bracket_max_decimal = Decimal(str(bracket_max))
        
        if taxable_income <= bracket_max_decimal:
            tax += (taxable_income - prev_bracket) * rate
            break
        else:
            tax += (bracket_max_decimal - prev_bracket) * rate
            prev_bracket = bracket_max_decimal
    
    return tax.quantize(Decimal("0.01"))
