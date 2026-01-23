# WhatsApp Cloud API Adapter

## Overview

OrcaZap uses the official WhatsApp Cloud API (via Meta's Business Platform) to receive and send messages.

## Required Environment Variables

```bash
# WhatsApp Cloud API
WHATSAPP_VERIFY_TOKEN=<random_string_for_webhook_verification>
WHATSAPP_ACCESS_TOKEN=<access_token_from_meta>
WHATSAPP_PHONE_NUMBER_ID=<phone_number_id>
WHATSAPP_BUSINESS_ACCOUNT_ID=<waba_id>

# Optional: For local testing
WHATSAPP_WEBHOOK_URL=<public_url_for_webhook>
```

## Webhook Endpoints

### `GET /webhooks/whatsapp`
Webhook verification endpoint (required by Meta).

**Query Parameters:**
- `hub.mode`: Must be "subscribe"
- `hub.verify_token`: Must match `WHATSAPP_VERIFY_TOKEN`
- `hub.challenge`: Random string from Meta

**Response:**
- If verify_token matches: Return `hub.challenge` as plain text (200)
- Otherwise: Return 403

### `POST /webhooks/whatsapp`
Receives inbound messages and status updates from WhatsApp.

**Headers:**
- `X-Hub-Signature-256`: SHA256 HMAC signature (if configured in Meta)
- `Content-Type`: application/json

**Request Body:**
WhatsApp webhook payload (see [Meta docs](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples))

**Response:**
- 200: Message received and queued
- 400: Invalid payload
- 401: Signature verification failed (if enabled)
- 500: Internal error

**Processing:**
1. Verify signature (if configured)
2. Extract `provider_message_id` from payload
3. Check idempotency: if message already processed, return 200 (idempotent)
4. Persist raw payload to `messages` table
5. Enqueue `InboundEvent` job to Redis queue
6. Return 200 immediately (<200ms target)

## Idempotency Strategy

**Key:** `provider_message_id` (unique in `messages` table)

**Process:**
1. Extract `provider_message_id` from webhook payload
2. Check if message with this ID already exists in DB
3. If exists: Return 200 (idempotent response, no duplicate processing)
4. If not: Process normally

**Implementation:**
- Database unique constraint on `messages.provider_message_id`
- Use `INSERT ... ON CONFLICT DO NOTHING` or check before insert
- Log idempotency hits for monitoring

## Sending Messages

### `POST /v1/messages` (WhatsApp API)
We call Meta's API to send messages.

**Endpoint:** `https://graph.facebook.com/v18.0/{phone_number_id}/messages`

**Headers:**
- `Authorization: Bearer {access_token}`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "messaging_product": "whatsapp",
  "to": "+5511999999999",
  "type": "text",
  "text": {
    "body": "Message text here"
  }
}
```

**Response:**
- `messages[0].id`: Provider message ID (store for tracking)

**Error Handling:**
- Rate limits: Retry with exponential backoff
- Invalid phone: Log and mark contact as invalid
- Template required (outside 24h window): Use template message flow

## Local Testing Strategy

### 1. Webhook Verification
Use `ngrok` or similar to expose local server:
```bash
ngrok http 8000
# Use the public URL in Meta webhook configuration
```

### 2. Fixtures
Create test fixtures in `tests/fixtures/whatsapp/`:
- `webhook_text_message.json`: Sample text message payload
- `webhook_status_update.json`: Status update payload
- `webhook_image_message.json`: Image message payload

### 3. Mock Meta API (Optional)
For integration tests, mock the Meta API responses:
- Use `responses` library or `httpx` with `MockTransport`
- Simulate successful sends and error cases

### 4. Idempotency Testing
- Send same webhook payload twice
- Verify only one message record created
- Verify only one job enqueued

## Security

### Webhook Signature Verification
Meta can send `X-Hub-Signature-256` header with SHA256 HMAC.

**Verification:**
1. Extract signature from header
2. Compute HMAC-SHA256 of request body using `WHATSAPP_APP_SECRET`
3. Compare (use constant-time comparison)

**Note:** For MVP, signature verification is optional but recommended for production.

### Access Token Storage
- Store `access_token` encrypted at rest in `channels.access_token_encrypted`
- Or use environment variables per tenant (simpler for MVP)
- Rotate tokens periodically (Meta tokens can expire)

## Rate Limits

WhatsApp Cloud API has rate limits:
- Tier 1: 1,000 conversations per 24h
- Tier 2: 10,000 conversations per 24h
- Higher tiers available

**Handling:**
- Track conversation starts per 24h
- Queue messages if rate limit hit
- Use template messages for outside-window sends

## Message Types Supported (MVP)

- **Text messages**: Full support
- **Status updates**: Acknowledge (read receipts, delivered, etc.)
- **Images**: Extract text from captions (later: OCR for product images)

## Future Enhancements

- Template message support (outside 24h window)
- Media messages (images, documents)
- Interactive messages (buttons, lists)
- Location sharing
- Product catalogs integration


