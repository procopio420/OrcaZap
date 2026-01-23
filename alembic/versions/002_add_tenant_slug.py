"""add tenant slug

Revision ID: 002_add_tenant_slug
Revises: 001_initial
Create Date: 2024-01-20 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_tenant_slug"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add slug column to tenants table
    op.add_column("tenants", sa.Column("slug", sa.String(32), nullable=True))
    
    # Create unique index on slug
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)


def downgrade() -> None:
    # Drop index and column
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_column("tenants", "slug")


