"""WhatsApp message sender."""

import logging
from typing import Any
from uuid import UUID

import httpx

from app.db.models import Channel
from app.settings import settings

logger = logging.getLogger(__name__)


def send_text_message(
    channel: Channel,
    to_phone: str,
    message_text: str,
) -> str | None:
    """Send a text message via WhatsApp Cloud API.

    Args:
        channel: Channel configuration
        to_phone: Recipient phone number (E.164 format, e.g., +5511999999999)
        message_text: Message text content

    Returns:
        Provider message ID if successful, None otherwise

    Raises:
        Exception: If message sending fails
    """
    # Use access token from settings (for MVP)
    # In production, would decrypt channel.access_token_encrypted
    access_token = settings.whatsapp_access_token
    phone_number_id = channel.phone_number_id or settings.whatsapp_phone_number_id

    if not access_token:
        raise ValueError(f"No access token available for channel {channel.id}")
    
    if not phone_number_id:
        raise ValueError(f"No phone_number_id available for channel {channel.id}")

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text},
    }

    log_extra = {
        "provider_message_id": None,  # Will be set after response
        "channel_id": str(channel.id),
        "to_phone": to_phone,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            result = response.json()
            provider_message_id = result.get("messages", [{}])[0].get("id")

            if provider_message_id:
                log_extra["provider_message_id"] = provider_message_id
                logger.info(
                    f"Message sent successfully: {provider_message_id}",
                    extra=log_extra,
                )
                return provider_message_id
            else:
                logger.warning(
                    "Message sent but no provider_message_id in response",
                    extra=log_extra,
                )
                return None

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error sending message: {e.response.status_code} - {e.response.text}",
            extra=log_extra,
        )
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}", extra=log_extra, exc_info=True)
        raise

