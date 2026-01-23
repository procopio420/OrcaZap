"""initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if migration already applied (tenants table exists)
    connection = op.get_bind()
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'tenants'"
    )).fetchone()
    if result:
        # Migration already applied, skip
        return
    
    # Create enum types (idempotent - check if exists first)
    # Check and create userrole enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'userrole'"
    )).fetchone()
    if not result:
        op.execute("CREATE TYPE userrole AS ENUM ('owner', 'attendant')")
    
    # Check and create conversationstate enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'conversationstate'"
    )).fetchone()
    if not result:
        op.execute(
            "CREATE TYPE conversationstate AS ENUM "
            "('INBOUND', 'CAPTURE_MIN', 'QUOTE_READY', 'QUOTE_SENT', "
            "'WAITING_REPLY', 'HUMAN_APPROVAL', 'WON', 'LOST')"
        )
    
    # Check and create messagedirection enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'messagedirection'"
    )).fetchone()
    if not result:
        op.execute("CREATE TYPE messagedirection AS ENUM ('inbound', 'outbound')")
    
    # Check and create quotestatus enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'quotestatus'"
    )).fetchone()
    if not result:
        op.execute("CREATE TYPE quotestatus AS ENUM ('draft', 'sent', 'expired', 'won', 'lost')")
    
    # Check and create approvalstatus enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'approvalstatus'"
    )).fetchone()
    if not result:
        op.execute("CREATE TYPE approvalstatus AS ENUM ('pending', 'approved', 'rejected')")
    
    # Tenants
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("owner", "attendant", name="userrole"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # Channels
    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("waba_id", sa.String(255), nullable=False),
        sa.Column("phone_number_id", sa.String(255), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_verify_token", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Items
    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sku", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Tenant Items
    op.create_table(
        "tenant_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("price_base", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "item_id", name="uq_tenant_items_tenant_item"),
    )

    # Pricing Rules
    op.create_table(
        "pricing_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("pix_discount_pct", sa.Numeric(5, 4), nullable=False),
        sa.Column("margin_min_pct", sa.Numeric(5, 4), nullable=False),
        sa.Column("approval_threshold_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("approval_threshold_margin", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Volume Discounts
    op.create_table(
        "volume_discounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=True),
        sa.Column("min_quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Freight Rules
    op.create_table(
        "freight_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bairro", sa.String(255), nullable=True),
        sa.Column("cep_range_start", sa.String(10), nullable=True),
        sa.Column("cep_range_end", sa.String(10), nullable=True),
        sa.Column("base_freight", sa.Numeric(10, 2), nullable=False),
        sa.Column("per_kg_additional", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Contacts
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_contacts_tenant_phone"),
    )

    # Conversations
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channels.id"), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "INBOUND",
                "CAPTURE_MIN",
                "QUOTE_READY",
                "QUOTE_SENT",
                "WAITING_REPLY",
                "HUMAN_APPROVAL",
                "WON",
                "LOST",
                name="conversationstate",
            ),
            nullable=False,
        ),
        sa.Column("window_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_conversations_tenant_state", "conversations", ["tenant_id", "state"])

    # Messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("provider_message_id", sa.String(255), unique=True, nullable=False),
        sa.Column("direction", sa.Enum("inbound", "outbound", name="messagedirection"), nullable=False),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_messages_provider_id", "messages", ["provider_message_id"])
    op.create_index("idx_messages_tenant_id", "messages", ["tenant_id"])

    # Quotes
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("status", sa.Enum("draft", "sent", "expired", "won", "lost", name="quotestatus"), nullable=False),
        sa.Column("items_json", postgresql.JSONB(), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("freight", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 4), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("margin_pct", sa.Numeric(5, 4), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_quotes_tenant_id", "quotes", ["tenant_id"])

    # Approvals
    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("quote_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", name="approvalstatus"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_approvals_tenant_status", "approvals", ["tenant_id", "status"])

    # Audit Log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("before_json", postgresql.JSONB(), nullable=True),
        sa.Column("after_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("approvals")
    op.drop_table("quotes")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("contacts")
    op.drop_table("freight_rules")
    op.drop_table("volume_discounts")
    op.drop_table("pricing_rules")
    op.drop_table("tenant_items")
    op.drop_table("items")
    op.drop_table("channels")
    op.drop_table("users")
    op.drop_table("tenants")

    op.execute("DROP TYPE approvalstatus")
    op.execute("DROP TYPE quotestatus")
    op.execute("DROP TYPE messagedirection")
    op.execute("DROP TYPE conversationstate")
    op.execute("DROP TYPE userrole")

