"""Integration test for quote generation flow."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.db.base import Base, SessionLocal, engine
from app.db.models import (
    Channel,
    Contact,
    Conversation,
    ConversationState,
    FreightRule,
    Item,
    Message,
    MessageDirection,
    PricingRule,
    QuoteStatus,
    Tenant,
    TenantItem,
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
def pricing_rules(db_session, tenant):
    """Create pricing rules."""
    rules = PricingRule(
        tenant_id=tenant.id,
        pix_discount_pct=Decimal("0.05"),
        margin_min_pct=Decimal("0.10"),
        approval_threshold_total=Decimal("10000.00"),
        approval_threshold_margin=Decimal("0.05"),
    )
    db_session.add(rules)
    db_session.commit()
    return rules


@pytest.fixture
def freight_rule(db_session, tenant):
    """Create freight rule."""
    rule = FreightRule(
        tenant_id=tenant.id,
        bairro="Centro",
        base_freight=Decimal("45.00"),
    )
    db_session.add(rule)
    db_session.commit()
    return rule


@pytest.fixture
def item(db_session):
    """Create a test item."""
    item = Item(sku="CEMENT-50KG", name="Cimento 50kg", unit="saco")
    db_session.add(item)
    db_session.commit()
    return item


@pytest.fixture
def tenant_item(db_session, tenant, item):
    """Create tenant item."""
    tenant_item = TenantItem(
        tenant_id=tenant.id,
        item_id=item.id,
        price_base=Decimal("45.00"),
        is_active=True,
    )
    db_session.add(tenant_item)
    db_session.commit()
    return tenant_item


@pytest.fixture
def conversation(db_session, tenant, channel):
    """Create a conversation in CAPTURE_MIN state."""
    contact = Contact(tenant_id=tenant.id, phone="+5511999999999")
    db_session.add(contact)
    db_session.commit()

    conversation = Conversation(
        tenant_id=tenant.id,
        contact_id=contact.id,
        channel_id=channel.id,
        state=ConversationState.CAPTURE_MIN,
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(conversation)
    db_session.commit()
    return conversation


@patch("app.adapters.whatsapp.sender.send_text_message")
def test_quote_generation_flow(
    mock_send,
    db_session,
    tenant,
    channel,
    pricing_rules,
    freight_rule,
    item,
    tenant_item,
    conversation,
):
    """Test full flow: data capture message -> quote generation -> quote sent."""
    mock_send.return_value = "wamid.quote123"

    # Create inbound message with data capture response
    message = Message(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        provider_message_id="wamid.data123",
        direction=MessageDirection.INBOUND,
        message_type="text",
        raw_payload={"text": {"body": "test"}},
        text_content=(
            "📍 CEP: 01310-100\n"
            "💳 PIX\n"
            "📅 Amanhã\n"
            "📦\n"
            "- Cimento 50kg: 10 sacos"
        ),
    )
    db_session.add(message)
    db_session.commit()

    job_data = {
        "tenant_id": str(tenant.id),
        "provider_message_id": "wamid.data123",
        "contact_phone": "+5511999999999",
        "message_text": message.text_content,
        "raw_payload": message.raw_payload,
        "channel_id": str(channel.id),
    }

    # Process event
    process_inbound_event(job_data)

    # Verify quote was created
    from app.db.models import Quote

    quote = db_session.query(Quote).filter_by(conversation_id=conversation.id).first()
    assert quote is not None
    assert quote.status == QuoteStatus.SENT
    assert float(quote.subtotal) > 0
    assert float(quote.freight) > 0
    assert float(quote.total) > 0

    # Verify quote message was sent
    assert mock_send.called
    call_args = mock_send.call_args
    assert "Orçamento Gerado" in call_args[1]["message_text"]
    assert "Cimento 50kg" in call_args[1]["message_text"]

    # Verify conversation state updated
    db_session.refresh(conversation)
    assert conversation.state == ConversationState.QUOTE_SENT


