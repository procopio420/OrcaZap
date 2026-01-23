"""Database models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class UserRole(PyEnum):
    """User role enum."""

    OWNER = "owner"
    ATTENDANT = "attendant"


class ConversationState(PyEnum):
    """Conversation state enum."""

    INBOUND = "INBOUND"
    CAPTURE_MIN = "CAPTURE_MIN"
    QUOTE_READY = "QUOTE_READY"
    QUOTE_SENT = "QUOTE_SENT"
    WAITING_REPLY = "WAITING_REPLY"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    WON = "WON"
    LOST = "LOST"


class MessageDirection(PyEnum):
    """Message direction enum."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class QuoteStatus(PyEnum):
    """Quote status enum."""

    DRAFT = "draft"
    SENT = "sent"
    EXPIRED = "expired"
    WON = "won"
    LOST = "lost"


class ApprovalStatus(PyEnum):
    """Approval status enum."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Tenant(Base):
    """Tenant model."""

    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(32), unique=True, nullable=True, index=True)
    onboarding_step = Column(Integer, nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), nullable=True)  # active, canceled, past_due, trialing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)


class Channel(Base):
    """WhatsApp channel model."""

    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    waba_id = Column(String(255), nullable=False)
    phone_number_id = Column(String(255), nullable=False)
    access_token_encrypted = Column(Text, nullable=True)  # Encrypted at rest
    webhook_verify_token = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Item(Base):
    """Item (product) model."""

    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=False)  # kg, m², un, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantItem(Base):
    """Tenant-specific item pricing."""

    __tablename__ = "tenant_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    price_base = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "item_id", name="uq_tenant_items_tenant_item"),
    )


class PricingRule(Base):
    """Pricing rules for a tenant."""

    __tablename__ = "pricing_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, unique=True)
    pix_discount_pct = Column(Numeric(5, 4), nullable=False)  # e.g., 0.05 for 5%
    margin_min_pct = Column(Numeric(5, 4), nullable=False)
    approval_threshold_total = Column(Numeric(10, 2), nullable=True)
    approval_threshold_margin = Column(Numeric(5, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class VolumeDiscount(Base):
    """Volume discount rules."""

    __tablename__ = "volume_discounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=True)  # null = global
    min_quantity = Column(Numeric(10, 2), nullable=False)
    discount_pct = Column(Numeric(5, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FreightRule(Base):
    """Freight rules by bairro or CEP range."""

    __tablename__ = "freight_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    bairro = Column(String(255), nullable=True)
    cep_range_start = Column(String(10), nullable=True)
    cep_range_end = Column(String(10), nullable=True)
    base_freight = Column(Numeric(10, 2), nullable=False)
    per_kg_additional = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Contact(Base):
    """Contact (WhatsApp user) model."""

    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    phone = Column(String(20), nullable=False)  # Normalized phone number
    name = Column(String(255), nullable=True)  # From WhatsApp profile
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_contacts_tenant_phone"),)


class Conversation(Base):
    """Conversation model."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    state = Column(Enum(ConversationState), nullable=False)
    window_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_conversations_tenant_state", "tenant_id", "state"),
    )


class Message(Base):
    """Message model."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)  # Set by worker
    provider_message_id = Column(String(255), unique=True, nullable=False)  # WhatsApp message ID
    direction = Column(Enum(MessageDirection), nullable=False)
    message_type = Column(String(50), nullable=False)  # text, image, etc.
    raw_payload = Column(JSONB, nullable=False)
    text_content = Column(Text, nullable=True)  # Extracted text
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_messages_provider_id", "provider_message_id"),
        Index("idx_messages_tenant_id", "tenant_id"),
    )


class Quote(Base):
    """Quote model."""

    __tablename__ = "quotes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    status = Column(Enum(QuoteStatus), nullable=False)
    items_json = Column(JSONB, nullable=False)  # Array of {item_id, quantity, unit_price, total}
    subtotal = Column(Numeric(10, 2), nullable=False)
    freight = Column(Numeric(10, 2), nullable=False)
    discount_pct = Column(Numeric(5, 4), nullable=False)  # e.g., PIX discount
    total = Column(Numeric(10, 2), nullable=False)
    margin_pct = Column(Numeric(5, 4), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    payload_json = Column(JSONB, nullable=False)  # Full quote details
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_quotes_tenant_id", "tenant_id"),
    )


class Approval(Base):
    """Approval model."""

    __tablename__ = "approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=False)
    status = Column(Enum(ApprovalStatus), nullable=False)
    reason = Column(Text, nullable=True)  # Why approval needed
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_approvals_tenant_status", "tenant_id", "status"),
    )


class AuditLog(Base):
    """Audit log model."""

    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    entity_type = Column(String(50), nullable=False)  # quote, pricing_rule, etc.
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)  # create, update, approve, etc.
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    before_json = Column(JSONB, nullable=True)
    after_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

