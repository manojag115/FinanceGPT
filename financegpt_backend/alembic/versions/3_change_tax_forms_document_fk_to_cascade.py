"""change_tax_forms_document_fk_to_cascade

Revision ID: 3
Revises: 2
Create Date: 2026-02-02 20:43:14.342128

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3'
down_revision: Union[str, None] = '2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change tax_forms.document_id FK from SET NULL to CASCADE."""
    # Drop the existing foreign key constraint
    op.drop_constraint('tax_forms_document_id_fkey', 'tax_forms', type_='foreignkey')
    
    # Recreate with CASCADE on delete
    op.create_foreign_key(
        'tax_forms_document_id_fkey',
        'tax_forms',
        'documents',
        ['document_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Revert to SET NULL behavior."""
    op.drop_constraint('tax_forms_document_id_fkey', 'tax_forms', type_='foreignkey')
    
    op.create_foreign_key(
        'tax_forms_document_id_fkey',
        'tax_forms',
        'documents',
        ['document_id'],
        ['id'],
        ondelete='SET NULL'
    )
