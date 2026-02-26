"""Add missing database indexes for performance.

Revision ID: 007_add_missing_indexes
Revises: 006_add_template_smart_fields
Create Date: 2024-12-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_missing_indexes'
down_revision = '006_add_template_smart_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add indexes for quotes.status and quotes.tenant_id + status
    op.create_index('idx_quotes_status', 'quotes', ['status'])
    op.create_index('idx_quotes_tenant_status', 'quotes', ['tenant_id', 'status'])


def downgrade():
    op.drop_index('idx_quotes_tenant_status', table_name='quotes')
    op.drop_index('idx_quotes_status', table_name='quotes')








