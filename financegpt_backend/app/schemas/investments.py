"""Pydantic schemas for investment holdings and accounts."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssetType(str, Enum):
    """Investment asset types."""
    STOCK = "stock"
    BOND = "bond"
    MUTUAL_FUND = "mutual_fund"
    ETF = "etf"
    CRYPTO = "crypto"
    OPTION = "option"
    OTHER = "other"


class AccountTaxType(str, Enum):
    """Account tax treatment types."""
    TAXABLE = "taxable"
    TAX_DEFERRED = "tax_deferred"  # Traditional IRA, 401k
    TAX_FREE = "tax_free"  # Roth IRA, Roth 401k


class SourceType(str, Enum):
    """Data source types."""
    PLAID = "plaid"
    DOCUMENT = "document"
    MANUAL = "manual"


class TransactionType(str, Enum):
    """Transaction types."""
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


# ============================================================================
# Investment Account Schemas
# ============================================================================

class InvestmentAccountBase(BaseModel):
    """Base schema for investment accounts."""
    account_name: str
    account_type: str  # brokerage, IRA, 401k, etc.
    account_tax_type: AccountTaxType
    account_number: str | None = None
    institution: str | None = None
    total_value: Decimal | None = None
    cash_balance: Decimal | None = None


class InvestmentAccountCreate(InvestmentAccountBase):
    """Schema for creating an investment account."""
    source_type: SourceType = SourceType.MANUAL
    source_id: str | None = None
    metadata: dict[str, Any] | None = None


class InvestmentAccountUpdate(BaseModel):
    """Schema for updating an investment account."""
    account_name: str | None = None
    total_value: Decimal | None = None
    cash_balance: Decimal | None = None
    metadata: dict[str, Any] | None = None


class InvestmentAccount(InvestmentAccountBase):
    """Full investment account schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    source_type: SourceType
    source_id: str | None = None
    last_synced_at: datetime | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Investment Holding Schemas
# ============================================================================

class InvestmentHoldingBase(BaseModel):
    """Base schema for investment holdings."""
    symbol: str = Field(..., max_length=20)
    description: str | None = None
    quantity: Decimal
    cost_basis: Decimal
    average_cost_basis: Decimal | None = None


class InvestmentHoldingCreate(InvestmentHoldingBase):
    """Schema for creating an investment holding (minimal user input)."""
    account_id: UUID


class InvestmentHoldingEnriched(InvestmentHoldingBase):
    """Enriched holding data from Yahoo Finance or LLM."""
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    previous_close: Decimal | None = None
    day_change: Decimal | None = None
    day_change_pct: Decimal | None = None
    unrealized_gain_loss: Decimal | None = None
    unrealized_gain_loss_pct: Decimal | None = None
    
    asset_type: AssetType | None = None
    sector: str | None = None
    industry: str | None = None
    geographic_region: str | None = None
    
    price_as_of_timestamp: datetime | None = None
    extraction_confidence: Decimal | None = Field(None, ge=0, le=1)


class InvestmentHolding(InvestmentHoldingEnriched):
    """Full investment holding schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    account_id: UUID
    acquisition_date: date | None = None
    holding_period_days: int | None = None
    is_long_term: bool = False
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Transaction Schemas
# ============================================================================

class InvestmentTransactionBase(BaseModel):
    """Base schema for investment transactions."""
    symbol: str = Field(..., max_length=20)
    transaction_type: TransactionType
    transaction_date: date
    quantity: Decimal
    price: Decimal
    amount: Decimal
    fees: Decimal | None = None
    description: str | None = None


class InvestmentTransactionCreate(InvestmentTransactionBase):
    """Schema for creating a transaction."""
    account_id: UUID
    metadata: dict[str, Any] | None = None


class InvestmentTransaction(InvestmentTransactionBase):
    """Full transaction schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    account_id: UUID
    metadata: dict[str, Any] | None = None
    created_at: datetime


# ============================================================================
# Portfolio Allocation Schemas
# ============================================================================

