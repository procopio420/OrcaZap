"""add smart template fields

Revision ID: 006_add_template_smart_fields
Revises: 005_add_message_templates
Create Date: 2024-01-22 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_add_template_smart_fields"
down_revision: Union[str, None] = "005_add_message_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add smart template fields
    op.add_column("message_templates", sa.Column("quote_type", sa.String(50), nullable=True))
    op.add_column("message_templates", sa.Column("signature", sa.Text(), nullable=True))


def downgrade() -> None:
    # Drop smart template fields
    op.drop_column("message_templates", "signature")
    op.drop_column("message_templates", "quote_type")


