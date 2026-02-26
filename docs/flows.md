# Application Flows

This document describes the end-to-end flows in OrcaZap, from webhook receipt to quote delivery.

## Inbound Webhook Flow

**Trigger:** WhatsApp Cloud API sends webhook to `/webhooks/whatsapp`

```
WhatsApp Cloud API
    │
    ▼
POST /webhooks/whatsapp (api.orcazap.com)
    │
    ├─► Verify host context (must be API host)
    ├─► Rate limit check (1000/hour per IP)
    ├─► Parse payload (WhatsAppWebhookPayload)
    │
    ├─► For each message in payload:
    │   ├─► Extract provider_message_id
    │   ├─► Check idempotency (query messages table)
    │   │   └─► If exists: log and skip (idempotent)
    │   │
    │   ├─► Extract phone_number_id from metadata
    │   ├─► Look up Channel by phone_number_id
    │   │   └─► If not found: log warning and skip
    │   │
    │   ├─► Persist message to DB:
    │   │   ├─► tenant_id (from channel)
    │   │   ├─► provider_message_id (unique)
    │   │   ├─► direction = INBOUND
    │   │   ├─► text_content (extracted)
    │   │   └─► raw_payload (JSONB)
    │   │
    │   └─► Enqueue InboundEvent job to Redis
    │       └─► Job data: tenant_id, provider_message_id, contact_phone, message_text, channel_id
    │
    └─► Return 200 OK (<200ms target)
```

**Idempotency Key:** `provider_message_id` (unique constraint in messages table)

**Failure Modes:**
- **Duplicate webhook**: Idempotency check prevents duplicate processing
- **Missing channel**: Message logged but not processed (requires channel configuration)
- **DB error**: Transaction rollback, webhook returns 500 (WhatsApp will retry)
- **Queue error**: Message persisted but not enqueued (can be retried manually)

## Worker Inbound Processing Flow

**Trigger:** RQ worker picks up `InboundEvent` job from Redis queue

```
RQ Worker
    │
    ▼
process_inbound_event(job_data)
    │
    ├─► Validate job_data (tenant_id, provider_message_id, channel_id)
    ├─► Get message from DB by provider_message_id
    │   └─► If not found: log warning and return (idempotent)
    │
    ├─► Check if already processed (conversation_id set)
    │   └─► If yes: log and return (idempotent)
    │
    ├─► Get tenant and check subscription status
    │   └─► If inactive: log warning and return (skip processing)
    │
    ├─► Get channel (validate tenant_id matches)
    │
    ├─► Upsert contact:
    │   ├─► Query by (tenant_id, phone)
    │   └─► If not exists: create new contact
    │
    ├─► Get or create conversation:
    │   ├─► Query by (tenant_id, contact_id, channel_id)
    │   └─► If not exists: create with state = INBOUND
    │
    ├─► Update message.conversation_id
    │
    └─► State machine handling:
        │
        ├─► If state = INBOUND:
        │   ├─► Transition: INBOUND → CAPTURE_MIN (Event.FIRST_MESSAGE_RECEIVED)
        │   ├─► Set window_expires_at (24h from now)
        │   ├─► Send data capture prompt via WhatsApp
        │   │   └─► If send fails: rollback state change
        │   └─► Commit transaction
        │
        ├─► If state = CAPTURE_MIN:
        │   └─► See "Quote Generation Flow" below
        │
        └─► If state = other:
            └─► Log and commit (handled in future flows)
```

**Idempotency:** Worker checks `message.conversation_id` to prevent duplicate processing.

**Failure Modes:**
- **Worker crash mid-processing**: Job retried by RQ, idempotency check prevents duplicate work
- **WhatsApp API failure**: State change rolled back, job fails and retries
- **DB deadlock**: Transaction rollback, job retries

## Quote Generation Flow

**Trigger:** Worker processes message in `CAPTURE_MIN` state