class PortfolioAllocationTargets(BaseModel):
    """User's target portfolio allocation."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    target_stocks_pct: Decimal = Decimal("60.0")
    target_bonds_pct: Decimal = Decimal("30.0")
    target_cash_pct: Decimal = Decimal("10.0")
    target_international_pct: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class PortfolioAllocationTargetsUpdate(BaseModel):
    """Schema for updating allocation targets."""
    target_stocks_pct: Decimal | None = None
    target_bonds_pct: Decimal | None = None
    target_cash_pct: Decimal | None = None
    target_international_pct: Decimal | None = None


# ============================================================================
# CSV Import Schemas
# ============================================================================

class FidelityHoldingCSVRow(BaseModel):
    """Schema for parsing Fidelity CSV row."""
    account_number: str = Field(..., alias="Account Number")
    account_name: str = Field(..., alias="Account Name")
    symbol: str = Field(..., alias="Symbol")
    description: str = Field(..., alias="Description")
    quantity: Decimal = Field(..., alias="Quantity")
    last_price: Decimal = Field(..., alias="Last Price")
    last_price_change: Decimal = Field(..., alias="Last Price Change")
    current_value: Decimal = Field(..., alias="Current Value")
    todays_gain_loss_dollar: Decimal = Field(..., alias="Today's Gain/Loss Dollar")
    todays_gain_loss_percent: Decimal = Field(..., alias="Today's Gain/Loss Percent")
    total_gain_loss_dollar: Decimal = Field(..., alias="Total Gain/Loss Dollar")
    total_gain_loss_percent: Decimal = Field(..., alias="Total Gain/Loss Percent")
    percent_of_account: Decimal = Field(..., alias="Percent Of Account")
    cost_basis_total: Decimal = Field(..., alias="Cost Basis Total")
    average_cost_basis: Decimal = Field(..., alias="Average Cost Basis")
    type_field: str = Field(..., alias="Type")
    
    model_config = ConfigDict(populate_by_name=True)


class BulkHoldingsUpload(BaseModel):
    """Schema for bulk uploading holdings."""
    account_id: UUID | None = None
    account_name: str | None = None
    account_type: str = "brokerage"
    account_tax_type: AccountTaxType = AccountTaxType.TAXABLE
    institution: str = "Fidelity"
    holdings: list[InvestmentHoldingCreate]


# ============================================================================
# Analysis Response Schemas
# ============================================================================

class HoldingPerformance(BaseModel):
    """Performance data for a single holding."""
    symbol: str
    quantity: Decimal
    market_value: Decimal
    day_change: Decimal
    day_change_pct: Decimal
    unrealized_gain_loss: Decimal
    unrealized_gain_loss_pct: Decimal


class PortfolioPerformanceResponse(BaseModel):
    """Response schema for portfolio performance."""
    total_value: Decimal
    total_day_change: Decimal
    total_day_change_pct: Decimal
    total_unrealized_gain_loss: Decimal
    top_gainers: list[HoldingPerformance]
    top_losers: list[HoldingPerformance]
    as_of_timestamp: datetime


class AllocationBreakdown(BaseModel):
    """Allocation breakdown by category."""
    category: str
    value: Decimal
    percentage: Decimal
    target_percentage: Decimal | None = None
    variance: Decimal | None = None


class PortfolioAllocationResponse(BaseModel):
    """Response schema for portfolio allocation analysis."""
    total_value: Decimal
    by_asset_type: list[AllocationBreakdown]
    by_sector: list[AllocationBreakdown]
    rebalancing_needed: bool
    rebalancing_suggestions: list[str] | None = None


class TaxHarvestingOpportunity(BaseModel):
    """A single tax loss harvesting opportunity."""
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    current_value: Decimal
    unrealized_loss: Decimal
    holding_period_days: int
    is_long_term: bool
    potential_tax_savings: Decimal
    wash_sale_risk: bool


class TaxHarvestingResponse(BaseModel):
    """Response schema for tax harvesting opportunities."""
    opportunities: list[TaxHarvestingOpportunity]
    total_potential_loss: Decimal
    total_potential_tax_savings: Decimal
    warnings: list[str]
