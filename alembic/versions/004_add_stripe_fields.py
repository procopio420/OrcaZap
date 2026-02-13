"""add stripe fields

Revision ID: 004_add_stripe_fields
Revises: 003_add_onboarding_fields
Create Date: 2024-01-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_add_stripe_fields"
down_revision: Union[str, None] = "003_add_onboarding_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Stripe fields to tenants table
    op.add_column("tenants", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("subscription_status", sa.String(50), nullable=True))


def downgrade() -> None:
    # Drop Stripe fields
    op.drop_column("tenants", "subscription_status")
    op.drop_column("tenants", "stripe_subscription_id")
    op.drop_column("tenants", "stripe_customer_id")