```
Worker (state = CAPTURE_MIN)
    │
    ▼
Parse message (LLM or regex)
    │
    ├─► Extract:
    │   ├─► CEP or bairro (delivery location)
    │   ├─► Payment method (PIX, credit card, etc.)
    │   ├─► Delivery day
    │   └─► Items list (name, quantity)
    │
    └─► If parsing fails:
        ├─► Send error message to customer
        └─► Return (stay in CAPTURE_MIN state)
    │
    ▼
Map items to catalog
    │
    ├─► For each item in parsed data:
    │   ├─► Query Item by name (case-insensitive, partial match)
    │   ├─► Query TenantItem by (tenant_id, item_id, is_active)
    │   └─► If not found: add to unknown_skus list
    │
    └─► If no items found:
        ├─► Send error message to customer
        └─► Return
    │
    ▼
generate_quote()
    │
    ├─► Look up item prices (TenantItem.base_price)
    ├─► Calculate subtotal (sum of item prices × quantities)
    │
    ├─► Apply volume discounts:
    │   ├─► Query VolumeDiscount rules
    │   └─► Apply discount if quantity threshold met
    │
    ├─► Calculate freight:
    │   ├─► Query FreightRule by CEP range or bairro
    │   └─► Apply freight amount
    │
    ├─► Apply payment method discount:
    │   ├─► Query PricingRule.pix_discount_pct (if PIX)
    │   └─► Apply discount percentage
    │
    ├─► Calculate margin:
    │   └─► margin = (total - cost) / total
    │
    ├─► Check approval rules:
    │   ├─► If unknown_skus: needs_approval = true
    │   ├─► If margin < PricingRule.margin_min_pct: needs_approval = true
    │   ├─► If total > PricingRule.approval_threshold_total: needs_approval = true
    │   └─► If AI used for parsing: needs_approval = true
    │
    └─► Create Quote record:
        ├─► items_json (array of {item_id, quantity, unit_price, total})
        ├─► subtotal, freight, discount_pct, total
        ├─► margin_pct
        ├─► status = DRAFT
        └─► valid_until (7 days from now)
    │
    ▼
If needs_approval:
    │
    ├─► Create Approval record:
    │   ├─► status = PENDING
    │   ├─► reason (unknown_skus, low_margin, high_value, ai_used)
    │   └─► quote_id
    │
    ├─► Transition: CAPTURE_MIN → HUMAN_APPROVAL (Event.APPROVAL_REQUIRED)
    ├─► Send approval required message to customer
    └─► Commit transaction
    │
Else (auto-approve):
    │
    ├─► Transition: CAPTURE_MIN → QUOTE_READY (Event.MINIMAL_DATA_RECEIVED)
    ├─► Format quote message (PT-BR)
    ├─► Send quote via WhatsApp
    │   └─► If send fails: rollback state change
    ├─► Transition: QUOTE_READY → QUOTE_SENT (Event.QUOTE_AUTO_OK)
    ├─► Update quote.status = SENT
    ├─► Update window_expires_at (24h from now)
    └─► Commit transaction
```

**Failure Modes:**
- **Pricing rule missing**: Quote generation fails, error message sent to customer
- **Freight rule missing**: Quote generation fails, requires manual approval
- **WhatsApp send failure**: State change rolled back, job retries

## Approval Flow

**Trigger:** Admin views pending approvals in HTMX dashboard

