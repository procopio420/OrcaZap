"""WhatsApp webhook handler."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.adapters.whatsapp.models import WhatsAppWebhookPayload
from app.db.base import SessionLocal
from app.db.models import Message, MessageDirection
from app.middleware.rate_limit import webhook_rate_limit
from app.settings import settings
from app.worker.jobs import enqueue_inbound_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


def get_db() -> Session:
    """Get database session (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
async def verify_webhook(
    request: Request,
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
) -> Response:
    """Verify webhook with Meta (GET request).

    Meta sends a GET request to verify the webhook endpoint.
    Only accessible on API host.
    """
    # Check API host (webhooks should only be on API host)
    from app.middleware.host_routing import HostContext

    if request.state.host_context != HostContext.API:
        raise HTTPException(status_code=404, detail="Webhook only available on API host")
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.whatsapp_verify_token
        and hub_challenge is not None
    ):
        logger.info("Webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")
    else:
        logger.warning("Webhook verification failed")
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("")
@webhook_rate_limit
async def handle_webhook(
    request: Request,
    payload: WhatsAppWebhookPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Handle incoming WhatsApp webhook (POST request).

    Processes inbound messages and status updates.
    Only accessible on API host.
    Returns 200 quickly (target <200ms) after enqueueing.
    """
    # Check API host (webhooks should only be on API host)
    from app.middleware.host_routing import HostContext

    if request.state.host_context != HostContext.API:
        raise HTTPException(status_code=404, detail="Webhook only available on API host")
    logger.info(f"Received webhook: object={payload.object}, entries={len(payload.entry)}")

    try:
        for entry in payload.entry:
            # entry.changes is a list of dicts from Pydantic
            changes = entry.changes if isinstance(entry.changes, list) else []
            for change in changes:
                value = change.get("value", {}) if isinstance(change, dict) else {}

                # Process messages
                if "messages" in value and value["messages"]:
                    for msg_data in value["messages"]:
                        await _process_message(db, msg_data, value, entry)

                # Process status updates (acknowledge, but don't process)
                statuses = value.get("statuses")
                if statuses:
                    logger.debug(f"Status update received: {statuses}")

        return {"status": "ok"}

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _process_message(
    db: Session,
    msg_data: dict[str, Any],
    value: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    """Process a single message from webhook.

    Implements idempotency: checks if message already processed.
    Includes structured logging with provider_message_id (R5).
    """
    provider_message_id = msg_data.get("id")
    if not provider_message_id:
        logger.warning("Message missing id, skipping", extra={"provider_message_id": None})
        return

    # Structured logging with provider_message_id (R5)
    log_extra = {"provider_message_id": provider_message_id}

    # Idempotency check: if message already exists, skip
    existing = db.query(Message).filter_by(provider_message_id=provider_message_id).first()
    if existing:
        logger.info(
            f"Message {provider_message_id} already processed, skipping (idempotent)",
            extra=log_extra,
        )
        return

    # Extract message data
    from_phone = msg_data.get("from")
    message_type = msg_data.get("type", "unknown")
    text_content = None
    if message_type == "text" and "text" in msg_data:
        text_content = msg_data["text"].get("body", "")

    # For MVP, we need tenant_id and channel_id from metadata
    # In production, these would come from the webhook metadata or be determined by phone_number_id
    # For now, we'll need to look up the channel by phone_number_id from metadata
    metadata = value.get("metadata", {})
    phone_number_id = metadata.get("phone_number_id")

    if not phone_number_id:
        logger.warning(
            f"Missing phone_number_id in metadata, cannot process message {provider_message_id}",
            extra=log_extra,
        )
        return

    # Look up channel (for MVP, assume single tenant - will be enhanced later)
    from app.db.models import Channel

    channel = db.query(Channel).filter_by(phone_number_id=phone_number_id, is_active=True).first()
    if not channel:
        logger.warning(
            f"Channel not found for phone_number_id={phone_number_id}, message {provider_message_id}",
            extra=log_extra,
        )
        return

    tenant_id = channel.tenant_id
    channel_id = channel.id

    # Persist message (conversation_id will be set by worker)
    message = Message(
        tenant_id=tenant_id,
        conversation_id=None,  # Will be set by worker when conversation is created/updated
        provider_message_id=provider_message_id,
        direction=MessageDirection.INBOUND,
        message_type=message_type,
        raw_payload=msg_data,
        text_content=text_content,
    )

    try:
        db.add(message)
        db.commit()
        logger.info(f"Message {provider_message_id} persisted", extra=log_extra)
    except Exception as e:
        db.rollback()
        logger.error(f"Error persisting message {provider_message_id}: {e}", extra=log_extra)
        raise

    # Enqueue job for worker
    try:
        enqueue_inbound_event(
            tenant_id=str(tenant_id),
            provider_message_id=provider_message_id,
            contact_phone=from_phone or "",
            message_text=text_content or "",
            raw_payload=msg_data,
            channel_id=str(channel_id),
        )
        logger.info(f"Message {provider_message_id} enqueued for processing", extra=log_extra)
    except Exception as e:
        # Log error but don't fail - message is already persisted
        # Worker can retry or we can have a separate retry mechanism
        logger.error(
            f"Error enqueueing message {provider_message_id}: {e}. Message persisted but not queued.",
            extra=log_extra,
        )
        # Re-raise to allow caller to handle
        raise

