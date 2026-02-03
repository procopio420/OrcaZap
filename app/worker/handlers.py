"""Worker job handlers."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.adapters.whatsapp.sender import send_text_message
from app.db.base import SessionLocal
from app.db.models import (
    Approval,
    ApprovalStatus,
    Channel,
    Contact,
    Conversation,
    ConversationState,
    Item,
    Message,
    MessageDirection,
    QuoteStatus,
)
from app.domain.messages import format_quote_message, get_data_capture_prompt
from app.domain.parsing import parse_data_capture_message
from app.domain.quote import QuoteGenerationError, generate_quote
from app.domain.state_machine import Event, transition
from app.middleware.metrics import (
    record_ai_call,
    record_approval_created,
    record_message_processed,
    record_quote_generated,
)

logger = logging.getLogger(__name__)


def process_inbound_event(job_data: dict[str, Any]) -> None:
    """Process an inbound WhatsApp message event.

    Implements idempotency: checks if message already processed.
    Creates/updates contact and conversation, sends data capture prompt.

    Args:
        job_data: Dictionary with tenant_id, provider_message_id, contact_phone,
                  message_text, raw_payload, channel_id

    Raises:
        ValueError: If required keys are missing in job_data
        KeyError: If required keys are missing (should not happen with proper validation)
    """
    # Input validation
    required_keys = ["tenant_id", "provider_message_id", "contact_phone", "channel_id"]
    missing_keys = [key for key in required_keys if key not in job_data]
    if missing_keys:
        raise ValueError(f"Missing required keys in job_data: {missing_keys}")

    provider_message_id = job_data["provider_message_id"]
    tenant_id = UUID(job_data["tenant_id"])
    contact_phone = job_data["contact_phone"]
    channel_id = UUID(job_data["channel_id"])

    log_extra = {"provider_message_id": provider_message_id}

    db: Session = SessionLocal()
    try:
        # Idempotency check: if message already processed, skip
        message = db.query(Message).filter_by(provider_message_id=provider_message_id).first()
        if not message:
            logger.warning(
                f"Message {provider_message_id} not found in DB, skipping",
                extra=log_extra,
            )
            return  # Idempotent - message not found means it wasn't persisted by webhook

        # Check if already processed (has conversation_id set)
        if message.conversation_id is not None:
            logger.info(
                f"Message {provider_message_id} already processed (has conversation), skipping",
                extra=log_extra,
            )
            return  # Idempotent - already processed

        # Get tenant and check subscription status
        from app.db.models import Tenant
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            error_msg = f"Tenant {tenant_id} not found"
            logger.error(error_msg, extra=log_extra)
            raise ValueError(error_msg)
        
        # Check subscription status - block processing if inactive
        if not is_subscription_active(tenant):
            logger.warning(
                f"Message processing blocked for tenant {tenant_id} - subscription inactive",
                extra=log_extra,
            )
            # Don't process message if subscription is inactive
            return  # Idempotent - silently skip
        
        # Get channel
        channel = db.query(Channel).filter_by(id=channel_id, tenant_id=tenant_id).first()
        if not channel:
            error_msg = f"Channel {channel_id} not found for tenant {tenant_id}"
            logger.error(error_msg, extra=log_extra)
            raise ValueError(error_msg)  # Raise instead of silent return

        # Upsert contact
        contact = (
            db.query(Contact)
            .filter_by(tenant_id=tenant_id, phone=contact_phone)
            .first()
        )

        if not contact:
            contact = Contact(tenant_id=tenant_id, phone=contact_phone)
            db.add(contact)
            db.flush()  # Get contact.id
            logger.info(f"Created new contact: {contact.id}", extra=log_extra)
        else:
            logger.debug(f"Using existing contact: {contact.id}", extra=log_extra)

        # Get or create conversation
        conversation = (
            db.query(Conversation)
            .filter_by(
                tenant_id=tenant_id,
                contact_id=contact.id,
                channel_id=channel_id,
            )
            .first()
        )

        if not conversation:
            # New conversation - start in INBOUND state
            conversation = Conversation(
                tenant_id=tenant_id,
                contact_id=contact.id,
                channel_id=channel_id,
                state=ConversationState.INBOUND,
                last_message_at=datetime.now(timezone.utc),
            )
            db.add(conversation)
            db.flush()  # Get conversation.id
            logger.info(f"Created new conversation: {conversation.id}", extra=log_extra)
        else:
            # Update last_message_at
            conversation.last_message_at = datetime.now(timezone.utc)
            logger.debug(f"Updated existing conversation: {conversation.id}", extra=log_extra)

        # Update message with conversation_id
        message.conversation_id = conversation.id
        db.flush()

        # State machine: if INBOUND, transition to CAPTURE_MIN and send prompt
        if conversation.state == ConversationState.INBOUND:
            try:
                new_state = transition(
                    conversation.state,
                    Event.FIRST_MESSAGE_RECEIVED,
                )
                conversation.state = new_state

                # Set window expiration (24h from now)
                conversation.window_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

                # Send data capture prompt BEFORE committing state change
                # This way if send fails, we can rollback
                prompt_text = get_data_capture_prompt(contact.name)
                provider_msg_id = None
                try:
                    provider_msg_id = send_text_message(
                        channel=channel,
                        to_phone=contact_phone,
                        message_text=prompt_text,
                    )
                except Exception as send_error:
                    logger.error(
                        f"Failed to send data capture prompt: {send_error}",
                        extra=log_extra,
                        exc_info=True,
                    )
                    # Rollback state change since message send failed
                    db.rollback()
                    raise

                # Only commit if message was sent successfully
                if provider_msg_id:
                    # Save outbound message
                    outbound_message = Message(
                        tenant_id=tenant_id,
                        conversation_id=conversation.id,
                        provider_message_id=provider_msg_id,
                        direction=MessageDirection.OUTBOUND,
                        message_type="text",
                        raw_payload={"text": {"body": prompt_text}},
                        text_content=prompt_text,
                    )
                    db.add(outbound_message)

                # Commit state change and outbound message together
                db.commit()

                logger.info(
                    f"Sent data capture prompt for conversation {conversation.id}",
                    extra=log_extra,
                )

            except Exception as e:
                db.rollback()
                logger.error(
                    f"Error processing conversation state transition: {e}",
                    extra=log_extra,
                    exc_info=True,
                )
                raise
        elif conversation.state == ConversationState.CAPTURE_MIN:
            # Parse message to extract data
            message_text = job_data.get("message_text", "")
            # Try AI parsing first (will fallback to regex if AI fails)
            # For MVP, we can enable AI parsing via feature flag or tenant setting
            use_ai = job_data.get("use_ai", False)  # Can be enabled per tenant later
            parsed_data, requires_approval = parse_data_capture_message(
                message_text,
                use_ai=use_ai,
                tenant_id=tenant_id,
            )

            if not parsed_data:
                # Data not complete, send error message
                error_text = (
                    "Desculpe, não consegui entender algumas informações.\n\n"
                    "Por favor, envie novamente no formato:\n"
                    "📍 CEP ou bairro\n"
                    "💳 Forma de pagamento\n"
                    "📅 Dia de entrega\n"
                    "📦 Lista de itens\n\n"
                    "Obrigado! 😊"
                )
                try:
                    provider_msg_id = send_text_message(
                        channel=channel,
                        to_phone=contact_phone,
                        message_text=error_text,
                    )
                    if provider_msg_id:
                        error_message = Message(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            provider_message_id=provider_msg_id,
                            direction=MessageDirection.OUTBOUND,
                            message_type="text",
                            raw_payload={"text": {"body": error_text}},
                            text_content=error_text,
                        )
                        db.add(error_message)
                        db.commit()
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}", extra=log_extra)
                    db.rollback()
                return

            # Map parsed items to item_ids (by SKU or name)
            # For MVP, we'll do simple matching
            quote_items = []
            unknown_skus = []

            for item_data in parsed_data["items"]:
                item_name = item_data["name"]
                # Try exact match first (case-insensitive)
                item = (
                    db.query(Item)
                    .filter(Item.name.ilike(item_name))
                    .first()
                )
                # If no exact match, try partial match
                if not item:
                    item = (
                        db.query(Item)
                        .filter(Item.name.ilike(f"%{item_name}%"))
                        .first()
                    )

                if not item:
                    unknown_skus.append(item_name)
                    continue

                # Get tenant item to verify it exists and is active
                from app.db.models import TenantItem

                tenant_item = (
                    db.query(TenantItem)
                    .filter_by(tenant_id=tenant_id, item_id=item.id, is_active=True)
                    .first()
                )

                if not tenant_item:
                    unknown_skus.append(item_name)
                    continue

                quote_items.append({
                    "item_id": str(item.id),
                    "quantity": item_data["quantity"],
                })

            # If we have unknown SKUs, we might need approval
            # For now, if we have at least some items, generate quote
            if not quote_items:
                error_text = (
                    "Desculpe, não encontrei os produtos mencionados no nosso catálogo.\n\n"
                    "Pode verificar os nomes e enviar novamente?"
                )
                try:
                    provider_msg_id = send_text_message(
                        channel=channel,
                        to_phone=contact_phone,
                        message_text=error_text,
                    )
                    if provider_msg_id:
                        error_message = Message(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            provider_message_id=provider_msg_id,
                            direction=MessageDirection.OUTBOUND,
                            message_type="text",
                            raw_payload={"text": {"body": error_text}},
                            text_content=error_text,
                        )
                        db.add(error_message)
                        db.commit()
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}", extra=log_extra)
                    db.rollback()
                return

            # Generate quote
            try:
                quote, needs_approval = generate_quote(
                    db=db,
                    tenant_id=tenant_id,
                    conversation_id=conversation.id,
                    items=quote_items,
                    cep_or_bairro=parsed_data["cep_or_bairro"],
                    payment_method=parsed_data["payment_method"],
                    delivery_day=parsed_data["delivery_day"],
                    request_id=provider_message_id,  # For structured logging
                )

                # If we have unknown SKUs, require approval
                if unknown_skus and not needs_approval:
                    needs_approval = True
                
                # If AI was used, always require approval
                if requires_approval and not needs_approval:
                    needs_approval = True
                
                # Record quote generation
                record_quote_generated(str(tenant_id), "generated")
                
                # Create approval record if needed
                if needs_approval:
                    approval_reason_parts = []
                    reason_type = "other"
                    if unknown_skus:
                        approval_reason_parts.append(f"Unknown SKUs: {', '.join(unknown_skus)}")
                        reason_type = "unknown_sku"
                    if requires_approval:
                        approval_reason_parts.append("IA utilizada para parsing (requer supervisão)")
                        reason_type = "ai_used"
                    
                    approval_reason = "; ".join(approval_reason_parts) or "Aprovação requerida"
                    
                    approval = Approval(
                        tenant_id=tenant_id,
                        quote_id=quote.id,
                        status=ApprovalStatus.PENDING,
                        reason=approval_reason,
                    )
                    db.add(approval)
                    db.flush()
                    
                    # Record approval creation
                    record_approval_created(str(tenant_id), reason_type)

                if needs_approval:
                    # Transition to HUMAN_APPROVAL state
                    new_state = transition(
                        conversation.state,
                        Event.APPROVAL_REQUIRED,
                    )
                    conversation.state = new_state
                    db.commit()

                    # Send approval required message
                    approval_text = (
                        "Olá! 👋\n\n"
                        "Recebi sua solicitação. Para garantir o melhor atendimento, "
                        "nossa equipe está analisando seu pedido e entrará em contato em breve.\n\n"
                        "Você receberá uma resposta em até 2 horas úteis.\n\n"
                        "Obrigado pela compreensão! 🙏"
                    )
                    try:
                        provider_msg_id = send_text_message(
                            channel=channel,
                            to_phone=contact_phone,
                            message_text=approval_text,
                        )
                        if provider_msg_id:
                            approval_message = Message(
                                tenant_id=tenant_id,
                                conversation_id=conversation.id,
                                provider_message_id=provider_msg_id,
                                direction=MessageDirection.OUTBOUND,
                                message_type="text",
                                raw_payload={"text": {"body": approval_text}},
                                text_content=approval_text,
                            )
                            db.add(approval_message)
                            db.commit()
                    except Exception as e:
                        logger.error(f"Failed to send approval message: {e}", extra=log_extra)
                        db.rollback()

                else:
                    # Transition to QUOTE_READY first
                    new_state = transition(
                        conversation.state,
                        Event.MINIMAL_DATA_RECEIVED,
                    )
                    conversation.state = new_state
                    # Don't commit yet - wait for successful message send

                    # Format quote message BEFORE committing
                    discount_amount = quote.subtotal * quote.discount_pct
                    quote_text = format_quote_message(
                        items=quote.items_json,
                        subtotal=float(quote.subtotal),
                        freight=float(quote.freight),
                        discount_pct=float(quote.discount_pct),
                        discount_amount=float(discount_amount),
                        total=float(quote.total),
                        payment_method=parsed_data["payment_method"],
                        delivery_day=parsed_data["delivery_day"],
                        valid_until=quote.valid_until,
                    )

                    # Send quote message BEFORE committing state change
                    try:
                        provider_msg_id = send_text_message(
                            channel=channel,
                            to_phone=contact_phone,
                            message_text=quote_text,
                        )
                    except Exception as send_error:
                        logger.error(
                            f"Failed to send quote message: {send_error}",
                            extra=log_extra,
                            exc_info=True,
                        )
                        db.rollback()
                        raise

                    # Only commit if message was sent successfully
                    if provider_msg_id:
                        # Save quote message
                        quote_message = Message(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            provider_message_id=provider_msg_id,
                            direction=MessageDirection.OUTBOUND,
                            message_type="text",
                            raw_payload={"text": {"body": quote_text}},
                            text_content=quote_text,
                        )
                        db.add(quote_message)

                        # Update window expiration
                        conversation.window_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

                        # Transition to QUOTE_SENT (auto-approved)
                        new_state = transition(conversation.state, Event.QUOTE_AUTO_OK)
                        conversation.state = new_state
                        quote.status = QuoteStatus.SENT

                        # Commit everything together
                        db.commit()

                        logger.info(
                            f"Quote {quote.id} sent for conversation {conversation.id}",
                            extra=log_extra,
                        )
                    else:
                        # Message send returned None - rollback
                        logger.warning(
                            f"Quote message send returned None for quote {quote.id}",
                            extra=log_extra,
                        )
                        db.rollback()
                        raise ValueError("Quote message send failed (returned None)")

            except QuoteGenerationError as e:
                logger.error(f"Quote generation failed: {e}", extra=log_extra, exc_info=True)
                db.rollback()
                # Send error message to user
                error_text = (
                    "Desculpe, ocorreu um erro ao gerar seu orçamento.\n\n"
                    "Nossa equipe foi notificada e entrará em contato em breve."
                )
                try:
                    provider_msg_id = send_text_message(
                        channel=channel,
                        to_phone=contact_phone,
                        message_text=error_text,
                    )
                    if provider_msg_id:
                        error_message = Message(
                            tenant_id=tenant_id,
                            conversation_id=conversation.id,
                            provider_message_id=provider_msg_id,
                            direction=MessageDirection.OUTBOUND,
                            message_type="text",
                            raw_payload={"text": {"body": error_text}},
                            text_content=error_text,
                        )
                        db.add(error_message)
                        db.commit()
                except Exception as send_err:
                    logger.error(f"Failed to send error message: {send_err}", extra=log_extra)
                    db.rollback()

        else:
            # Conversation in other state - not handled in Step 4
            db.commit()
            logger.info(
                f"Conversation {conversation.id} in state {conversation.state}, not handled yet",
                extra=log_extra,
            )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error processing inbound event {provider_message_id}: {e}",
            extra=log_extra,
            exc_info=True,
        )
        raise
    finally:
        db.close()

