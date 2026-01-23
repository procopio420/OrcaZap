# Data Model

## Overview

OrcaZap uses a multi-tenant architecture with strict tenant isolation. All queries must include tenant_id filtering.

## Core Entities

### Tenants & Users

#### `tenants`
- `id` (UUID, PK)
- `name` (string)
- `created_at` (timestamp)
- `updated_at` (timestamp)

#### `users`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `email` (string, unique per tenant)
- `password_hash` (string)
- `role` (enum: 'owner' | 'attendant')
- `created_at` (timestamp)
- `updated_at` (timestamp)

### WhatsApp Channel

#### `channels`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `waba_id` (string, WhatsApp Business Account ID)
- `phone_number_id` (string)
- `access_token_encrypted` (string, encrypted at rest)
- `webhook_verify_token` (string, for webhook verification)
- `is_active` (boolean)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### Catalog & Pricing

#### `items`
- `id` (UUID, PK)
- `sku` (string, unique)
- `name` (string)
- `unit` (string, e.g., 'kg', 'm²', 'un')
- `created_at` (timestamp)
- `updated_at` (timestamp)

#### `tenant_items`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `item_id` (UUID, FK -> items.id)
- `price_base` (decimal)
- `is_active` (boolean)
- `created_at` (timestamp)
- `updated_at` (timestamp)
- Unique constraint: (tenant_id, item_id)

#### `pricing_rules`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `pix_discount_pct` (decimal, e.g., 0.05 for 5%)
- `margin_min_pct` (decimal, minimum margin percentage)
- `approval_threshold_total` (decimal, requires approval if quote total exceeds this)
- `approval_threshold_margin` (decimal, requires approval if margin below this)
- `created_at` (timestamp)
- `updated_at` (timestamp)

#### `volume_discounts`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `item_id` (UUID, FK -> items.id, nullable for global rules)
- `min_quantity` (decimal)
- `discount_pct` (decimal)
- `created_at` (timestamp)
- `updated_at` (timestamp)

#### `freight_rules`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `bairro` (string, nullable)
- `cep_range_start` (string, nullable)
- `cep_range_end` (string, nullable)
- `base_freight` (decimal)
- `per_kg_additional` (decimal, nullable)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### Conversations

#### `contacts`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `phone` (string, normalized)
- `name` (string, nullable, from WhatsApp profile)
- `created_at` (timestamp)
- `updated_at` (timestamp)
- Unique constraint: (tenant_id, phone)

#### `conversations`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `contact_id` (UUID, FK -> contacts.id)
- `channel_id` (UUID, FK -> channels.id)
- `state` (enum: INBOUND | CAPTURE_MIN | QUOTE_READY | QUOTE_SENT | WAITING_REPLY | HUMAN_APPROVAL | WON | LOST)
- `window_expires_at` (timestamp, nullable, 24h window for WhatsApp)
- `last_message_at` (timestamp)
- `created_at` (timestamp)
- `updated_at` (timestamp)

#### `messages`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `conversation_id` (UUID, FK -> conversations.id)
- `provider_message_id` (string, unique, from WhatsApp)
- `direction` (enum: 'inbound' | 'outbound')
- `message_type` (string, e.g., 'text', 'image')
- `raw_payload` (JSONB)
- `text_content` (text, nullable, extracted from payload)
- `created_at` (timestamp)
- Unique constraint: provider_message_id

### Quotes & Approvals

#### `quotes`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `conversation_id` (UUID, FK -> conversations.id)
- `status` (enum: 'draft' | 'sent' | 'expired' | 'won' | 'lost')
- `items_json` (JSONB, array of {item_id, quantity, unit_price, total})
- `subtotal` (decimal)
- `freight` (decimal)
- `discount_pct` (decimal, e.g., PIX discount)
- `total` (decimal)
- `margin_pct` (decimal, calculated)
- `valid_until` (timestamp)
- `payload_json` (JSONB, full quote details)
- `created_at` (timestamp)
- `updated_at` (timestamp)

#### `approvals`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `quote_id` (UUID, FK -> quotes.id)
- `status` (enum: 'pending' | 'approved' | 'rejected')
- `reason` (text, nullable, why approval needed)
- `approved_by_user_id` (UUID, FK -> users.id, nullable)
- `approved_at` (timestamp, nullable)
- `created_at` (timestamp)
- `updated_at` (timestamp)

### Audit Log

#### `audit_log`
- `id` (UUID, PK)
- `tenant_id` (UUID, FK -> tenants.id)
- `entity_type` (string, e.g., 'quote', 'pricing_rule')
- `entity_id` (UUID)
- `action` (string, e.g., 'create', 'update', 'approve')
- `user_id` (UUID, FK -> users.id, nullable)
- `before_json` (JSONB, nullable)
- `after_json` (JSONB, nullable)
- `created_at` (timestamp)

## Indexes

- `messages.provider_message_id` (unique index for idempotency)
- `conversations.tenant_id, state` (for state queries)
- `approvals.tenant_id, status` (for pending approvals)
- `contacts.tenant_id, phone` (unique index)
- All foreign keys should have indexes

## Tenant Isolation

All queries must include `WHERE tenant_id = ?` to enforce isolation. Consider Row Level Security (RLS) in PostgreSQL for additional safety.


