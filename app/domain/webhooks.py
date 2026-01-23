"""Webhook idempotency and signature verification utilities."""

import hashlib
import hmac
from typing import Optional

import redis

from app.settings import settings

# Redis client for idempotency
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# Idempotency key prefix
IDEMPOTENCY_PREFIX = "webhook:"


def check_idempotency(provider: str, event_id: str) -> bool:
    """Check if webhook event has already been processed.

    Args:
        provider: Provider name (e.g., "whatsapp", "stripe")
        event_id: Provider event ID

    Returns:
        True if already processed, False otherwise
    """
    key = f"{IDEMPOTENCY_PREFIX}{provider}:{event_id}"
    return redis_client.exists(key) > 0


def mark_processed(provider: str, event_id: str, ttl: int = 86400 * 7) -> None:
    """Mark webhook event as processed.

    Args:
        provider: Provider name
        event_id: Provider event ID
        ttl: Time to live in seconds (default 7 days)
    """
    key = f"{IDEMPOTENCY_PREFIX}{provider}:{event_id}"
    redis_client.setex(key, ttl, "processed")


def verify_stripe_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Stripe webhook signature.

    Args:
        payload: Raw request body
        signature: Stripe signature header
        secret: Stripe webhook secret

    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Stripe signature format: timestamp,signature
        timestamp, signature_hex = signature.split(",", 1)
        timestamp = timestamp.split("=", 1)[1]
        signature_hex = signature_hex.split("=", 1)[1]

        # Create signed payload
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature_hex)
    except (ValueError, IndexError, AttributeError):
        return False


def verify_whatsapp_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify WhatsApp webhook signature (if applicable).

    Note: WhatsApp Cloud API may use different signature verification.
    This is a placeholder implementation.

    Args:
        payload: Raw request body
        signature: WhatsApp signature header
        secret: WhatsApp app secret

    Returns:
        True if signature is valid, False otherwise
    """
    # WhatsApp signature verification implementation
    # For now, return True (implement based on WhatsApp API docs)
    return True


