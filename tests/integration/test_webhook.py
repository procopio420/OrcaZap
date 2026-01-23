"""Integration tests for WhatsApp webhook."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    with patch("app.worker.jobs.redis_conn") as mock:
        yield mock


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch("app.adapters.whatsapp.webhook.SessionLocal") as mock:
        mock_session = MagicMock()
        mock.return_value = mock_session
        yield mock_session


def test_webhook_verification_success():
    """Test webhook verification (GET) succeeds with correct token."""
    from app.settings import settings

    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "test_challenge_123",
        },
    )

    assert response.status_code == 200
    assert response.text == "test_challenge_123"


def test_webhook_verification_fails_wrong_token():
    """Test webhook verification fails with wrong token."""
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test_challenge_123",
        },
    )

    assert response.status_code == 403


def test_webhook_verification_fails_wrong_mode():
    """Test webhook verification fails with wrong mode."""
    from app.settings import settings

    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "test_challenge_123",
        },
    )

    assert response.status_code == 403


@patch("app.adapters.whatsapp.webhook.enqueue_inbound_event")
@patch("app.adapters.whatsapp.webhook.SessionLocal")
def test_webhook_receives_message(mock_session_local, mock_enqueue, mock_db_session):
    """Test webhook receives and processes a text message."""
    from app.db.models import Channel, Message
    from uuid import uuid4

    # Setup mock database
    tenant_id = uuid4()
    channel_id = uuid4()

    mock_channel = MagicMock(spec=Channel)
    mock_channel.id = channel_id
    mock_channel.tenant_id = tenant_id
    mock_channel.is_active = True

    mock_db_session.query.return_value.filter_by.return_value.first.side_effect = [
        None,  # Message doesn't exist yet
        mock_channel,  # Channel found
    ]

    # Webhook payload
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": "phone123",
                            },
                            "messages": [
                                {
                                    "id": "wamid.test123",
                                    "from": "5511999999999",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                    "timestamp": "1234567890",
                                }
                            ],
                        }
                    }
                ],
            }
        ],
    }

    response = client.post("/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify message was added to DB
    assert mock_db_session.add.called
    added_message = mock_db_session.add.call_args[0][0]
    assert isinstance(added_message, Message)
    assert added_message.provider_message_id == "wamid.test123"
    assert added_message.text_content == "Hello"

    # Verify commit was called
    mock_db_session.commit.assert_called_once()

    # Verify job was enqueued
    mock_enqueue.assert_called_once()
    call_args = mock_enqueue.call_args[1]
    assert call_args["provider_message_id"] == "wamid.test123"
    assert call_args["contact_phone"] == "5511999999999"
    assert call_args["message_text"] == "Hello"


@patch("app.adapters.whatsapp.webhook.enqueue_inbound_event")
@patch("app.adapters.whatsapp.webhook.SessionLocal")
def test_webhook_idempotency(mock_session_local, mock_enqueue, mock_db_session):
    """Test webhook is idempotent (same message ID processed only once)."""
    from app.db.models import Channel, Message
    from uuid import uuid4

    tenant_id = uuid4()
    channel_id = uuid4()

    # Mock existing message (idempotency check)
    existing_message = MagicMock(spec=Message)
    existing_message.provider_message_id = "wamid.test123"

    mock_channel = MagicMock(spec=Channel)
    mock_channel.id = channel_id
    mock_channel.tenant_id = tenant_id
    mock_channel.is_active = True

    mock_db_session.query.return_value.filter_by.return_value.first.side_effect = [
        existing_message,  # Message already exists
    ]

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "phone123"},
                            "messages": [
                                {
                                    "id": "wamid.test123",
                                    "from": "5511999999999",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                    "timestamp": "1234567890",
                                }
                            ],
                        }
                    }
                ],
            }
        ],
    }

    response = client.post("/webhooks/whatsapp", json=payload)

    assert response.status_code == 200

    # Verify message was NOT added again (idempotent)
    mock_db_session.add.assert_not_called()

    # Verify job was NOT enqueued again
    mock_enqueue.assert_not_called()


