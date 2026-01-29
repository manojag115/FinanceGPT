"""add_investment_holdings_tables

Revision ID: 1
Revises: 0
Create Date: 2026-01-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1'
down_revision: Union[str, None] = '0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create investment-related tables."""
    
    # Investment accounts table
    op.create_table(
        'investment_accounts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_number', sa.String(255), nullable=True),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('account_type', sa.String(100), nullable=False),  # brokerage, IRA, 401k, etc.
        sa.Column('account_tax_type', sa.String(50), nullable=False),  # taxable, tax_deferred, tax_free
        sa.Column('institution', sa.String(255), nullable=True),  # Fidelity, Vanguard, etc.
        sa.Column('total_value', sa.Numeric(20, 2), nullable=True),
        sa.Column('cash_balance', sa.Numeric(20, 2), nullable=True),
        sa.Column('last_synced_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),  # plaid, document, manual
        sa.Column('source_id', sa.String(255), nullable=True),  # plaid account_id or document_id
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_investment_accounts_user_id', 'investment_accounts', ['user_id'])
    op.create_index('ix_investment_accounts_account_number', 'investment_accounts', ['account_number'])
    
    # Investment holdings table
    op.create_table(
        'investment_holdings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('investment_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        
        # Quantities and values
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('cost_basis', sa.Numeric(20, 2), nullable=False),
        sa.Column('average_cost_basis', sa.Numeric(20, 2), nullable=True),
        sa.Column('current_price', sa.Numeric(20, 2), nullable=True),
        sa.Column('market_value', sa.Numeric(20, 2), nullable=True),
        
        # Performance metrics
        sa.Column('unrealized_gain_loss', sa.Numeric(20, 2), nullable=True),
        sa.Column('unrealized_gain_loss_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('day_change', sa.Numeric(20, 2), nullable=True),
        sa.Column('day_change_pct', sa.Numeric(10, 4), nullable=True),
        sa.Column('previous_close', sa.Numeric(20, 2), nullable=True),
        
        # Classification
        sa.Column('asset_type', sa.String(50), nullable=True),  # stock, bond, ETF, mutual_fund, crypto
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('geographic_region', sa.String(100), nullable=True),
        
        # Tax data
        sa.Column('acquisition_date', sa.Date, nullable=True),
        sa.Column('holding_period_days', sa.Integer, nullable=True),
        sa.Column('is_long_term', sa.Boolean, default=False, nullable=False),
        
        # Metadata
        sa.Column('price_as_of_timestamp', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('extraction_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_investment_holdings_account_id', 'investment_holdings', ['account_id'])
    op.create_index('ix_investment_holdings_symbol', 'investment_holdings', ['symbol'])
    op.create_index('ix_investment_holdings_asset_type', 'investment_holdings', ['asset_type'])
    
    # Transactions table for wash sale detection and history
    op.create_table(
        'investment_transactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('investment_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('transaction_type', sa.String(50), nullable=False),  # buy, sell, dividend, etc.
        sa.Column('transaction_date', sa.Date, nullable=False),
        sa.Column('quantity', sa.Numeric(20, 8), nullable=False),
        sa.Column('price', sa.Numeric(20, 2), nullable=False),
        sa.Column('amount', sa.Numeric(20, 2), nullable=False),
        sa.Column('fees', sa.Numeric(20, 2), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_investment_transactions_account_id', 'investment_transactions', ['account_id'])
    op.create_index('ix_investment_transactions_symbol', 'investment_transactions', ['symbol'])
    op.create_index('ix_investment_transactions_date', 'investment_transactions', ['transaction_date'])
    
    # Portfolio allocation targets table
    op.create_table(
        'portfolio_allocation_targets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_stocks_pct', sa.Numeric(5, 2), default=60.0, nullable=False),
        sa.Column('target_bonds_pct', sa.Numeric(5, 2), default=30.0, nullable=False),
        sa.Column('target_cash_pct', sa.Numeric(5, 2), default=10.0, nullable=False),
        sa.Column('target_international_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_portfolio_allocation_targets_user_id', 'portfolio_allocation_targets', ['user_id'])
    
    # Set REPLICA IDENTITY FULL on new tables for Electric SQL
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN 
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('investment_accounts', 'investment_holdings', 'investment_transactions', 'portfolio_allocation_targets')
            LOOP
                EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' REPLICA IDENTITY FULL';
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    """Drop investment-related tables."""
    op.drop_table('portfolio_allocation_targets')
    op.drop_table('investment_transactions')
    op.drop_table('investment_holdings')
    op.drop_table('investment_accounts')
