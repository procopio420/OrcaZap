"""Integration tests for worker idempotency."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.db.base import Base, SessionLocal, engine
from app.db.models import (
    Channel,
    Contact,
    Conversation,
    ConversationState,
    Message,
    MessageDirection,
    Tenant,
)
from app.worker.handlers import process_inbound_event


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


@pytest.fixture
def channel(db_session, tenant):
    """Create a test channel."""
    channel = Channel(
        tenant_id=tenant.id,
        waba_id="waba123",
        phone_number_id="phone123",
        webhook_verify_token="token123",
        is_active=True,
    )
    db_session.add(channel)
    db_session.commit()
    return channel


@pytest.fixture
def contact(db_session, tenant):
    """Create a test contact."""
    contact = Contact(tenant_id=tenant.id, phone="+5511999999999")
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def message(db_session, tenant, contact, channel):
    """Create a test message (as if from webhook)."""
    message = Message(
        tenant_id=tenant.id,
        conversation_id=None,  # Not set yet
        provider_message_id="wamid.test123",
        direction=MessageDirection.INBOUND,
        message_type="text",
        raw_payload={"text": {"body": "Hello"}},
        text_content="Hello",
    )
    db_session.add(message)
    db_session.commit()
    return message


@patch("app.adapters.whatsapp.sender.send_text_message")
def test_worker_processes_first_message(mock_send, db_session, tenant, channel, message):
    """Test worker processes first message and sends prompt."""
    mock_send.return_value = "wamid.outbound123"

    job_data = {
        "tenant_id": str(tenant.id),
        "provider_message_id": "wamid.test123",
        "contact_phone": "+5511999999999",
        "message_text": "Hello",
        "raw_payload": {"text": {"body": "Hello"}},
        "channel_id": str(channel.id),
    }

    process_inbound_event(job_data)

    # Verify contact was created
    contact = db_session.query(Contact).filter_by(tenant_id=tenant.id).first()
    assert contact is not None
    assert contact.phone == "+5511999999999"

    # Verify conversation was created
    conversation = db_session.query(Conversation).filter_by(tenant_id=tenant.id).first()
    assert conversation is not None
    assert conversation.state == ConversationState.CAPTURE_MIN
    assert conversation.contact_id == contact.id
    assert conversation.channel_id == channel.id

    # Verify message was linked to conversation
    db_session.refresh(message)
    assert message.conversation_id == conversation.id

    # Verify prompt was sent
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[1]["to_phone"] == "+5511999999999"
    assert "Para gerar seu orçamento" in call_args[1]["message_text"]

    # Verify outbound message was saved
    outbound = (
        db_session.query(Message)
        .filter_by(
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND,
        )
        .first()
    )
    assert outbound is not None
    assert outbound.provider_message_id == "wamid.outbound123"


@patch("app.adapters.whatsapp.sender.send_text_message")
def test_worker_idempotency_same_message_id(mock_send, db_session, tenant, channel, message):
    """Test worker is idempotent - same message ID processed only once."""
    mock_send.return_value = "wamid.outbound123"

    job_data = {
        "tenant_id": str(tenant.id),
        "provider_message_id": "wamid.test123",
        "contact_phone": "+5511999999999",
        "message_text": "Hello",
        "raw_payload": {"text": {"body": "Hello"}},
        "channel_id": str(channel.id),
    }

    # Process first time
    process_inbound_event(job_data)
    first_call_count = mock_send.call_count

    # Process second time with same message ID
    process_inbound_event(job_data)

    # Should not send message again (idempotent)
    assert mock_send.call_count == first_call_count

    # Verify only one conversation exists
    conversations = db_session.query(Conversation).filter_by(tenant_id=tenant.id).all()
    assert len(conversations) == 1


@patch("app.adapters.whatsapp.sender.send_text_message")
def test_worker_idempotency_message_already_has_conversation(
    mock_send, db_session, tenant, channel, contact, message
):
    """Test worker skips if message already has conversation_id."""
    # Create conversation and link message
    conversation = Conversation(
        tenant_id=tenant.id,
        contact_id=contact.id,
        channel_id=channel.id,
        state=ConversationState.CAPTURE_MIN,
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(conversation)
    db_session.commit()

    message.conversation_id = conversation.id
    db_session.commit()

    job_data = {
        "tenant_id": str(tenant.id),
        "provider_message_id": "wamid.test123",
        "contact_phone": "+5511999999999",
        "message_text": "Hello",
        "raw_payload": {"text": {"body": "Hello"}},
        "channel_id": str(channel.id),
    }

    # Process - should skip
    process_inbound_event(job_data)

    # Should not send message (already processed)
    mock_send.assert_not_called()

