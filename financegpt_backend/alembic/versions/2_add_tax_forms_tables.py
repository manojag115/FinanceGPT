"""add_tax_forms_tables

Revision ID: 2
Revises: 1
Create Date: 2026-01-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2'
down_revision: Union[str, None] = '1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tax form tables."""
    
    # Base tax forms table
    op.create_table(
        'tax_forms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('search_space_id', sa.Integer, sa.ForeignKey('searchspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('form_type', sa.String(20), nullable=False),  # W2, 1099-MISC, 1099-INT, etc.
        sa.Column('tax_year', sa.Integer, nullable=False),
        sa.Column('document_id', sa.Integer, sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('processing_status', sa.String(20), server_default='pending', nullable=False),  # pending, processing, completed, failed, needs_review
        sa.Column('extraction_method', sa.String(50), nullable=True),  # structured_pdf, unstructured, ocr, llm_assisted
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True),  # 0.00 to 1.00
        sa.Column('needs_review', sa.Boolean, server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_tax_forms_user_id', 'tax_forms', ['user_id'])
    op.create_index('ix_tax_forms_tax_year', 'tax_forms', ['tax_year'])
    op.create_index('ix_tax_forms_form_type', 'tax_forms', ['form_type'])
    op.create_index('ix_tax_forms_search_space_id', 'tax_forms', ['search_space_id'])
    
    # W2 forms table
    op.create_table(
        'w2_forms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tax_form_id', UUID(as_uuid=True), sa.ForeignKey('tax_forms.id', ondelete='CASCADE'), nullable=False, unique=True),
        
        # Employer Information (masked for privacy)
        sa.Column('employer_name', sa.String(255), nullable=True),
        sa.Column('employer_ein_hash', sa.String(64), nullable=True),  # SHA256 hashed
        sa.Column('employer_address', sa.Text, nullable=True),
        
        # Employee Information (masked)
        sa.Column('employee_ssn_hash', sa.String(64), nullable=True),  # SHA256 hashed, never plain text
        sa.Column('employee_name_masked', sa.String(255), nullable=True),  # [EMPLOYEE_NAME] for UI
        
        # Wage Information - Box 1-9
        sa.Column('wages_tips_compensation', sa.Numeric(12, 2), nullable=True),  # Box 1
        sa.Column('federal_income_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 2
        sa.Column('social_security_wages', sa.Numeric(12, 2), nullable=True),  # Box 3
        sa.Column('social_security_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 4
        sa.Column('medicare_wages', sa.Numeric(12, 2), nullable=True),  # Box 5
        sa.Column('medicare_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 6
        sa.Column('social_security_tips', sa.Numeric(12, 2), nullable=True),  # Box 7
        sa.Column('allocated_tips', sa.Numeric(12, 2), nullable=True),  # Box 8
        
        # Other Compensation - Box 10-11
        sa.Column('dependent_care_benefits', sa.Numeric(12, 2), nullable=True),  # Box 10
        sa.Column('nonqualified_plans', sa.Numeric(12, 2), nullable=True),  # Box 11
        
        # Box 12 codes (multiple entries)
        sa.Column('box_12_codes', JSONB, nullable=True),  # [{code: 'D', amount: 5000.00}, ...]
        
        # Box 13 checkboxes
        sa.Column('statutory_employee', sa.Boolean, server_default='false', nullable=False),
        sa.Column('retirement_plan', sa.Boolean, server_default='false', nullable=False),
        sa.Column('third_party_sick_pay', sa.Boolean, server_default='false', nullable=False),
        
        # State/Local Tax - Box 15-20
        sa.Column('state_code', sa.String(2), nullable=True),  # Box 15
        sa.Column('state_wages', sa.Numeric(12, 2), nullable=True),  # Box 16
        sa.Column('state_income_tax', sa.Numeric(12, 2), nullable=True),  # Box 17
        sa.Column('local_wages', sa.Numeric(12, 2), nullable=True),  # Box 18
        sa.Column('local_income_tax', sa.Numeric(12, 2), nullable=True),  # Box 19
        sa.Column('locality_name', sa.String(100), nullable=True),  # Box 20
        
        # Field-level confidence scores
        sa.Column('field_confidence_scores', JSONB, nullable=True),  # {wages: 0.95, federal_tax: 0.88, ...}
        
        # Raw OCR/extraction data (for debugging/re-processing)
        sa.Column('raw_extraction_data', JSONB, nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_w2_forms_tax_form_id', 'w2_forms', ['tax_form_id'])
    
    # 1099-MISC forms table
    op.create_table(
        'form_1099_misc',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tax_form_id', UUID(as_uuid=True), sa.ForeignKey('tax_forms.id', ondelete='CASCADE'), nullable=False, unique=True),
        
        # Payer Information
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('payer_tin_hash', sa.String(64), nullable=True),
        sa.Column('payer_address', sa.Text, nullable=True),
        
        # Recipient (masked)
        sa.Column('recipient_tin_hash', sa.String(64), nullable=True),
        
        # Income Boxes
        sa.Column('rents', sa.Numeric(12, 2), nullable=True),  # Box 1
        sa.Column('royalties', sa.Numeric(12, 2), nullable=True),  # Box 2
        sa.Column('other_income', sa.Numeric(12, 2), nullable=True),  # Box 3
        sa.Column('federal_income_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 4
        sa.Column('fishing_boat_proceeds', sa.Numeric(12, 2), nullable=True),  # Box 5
        sa.Column('medical_health_payments', sa.Numeric(12, 2), nullable=True),  # Box 6
        sa.Column('substitute_payments', sa.Numeric(12, 2), nullable=True),  # Box 8
        sa.Column('crop_insurance_proceeds', sa.Numeric(12, 2), nullable=True),  # Box 10
        sa.Column('gross_proceeds_attorney', sa.Numeric(12, 2), nullable=True),  # Box 14
        sa.Column('section_409a_deferrals', sa.Numeric(12, 2), nullable=True),  # Box 15
        sa.Column('state_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 16
        sa.Column('state_payer_number', sa.String(50), nullable=True),
        sa.Column('state_income', sa.Numeric(12, 2), nullable=True),  # Box 18
        
        # Field confidence scores
        sa.Column('field_confidence_scores', JSONB, nullable=True),
        sa.Column('raw_extraction_data', JSONB, nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_1099_misc_tax_form_id', 'form_1099_misc', ['tax_form_id'])
    
    # 1099-INT (Interest Income) forms table
    op.create_table(
        'form_1099_int',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tax_form_id', UUID(as_uuid=True), sa.ForeignKey('tax_forms.id', ondelete='CASCADE'), nullable=False, unique=True),
        
        # Payer Information
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('payer_tin_hash', sa.String(64), nullable=True),
        
        # Interest Income
        sa.Column('interest_income', sa.Numeric(12, 2), nullable=True),  # Box 1
        sa.Column('early_withdrawal_penalty', sa.Numeric(12, 2), nullable=True),  # Box 2
        sa.Column('interest_us_savings_bonds', sa.Numeric(12, 2), nullable=True),  # Box 3
        sa.Column('federal_income_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 4
        sa.Column('investment_expenses', sa.Numeric(12, 2), nullable=True),  # Box 5
        sa.Column('foreign_tax_paid', sa.Numeric(12, 2), nullable=True),  # Box 6
        sa.Column('foreign_country', sa.String(100), nullable=True),  # Box 7
        sa.Column('tax_exempt_interest', sa.Numeric(12, 2), nullable=True),  # Box 8
        sa.Column('specified_private_activity_bond_interest', sa.Numeric(12, 2), nullable=True),  # Box 9
        sa.Column('market_discount', sa.Numeric(12, 2), nullable=True),  # Box 10
        sa.Column('bond_premium', sa.Numeric(12, 2), nullable=True),  # Box 11
        sa.Column('bond_premium_treasury', sa.Numeric(12, 2), nullable=True),  # Box 12
        sa.Column('tax_exempt_bond_premium', sa.Numeric(12, 2), nullable=True),  # Box 13
        
        sa.Column('field_confidence_scores', JSONB, nullable=True),
        sa.Column('raw_extraction_data', JSONB, nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_1099_int_tax_form_id', 'form_1099_int', ['tax_form_id'])
    
    # 1099-DIV (Dividends) forms table
    op.create_table(
        'form_1099_div',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tax_form_id', UUID(as_uuid=True), sa.ForeignKey('tax_forms.id', ondelete='CASCADE'), nullable=False, unique=True),
        
        # Payer Information
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('payer_tin_hash', sa.String(64), nullable=True),
        
        # Dividend Income
        sa.Column('total_ordinary_dividends', sa.Numeric(12, 2), nullable=True),  # Box 1a
        sa.Column('qualified_dividends', sa.Numeric(12, 2), nullable=True),  # Box 1b
        sa.Column('total_capital_gain_distributions', sa.Numeric(12, 2), nullable=True),  # Box 2a
        sa.Column('unrecaptured_section_1250_gain', sa.Numeric(12, 2), nullable=True),  # Box 2b
        sa.Column('section_1202_gain', sa.Numeric(12, 2), nullable=True),  # Box 2c
        sa.Column('collectibles_gain', sa.Numeric(12, 2), nullable=True),  # Box 2d
        sa.Column('nondividend_distributions', sa.Numeric(12, 2), nullable=True),  # Box 3
        sa.Column('federal_income_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 4
        sa.Column('section_199a_dividends', sa.Numeric(12, 2), nullable=True),  # Box 5
        sa.Column('investment_expenses', sa.Numeric(12, 2), nullable=True),  # Box 6
        sa.Column('foreign_tax_paid', sa.Numeric(12, 2), nullable=True),  # Box 7
        sa.Column('foreign_country', sa.String(100), nullable=True),  # Box 8
        sa.Column('cash_liquidation_distributions', sa.Numeric(12, 2), nullable=True),  # Box 9
        sa.Column('noncash_liquidation_distributions', sa.Numeric(12, 2), nullable=True),  # Box 10
        
        sa.Column('field_confidence_scores', JSONB, nullable=True),
        sa.Column('raw_extraction_data', JSONB, nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_1099_div_tax_form_id', 'form_1099_div', ['tax_form_id'])
    
    # 1099-B (Brokerage Transactions) forms table
    op.create_table(
        'form_1099_b',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tax_form_id', UUID(as_uuid=True), sa.ForeignKey('tax_forms.id', ondelete='CASCADE'), nullable=False, unique=True),
        
        # Payer Information
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('payer_tin_hash', sa.String(64), nullable=True),
        
        # Transaction Details
        sa.Column('description_of_property', sa.Text, nullable=True),  # Box 1a (stock name, quantity)
        sa.Column('date_acquired', sa.Date, nullable=True),  # Box 1b
        sa.Column('date_sold', sa.Date, nullable=True),  # Box 1c
        sa.Column('proceeds', sa.Numeric(12, 2), nullable=True),  # Box 1d
        sa.Column('cost_basis', sa.Numeric(12, 2), nullable=True),  # Box 1e
        sa.Column('adjustments_to_basis', sa.Numeric(12, 2), nullable=True),  # Box 1f
        sa.Column('realized_gain_loss', sa.Numeric(12, 2), nullable=True),  # Box 1g (calculated)
        
        sa.Column('federal_income_tax_withheld', sa.Numeric(12, 2), nullable=True),  # Box 4
        
        # Form Characteristics
        sa.Column('short_term', sa.Boolean, nullable=True),  # Box 2
        sa.Column('long_term', sa.Boolean, nullable=True),
        sa.Column('basis_reported_to_irs', sa.Boolean, nullable=True),  # Box 3
        sa.Column('noncovered_security', sa.Boolean, nullable=True),  # Box 5
        
        sa.Column('field_confidence_scores', JSONB, nullable=True),
        sa.Column('raw_extraction_data', JSONB, nullable=True),
        
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_1099_b_tax_form_id', 'form_1099_b', ['tax_form_id'])


def downgrade() -> None:
    """Drop tax form tables."""
    op.drop_table('form_1099_b')
    op.drop_table('form_1099_div')
    op.drop_table('form_1099_int')
    op.drop_table('form_1099_misc')
    op.drop_table('w2_forms')
    op.drop_table('tax_forms')
