"""Pydantic schemas for tax forms."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# Base Tax Form Schema
class TaxFormBase(BaseModel):
    """Base schema for all tax forms."""
    
    form_type: Literal["W2", "1099-MISC", "1099-INT", "1099-DIV", "1099-B"]
    tax_year: int = Field(ge=1900, le=2100)
    
    @field_validator("tax_year")
    @classmethod
    def validate_tax_year(cls, v: int) -> int:
        """Validate tax year is reasonable."""
        current_year = datetime.now().year
        if v > current_year + 1:
            raise ValueError(f"Tax year cannot be more than {current_year + 1}")
        return v


class TaxFormCreate(TaxFormBase):
    """Schema for creating a tax form."""
    
    search_space_id: int
    document_id: Optional[int] = None


class TaxFormResponse(TaxFormBase):
    """Response schema for tax form."""
    
    id: UUID
    user_id: UUID
    search_space_id: int
    document_id: Optional[int] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    processing_status: Literal["pending", "processing", "completed", "failed", "needs_review"]
    extraction_method: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    needs_review: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# W2 Form Schemas
class W2Box12Code(BaseModel):
    """Box 12 code entry on W2."""
    
    code: str = Field(max_length=2)
    amount: Decimal = Field(ge=0, decimal_places=2)


class W2FormBase(BaseModel):
    """Base schema for W2 form data."""
    
    # Employer info (masked)
    employer_name: Optional[str] = None
    employer_ein_hash: Optional[str] = None
    employer_address: Optional[str] = None
    
    # Wage information
    wages_tips_compensation: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    federal_income_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    social_security_wages: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    social_security_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    medicare_wages: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    medicare_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    social_security_tips: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    allocated_tips: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    
    # Other compensation
    dependent_care_benefits: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    nonqualified_plans: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    
    # Box 12 codes
    box_12_codes: Optional[list[W2Box12Code]] = None
    
    # Box 13 checkboxes
    statutory_employee: bool = False
    retirement_plan: bool = False
    third_party_sick_pay: bool = False
    
    # State/Local tax
    state_code: Optional[str] = Field(None, max_length=2)
    state_wages: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    state_income_tax: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    local_wages: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    local_income_tax: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    locality_name: Optional[str] = Field(None, max_length=100)


class W2FormCreate(W2FormBase):
    """Schema for creating W2 form."""
    
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    raw_extraction_data: Optional[dict[str, Any]] = None


class W2FormResponse(W2FormBase):
    """Response schema for W2 form."""
    
    id: UUID
    tax_form_id: UUID
    employee_name_masked: Optional[str] = None
    employee_ssn_hash: Optional[str] = None
    field_confidence_scores: Optional[dict[str, float]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 1099-MISC Form Schemas
class Form1099MiscBase(BaseModel):
    """Base schema for 1099-MISC form."""
    
    payer_name: Optional[str] = None
    payer_tin_hash: Optional[str] = None
    payer_address: Optional[str] = None
    
    rents: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    royalties: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    other_income: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    federal_income_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    fishing_boat_proceeds: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    medical_health_payments: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    substitute_payments: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    crop_insurance_proceeds: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    gross_proceeds_attorney: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    section_409a_deferrals: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    state_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    state_payer_number: Optional[str] = Field(None, max_length=50)
    state_income: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class Form1099MiscCreate(Form1099MiscBase):
    """Schema for creating 1099-MISC form."""
    
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    raw_extraction_data: Optional[dict[str, Any]] = None


class Form1099MiscResponse(Form1099MiscBase):
    """Response schema for 1099-MISC form."""
    
    id: UUID
    tax_form_id: UUID
    recipient_tin_hash: Optional[str] = None
    field_confidence_scores: Optional[dict[str, float]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 1099-INT Form Schemas
class Form1099IntBase(BaseModel):
    """Base schema for 1099-INT form."""
    
    payer_name: Optional[str] = None
    payer_tin_hash: Optional[str] = None
    
    interest_income: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    early_withdrawal_penalty: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    interest_us_savings_bonds: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    federal_income_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    investment_expenses: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    foreign_tax_paid: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    foreign_country: Optional[str] = Field(None, max_length=100)
    tax_exempt_interest: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    specified_private_activity_bond_interest: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    market_discount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    bond_premium: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    bond_premium_treasury: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    tax_exempt_bond_premium: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class Form1099IntCreate(Form1099IntBase):
    """Schema for creating 1099-INT form."""
    
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    raw_extraction_data: Optional[dict[str, Any]] = None


class Form1099IntResponse(Form1099IntBase):
    """Response schema for 1099-INT form."""
    
    id: UUID
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 1099-DIV Form Schemas
class Form1099DivBase(BaseModel):
    """Base schema for 1099-DIV form."""
    
    payer_name: Optional[str] = None
    payer_tin_hash: Optional[str] = None
    
    total_ordinary_dividends: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    qualified_dividends: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    total_capital_gain_distributions: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    unrecaptured_section_1250_gain: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    section_1202_gain: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    collectibles_gain: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    nondividend_distributions: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    federal_income_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    section_199a_dividends: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    investment_expenses: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    foreign_tax_paid: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    foreign_country: Optional[str] = Field(None, max_length=100)
    cash_liquidation_distributions: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    noncash_liquidation_distributions: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class Form1099DivCreate(Form1099DivBase):
    """Schema for creating 1099-DIV form."""
    
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    raw_extraction_data: Optional[dict[str, Any]] = None


class Form1099DivResponse(Form1099DivBase):
    """Response schema for 1099-DIV form."""
    
    id: UUID
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# 1099-B Form Schemas
class Form1099BBase(BaseModel):
    """Base schema for 1099-B form."""
    
    payer_name: Optional[str] = None
    payer_tin_hash: Optional[str] = None
    
    description_of_property: Optional[str] = None
    date_acquired: Optional[date] = None
    date_sold: Optional[date] = None
    proceeds: Optional[Decimal] = Field(None, decimal_places=2)
    cost_basis: Optional[Decimal] = Field(None, decimal_places=2)
    adjustments_to_basis: Optional[Decimal] = Field(None, decimal_places=2)
    realized_gain_loss: Optional[Decimal] = Field(None, decimal_places=2)
    federal_income_tax_withheld: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    
    short_term: Optional[bool] = None
    long_term: Optional[bool] = None
    basis_reported_to_irs: Optional[bool] = None
    noncovered_security: Optional[bool] = None


class Form1099BCreate(Form1099BBase):
    """Schema for creating 1099-B form."""
    
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    raw_extraction_data: Optional[dict[str, Any]] = None


class Form1099BResponse(Form1099BBase):
    """Response schema for 1099-B form."""
    
    id: UUID
    tax_form_id: UUID
    field_confidence_scores: Optional[dict[str, float]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Combined response with form details
class TaxFormWithDetails(TaxFormResponse):
    """Tax form response with nested form-specific details."""
    
    w2_form: Optional[W2FormResponse] = None
    form_1099_misc: Optional[Form1099MiscResponse] = None
    form_1099_int: Optional[Form1099IntResponse] = None
    form_1099_div: Optional[Form1099DivResponse] = None
    form_1099_b: Optional[Form1099BResponse] = None