```
Admin Panel (HTMX)
    │
    ▼
GET /admin/approvals ({slug}.orcazap.com)
    │
    ├─► Require authentication (tenant user)
    ├─► Query pending approvals:
    │   └─► SELECT * FROM approvals
    │       WHERE tenant_id = ? AND status = 'pending'
    │       ORDER BY created_at DESC
    │
    └─► Render approval list (HTMX template)
    │
    ▼
Admin clicks "Approve" or "Reject"
    │
    ▼
POST /admin/approvals/{id}/approve (or /reject)
    │
    ├─► Require CSRF token
    ├─► Require authentication
    ├─► Get approval from DB (validate tenant_id)
    │
    ├─► If approve:
    │   ├─► Update approval.status = APPROVED
    │   ├─► Update approval.approved_by_user_id
    │   ├─► Get quote and conversation
    │   ├─► Transition: HUMAN_APPROVAL → QUOTE_SENT (Event.ADMIN_APPROVED)
    │   ├─► Format quote message (PT-BR)
    │   ├─► Send quote via WhatsApp
    │   │   └─► If send fails: rollback and show error
    │   ├─► Update quote.status = SENT
    │   ├─► Update window_expires_at (24h from now)
    │   └─► Commit transaction
    │
    └─► If reject:
        ├─► Update approval.status = REJECTED
        ├─► Update approval.approved_by_user_id
        ├─► Transition: HUMAN_APPROVAL → LOST (Event.ADMIN_REJECTED)
        ├─► Optionally send rejection message to customer
        └─► Commit transaction
```

**Failure Modes:**
- **WhatsApp send failure**: Approval committed but quote not sent (can retry manually)
- **Concurrent approval**: Database constraint prevents duplicate approval

## Quote Response Flow

**Trigger:** Customer responds to quote message

```
Customer sends message
    │
    ▼
Webhook → Worker (same as inbound flow)
    │
    ├─► Conversation state = QUOTE_SENT
    ├─► Parse message intent:
    │   ├─► Accept/confirm → schedule_confirmed
    │   ├─► Decline/reject → user_declined
    │   └─► Other/question → user_replied
    │
    └─► State machine transition:
        │
        ├─► If schedule_confirmed:
        │   ├─► Transition: QUOTE_SENT → WAITING_REPLY (Event.USER_REPLIED)
        │   ├─► Extract delivery date/time
        │   ├─► Send confirmation message
        │   └─► Transition: WAITING_REPLY → WON (Event.SCHEDULE_CONFIRMED)
        │
        ├─► If user_declined:
        │   ├─► Transition: QUOTE_SENT → LOST (Event.USER_DECLINED)
        │   └─► Update quote.status = LOST
        │
        └─► If user_replied (question):
            ├─► Transition: QUOTE_SENT → WAITING_REPLY (Event.USER_REPLIED)
            └─► Send response (future: AI-powered or manual)
```

**Window Expiration:**
- If `window_expires_at` passes without customer response:
  - Background job (cron) transitions: `QUOTE_SENT → LOST` (Event.WINDOW_EXPIRED)
  - Updates quote.status = LOST

## Failure Modes Summary

### Webhook Failures
- **WhatsApp retries**: Webhook idempotency prevents duplicate processing
- **Rate limiting**: Returns 429, WhatsApp backs off
- **DB unavailable**: Returns 500, WhatsApp retries

### Worker Failures
- **Job retry**: RQ retries failed jobs (exponential backoff)
- **Idempotency**: Prevents duplicate processing on retry
- **Poison messages**: Jobs that fail repeatedly are moved to failed queue (manual review)

### WhatsApp API Failures
- **Rate limits**: Retry with exponential backoff
- **Invalid phone**: Log error, mark contact as invalid
- **Template required**: Outside 24h window, requires template message flow (future)

### Database Failures
- **Connection pool exhausted**: PgBouncer limits connections, returns error
- **Deadlock**: Transaction rollback, job retries
- **Constraint violation**: Idempotency prevents duplicate inserts

## Idempotency Strategy

**Keys:**
- **Webhook level**: `provider_message_id` (unique in messages table)
- **Worker level**: `message.conversation_id` (prevents duplicate processing)
- **Job level**: RQ job ID (prevents duplicate enqueueing)

**Implementation:**
- Database unique constraints enforce idempotency
- Worker checks before processing (idempotent reads)
- Failed jobs can be retried safely




