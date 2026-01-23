"""WhatsApp webhook payload models."""

from typing import Any

from pydantic import BaseModel, Field


class WhatsAppText(BaseModel):
    """WhatsApp text message content."""

    body: str


class WhatsAppMessage(BaseModel):
    """WhatsApp message from webhook."""

    id: str = Field(alias="id")  # provider_message_id
    from_: str = Field(alias="from")
    type: str
    text: WhatsAppText | None = None
    timestamp: str


class WhatsAppValue(BaseModel):
    """WhatsApp webhook value."""

    messaging_product: str
    metadata: dict[str, Any]
    contacts: list[dict[str, Any]] | None = None
    messages: list[WhatsAppMessage] | None = None
    statuses: list[dict[str, Any]] | None = None


class WhatsAppWebhookEntry(BaseModel):
    """WhatsApp webhook entry."""

    id: str
    changes: list[dict[str, Any]]


class WhatsAppWebhookPayload(BaseModel):
    """WhatsApp webhook payload."""

    object: str
    entry: list[WhatsAppWebhookEntry]


