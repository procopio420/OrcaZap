"""RQ job definitions."""

import logging
from typing import Any

import redis
from rq import Queue

from app.settings import settings

logger = logging.getLogger(__name__)

# Redis connection
redis_conn = redis.from_url(settings.redis_url)

# Default queue
default_queue = Queue("default", connection=redis_conn)


def enqueue_inbound_event(
    tenant_id: str,
    provider_message_id: str,
    contact_phone: str,
    message_text: str,
    raw_payload: dict[str, Any],
    channel_id: str,
) -> None:
    """Enqueue an inbound event job.

    Args:
        tenant_id: Tenant UUID as string
        provider_message_id: WhatsApp message ID
        contact_phone: Contact phone number
        message_text: Extracted text content
        raw_payload: Full webhook payload
        channel_id: Channel UUID as string
    """
    job_data = {
        "tenant_id": tenant_id,
        "provider_message_id": provider_message_id,
        "contact_phone": contact_phone,
        "message_text": message_text,
        "raw_payload": raw_payload,
        "channel_id": channel_id,
    }

    job = default_queue.enqueue(
        "app.worker.handlers.process_inbound_event",
        job_data,
        job_timeout=300,  # 5 minutes
    )

    logger.info(f"Enqueued inbound event job {job.id} for message {provider_message_id}")


