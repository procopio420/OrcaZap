# Conversation State Machine

## States

| State | Description |
|-------|-------------|
| `INBOUND` | Initial state when first message received |
| `CAPTURE_MIN` | Waiting for user to provide minimal data (CEP/bairro, payment, delivery, items) |
| `QUOTE_READY` | Quote generated, ready to send |
| `QUOTE_SENT` | Quote sent to user, waiting for reply |
| `WAITING_REPLY` | Waiting for user response (scheduling, questions, etc.) |
| `HUMAN_APPROVAL` | Quote requires human approval before sending |
| `WON` | Quote accepted, order confirmed |
| `LOST` | Conversation ended without conversion |

## State Transitions

| From State | Event | To State | Actions |
|------------|-------|----------|---------|
| `INBOUND` | `first_message_received` | `CAPTURE_MIN` | Create conversation, send data capture prompt |
| `CAPTURE_MIN` | `minimal_data_received` | `QUOTE_READY` | Generate quote, check approval rules |
| `QUOTE_READY` | `approval_required` | `HUMAN_APPROVAL` | Create approval record, notify admin |
| `QUOTE_READY` | `quote_approved` | `QUOTE_SENT` | Send quote message, update state |
| `QUOTE_READY` | `quote_auto_ok` | `QUOTE_SENT` | Send quote message, update state |
| `QUOTE_SENT` | `user_replied` | `WAITING_REPLY` | Process reply (scheduling, questions) |
| `WAITING_REPLY` | `schedule_confirmed` | `WON` | Mark as won, send confirmation |
| `WAITING_REPLY` | `user_declined` | `LOST` | Mark as lost |
| `WAITING_REPLY` | `window_expired` | `LOST` | Mark as lost (24h window) |
| `HUMAN_APPROVAL` | `admin_approved` | `QUOTE_SENT` | Send quote message, update state |
| `HUMAN_APPROVAL` | `admin_rejected` | `LOST` | Mark as lost, optionally notify user |
| `QUOTE_SENT` | `window_expired` | `LOST` | Mark as lost (24h window) |

## Events

### `first_message_received`
- Triggered when: First inbound message from a contact
- Data: `contact_phone`, `message_text`, `provider_message_id`

### `minimal_data_received`
- Triggered when: User provides CEP/bairro, payment method, delivery day, and item list
- Data: `cep_or_bairro`, `payment_method`, `delivery_day`, `items` (list of {sku, quantity})

### `approval_required`
- Triggered when: Quote violates rules (unknown SKU, margin too low, total too high, freight uncertainty)
- Data: `quote_id`, `reason`

### `quote_approved`
- Triggered when: Admin approves a pending quote
- Data: `quote_id`, `approved_by_user_id`

### `quote_auto_ok`
- Triggered when: Quote passes all rules, no approval needed
- Data: `quote_id`

### `user_replied`
- Triggered when: User sends a message after quote was sent
- Data: `message_text`, `provider_message_id`

### `schedule_confirmed`
- Triggered when: User confirms delivery scheduling
- Data: `delivery_date`, `delivery_time`

### `user_declined`
- Triggered when: User explicitly declines or says no
- Data: `reason` (optional)

### `window_expired`
- Triggered when: 24h window expires without user interaction
- Data: `conversation_id`

### `admin_approved` / `admin_rejected`
- Triggered when: Admin approves or rejects a quote
- Data: `approval_id`, `approved_by_user_id`, `reason` (for rejection)

## State Machine Implementation

The state machine should be implemented in `app/domain/state_machine.py` with:
- `State` enum
- `Event` enum
- `StateMachine` class with `transition()` method
- Validation of allowed transitions
- Side effects (e.g., sending messages) handled by callbacks

## Window Management

WhatsApp has a 24-hour messaging window. After sending a message, we have 24 hours to send free messages. After that, we can only send template messages.

- `window_expires_at` is set when we send a message
- If window expires, transition to `LOST` state
- For template messages (outside window), we may need a separate flow


