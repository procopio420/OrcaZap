"""Integration tests for approval flow."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.db.base import Base, SessionLocal, engine
from app.db.models import (
    Approval,
    ApprovalStatus,
    Channel,
    Contact,
    Conversation,
    ConversationState,
    PricingRule,
    Quote,
    QuoteStatus,
    Tenant,
    User,
    UserRole,
)
from app.admin.auth import authenticate_user, create_session, get_password_hash
from app.admin.routes import approve_quote, reject_quote


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
def user(db_session, tenant):
    """Create a test admin user."""
    user = User(
        tenant_id=tenant.id,
        email="admin@test.com",
        password_hash=get_password_hash("password123"),
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()
    return user


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
def conversation(db_session, tenant, contact, channel):
    """Create a conversation in HUMAN_APPROVAL state."""
    conversation = Conversation(
        tenant_id=tenant.id,
        contact_id=contact.id,
        channel_id=channel.id,
        state=ConversationState.HUMAN_APPROVAL,
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(conversation)
    db_session.commit()
    return conversation


@pytest.fixture
def quote(db_session, tenant, conversation):
    """Create a quote requiring approval."""
    quote = Quote(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        status=QuoteStatus.DRAFT,
        items_json=[{"name": "Cimento", "quantity": 10, "total": 450.00}],
        subtotal=Decimal("450.00"),
        freight=Decimal("45.00"),
        discount_pct=Decimal("0.05"),
        total=Decimal("470.25"),
        margin_pct=Decimal("0.10"),
        valid_until=datetime.now(timezone.utc),
        payload_json={
            "payment_method": "PIX",
            "delivery_day": "Amanhã",
        },
    )
    db_session.add(quote)
    db_session.commit()
    return quote


@pytest.fixture
def approval(db_session, tenant, quote):
    """Create a pending approval."""
    approval = Approval(
        tenant_id=tenant.id,
        quote_id=quote.id,
        status=ApprovalStatus.PENDING,
        reason="Total exceeds threshold",
    )
    db_session.add(approval)
    db_session.commit()
    return approval


@patch("app.admin.routes.send_text_message")
def test_approve_quote_sends_message(mock_send, db_session, user, quote, conversation, contact, channel, approval):
    """Test that approving a quote sends the message."""
    mock_send.return_value = "wamid.approved123"

    # Mock request and dependencies
    from unittest.mock import MagicMock
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    mock_request.cookies = {"admin_session_id": create_session(user.id)}

    # Call approve function
    from unittest.mock import MagicMock
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    result = approve_quote(
        mock_request,
        str(approval.id),
        user,
        db_session,
    )

    # Verify message was sent
    assert mock_send.called
    call_args = mock_send.call_args
    assert call_args[1]["to_phone"] == contact.phone
    assert "Orçamento Gerado" in call_args[1]["message_text"]

    # Verify approval was updated
    db_session.refresh(approval)
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approved_by_user_id == user.id

    # Verify conversation state
    db_session.refresh(conversation)
    assert conversation.state == ConversationState.QUOTE_SENT

    # Verify quote status
    db_session.refresh(quote)
    assert quote.status == QuoteStatus.SENT


def test_reject_quote_updates_state(db_session, user, quote, conversation, approval):
    """Test that rejecting a quote updates state to LOST."""
    # Mock request
    from unittest.mock import MagicMock
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    mock_request.cookies = {"admin_session_id": create_session(user.id)}

    # Call reject function
    from unittest.mock import MagicMock
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    result = reject_quote(
        mock_request,
        str(approval.id),
        user,
        db_session,
    )

    # Verify approval was updated
    db_session.refresh(approval)
    assert approval.status == ApprovalStatus.REJECTED
    assert approval.approved_by_user_id == user.id

    # Verify conversation state
    db_session.refresh(conversation)
    assert conversation.state == ConversationState.LOST

    # Verify quote status
    db_session.refresh(quote)
    assert quote.status == QuoteStatus.LOST


def test_approve_quote_idempotency(db_session, user, quote, conversation, contact, channel, approval):
    """Test that approving an already-approved quote doesn't cause errors."""
    # Approve once
    approval.status = ApprovalStatus.APPROVED
    approval.approved_by_user_id = user.id
    approval.approved_at = datetime.now(timezone.utc)
    db_session.commit()

    # Try to approve again
    from unittest.mock import MagicMock
    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    result = approve_quote(
        mock_request,
        str(approval.id),
        user,
        db_session,
    )

    # Should return message saying already approved
    assert "already" in result.lower()

