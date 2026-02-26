"""add message templates

Revision ID: 005_add_message_templates
Revises: 004_add_stripe_fields
Create Date: 2024-01-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_add_message_templates"
down_revision: Union[str, None] = "004_add_stripe_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create message_templates table
    op.create_table(
        "message_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    
    # Create unique constraint
    op.create_unique_constraint(
        "uq_message_templates_tenant_type_name",
        "message_templates",
        ["tenant_id", "template_type", "name"],
    )
    
    # Create index
    op.create_index(
        "idx_message_templates_tenant_type",
        "message_templates",
        ["tenant_id", "template_type"],
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("idx_message_templates_tenant_type", table_name="message_templates")
    
    # Drop unique constraint
    op.drop_constraint("uq_message_templates_tenant_type_name", "message_templates", type_="unique")
    
    # Drop table
    op.drop_table("message_templates")








