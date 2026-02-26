"""add onboarding fields

Revision ID: 003_add_onboarding_fields
Revises: 002_add_tenant_slug
Create Date: 2024-01-20 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_add_onboarding_fields"
down_revision: Union[str, None] = "002_add_tenant_slug"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add onboarding fields to tenants table
    op.add_column("tenants", sa.Column("onboarding_step", sa.Integer(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Drop onboarding fields
    op.drop_column("tenants", "onboarding_completed_at")
    op.drop_column("tenants", "onboarding_step")











