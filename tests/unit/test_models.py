"""Unit tests for database models."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.base import Base, SessionLocal, engine
from app.db.models import (
    Approval,
    ApprovalStatus,
    Channel,
    Contact,
    Conversation,
    ConversationState,
    FreightRule,
    Item,
    Message,
    MessageDirection,
    PricingRule,
    Quote,
    QuoteStatus,
    Tenant,
    TenantItem,
    User,
    UserRole,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def tenant(db_session):
    """Create a test tenant."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Store")
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_tenant_creation(db_session, tenant):
    """Test tenant can be created."""
    assert tenant.id is not None
    assert tenant.name == "Test Store"
    assert tenant.created_at is not None


def test_user_creation(db_session, tenant):
    """Test user can be created."""
    user = User(
        tenant_id=tenant.id,
        email="owner@test.com",
        password_hash="hashed_password",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
    assert user.tenant_id == tenant.id
    assert user.email == "owner@test.com"
    assert user.role == UserRole.OWNER


def test_user_unique_email_per_tenant(db_session, tenant):
    """Test that users must have unique emails per tenant."""
    user1 = User(
        tenant_id=tenant.id,
        email="same@test.com",
        password_hash="hash1",
        role=UserRole.OWNER,
    )
    db_session.add(user1)
    db_session.commit()

    # Same email, different tenant should be OK (we'd need another tenant)
    # Same email, same tenant should fail
    user2 = User(
        tenant_id=tenant.id,
        email="same@test.com",
        password_hash="hash2",
        role=UserRole.ATTENDANT,
    )
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_item_creation(db_session):
    """Test item can be created."""
    item = Item(sku="CEMENT-50KG", name="Cimento 50kg", unit="saco")
    db_session.add(item)
    db_session.commit()

    assert item.id is not None
    assert item.sku == "CEMENT-50KG"
    assert item.unit == "saco"


def test_tenant_item_creation(db_session, tenant):
    """Test tenant item can be created."""
    item = Item(sku="CEMENT-50KG", name="Cimento 50kg", unit="saco")
    db_session.add(item)
    db_session.commit()

    tenant_item = TenantItem(
        tenant_id=tenant.id,
        item_id=item.id,
        price_base=45.00,
        is_active=True,
    )
    db_session.add(tenant_item)
    db_session.commit()

    assert tenant_item.id is not None
    assert tenant_item.price_base == 45.00


def test_message_provider_id_unique(db_session, tenant):
    """Test that provider_message_id must be unique."""
    # Create conversation and contact first
    contact = Contact(tenant_id=tenant.id, phone="+5511999999999")
    db_session.add(contact)
    db_session.commit()

    channel = Channel(
        tenant_id=tenant.id,
        waba_id="waba123",
        phone_number_id="phone123",
        webhook_verify_token="token123",
    )
    db_session.add(channel)
    db_session.commit()

    from datetime import datetime, timezone

    conversation = Conversation(
        tenant_id=tenant.id,
        contact_id=contact.id,
        channel_id=channel.id,
        state=ConversationState.INBOUND,
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(conversation)
    db_session.commit()

    message1 = Message(
        tenant_id=tenant.id,
        conversation_id=conversation.id,  # Can be None initially
        provider_message_id="wamid.123",
        direction=MessageDirection.INBOUND,
        message_type="text",
        raw_payload={"text": "hello"},
    )
    db_session.add(message1)
    db_session.commit()

    # Same provider_message_id should fail
    message2 = Message(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        provider_message_id="wamid.123",
        direction=MessageDirection.INBOUND,
        message_type="text",
        raw_payload={"text": "hello again"},
    )
    db_session.add(message2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_conversation_state_enum(db_session, tenant):
    """Test conversation state enum values."""
    contact = Contact(tenant_id=tenant.id, phone="+5511999999999")
    db_session.add(contact)
    db_session.commit()

    channel = Channel(
        tenant_id=tenant.id,
        waba_id="waba123",
        phone_number_id="phone123",
        webhook_verify_token="token123",
    )
    db_session.add(channel)
    db_session.commit()

    from datetime import datetime, timezone

    conversation = Conversation(
        tenant_id=tenant.id,
        contact_id=contact.id,
        channel_id=channel.id,
        state=ConversationState.CAPTURE_MIN,
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(conversation)
    db_session.commit()

    assert conversation.state == ConversationState.CAPTURE_MIN

