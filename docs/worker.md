# Worker & Queue

## Overview

The worker processes `InboundEvent` jobs from Redis queue. It handles the core conversation flow: deduplication, state management, quote generation, and message sending.

## Queue System

**Choice: RQ (Redis Queue)**

**Justification:**
- Lightweight, simple API
- Good for MVP (no heavy dependencies)
- Built on Redis (already in stack)
- Easy to test (in-memory Redis for tests)
- Can migrate to Arq later if needed (similar API)

**Alternative considered:** Arq
- More modern, async/await native
- Better for high-throughput scenarios
- Slightly more complex setup

For MVP, RQ is sufficient and simpler.

## Job Types

### `InboundEvent`
Processes an inbound WhatsApp message.

**Payload:**
```python
{
    "tenant_id": "uuid",
    "provider_message_id": "wamid.xxx",
    "contact_phone": "+5511999999999",
    "message_text": "Hello",
    "raw_payload": {...},
    "channel_id": "uuid"
}
```

**Processing Steps:**
1. **Deduplicate**: Check if `provider_message_id` already processed
2. **Upsert Contact**: Create or update contact record
3. **Upsert Conversation**: Create or get conversation, update `last_message_at`
4. **State Machine**: Determine current state and next action
5. **Process Message**:
   - If `INBOUND` or `CAPTURE_MIN`: Extract data, request missing info, or generate quote
   - If `QUOTE_SENT` or `WAITING_REPLY`: Process user reply (scheduling, questions)
6. **Generate Quote** (if data complete):
   - Call pricing engine
   - Calculate freight
   - Check approval rules
   - If needs approval: Create approval record, transition to `HUMAN_APPROVAL`
   - If OK: Generate quote, transition to `QUOTE_READY`
7. **Send Message** (if quote ready and approved):
   - Format quote message (PT-BR)
   - Call WhatsApp sender service
   - Update conversation state to `QUOTE_SENT`
   - Set `window_expires_at` (24h from now)

### `SendMessage` (Future)
Dedicated job for sending messages (if we need retry logic or rate limiting).

### `ExpireConversations` (Scheduled)
Periodic job to transition expired conversations to `LOST` state.

**Schedule:** Every hour (via cron or RQ scheduler)

**Process:**
- Find conversations where `window_expires_at < NOW()` and state is `QUOTE_SENT` or `WAITING_REPLY`
- Transition to `LOST`

## Worker Implementation

### Structure
```
app/worker/
  - worker.py      # RQ worker setup
  - jobs.py        # Job functions
  - handlers.py    # Message processing logic
```

### Error Handling

**Transient Errors:**
- Database connection lost: Retry with exponential backoff
- WhatsApp API rate limit: Retry after delay
- Redis connection lost: Retry

**Permanent Errors:**
- Invalid payload: Log and fail (don't retry)
- Unknown tenant: Log and fail
- Invalid state transition: Log and fail

**Dead Letter Queue:**
- After max retries, move to DLQ
- Log with full context
- Admin can inspect and reprocess manually

## Testing Strategy

### Unit Tests
- Test job functions with mocked dependencies
- Test state machine transitions
- Test idempotency logic

### Integration Tests
- Use `fakeredis` for in-memory Redis
- Test full flow: webhook -> queue -> worker -> DB
- Test deduplication (same message ID twice)

### Worker Tests
- Start RQ worker in test mode
- Enqueue job, wait for completion
- Verify side effects (DB records, messages sent)

## Monitoring

### Logging
- Structured logging with `request_id` (use `provider_message_id` as request_id)
- Log levels: DEBUG, INFO, WARN, ERROR
- Include: tenant_id, conversation_id, state, action

### Metrics (Future)
- Jobs processed per minute
- Job duration (p50, p95, p99)
- Error rate
- Queue depth

## Deployment

### Systemd Unit
See `docs/infra.md` for systemd unit template.

### Scaling
- Run multiple worker processes on VPS3
- RQ workers are stateless (can scale horizontally)
- Use Redis connection pooling

## Idempotency

**Key:** `provider_message_id`

**Implementation:**
1. Before processing, check if message already processed
2. If yes: Skip processing, log idempotency hit
3. If no: Process and mark as processed

**Database:**
- Unique constraint on `messages.provider_message_id`
- Use `INSERT ... ON CONFLICT DO NOTHING` or check before insert


