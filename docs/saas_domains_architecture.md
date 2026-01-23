# OrcaZap — Multi-domain SaaS Architecture

## Overview

OrcaZap is implemented as a multi-domain SaaS platform with:

- **Public site** on apex + www: `orcazap.com`, `www.orcazap.com`
- **Tenant dashboards** on subdomain slugs: `https://{tenant_slug}.orcazap.com`
- **API** on `https://api.orcazap.com` hosting:
  - public API endpoints (webhooks)
  - internal **admin API/UI for the operator** (me)
- One FastAPI codebase behind Nginx. Route by `Host` header.
- Cross-subdomain auth: login on `orcazap.com` must redirect user to correct tenant subdomain and keep session valid across `.orcazap.com`.

## Domain & Routing Requirements

### Hosts
- `orcazap.com` + `www.orcazap.com`: Public marketing + register + onboarding + central login
- `*.orcazap.com` (wildcard): Tenant dashboard per slug (HTMX)
- `api.orcazap.com`: API (webhooks + JSON) + **internal admin UI/API** for the operator

### DNS
- A record: apex → VPS1
- CNAME: www → apex
- A record: api → VPS1
- A record: wildcard `*` → VPS1

### TLS
- Must support:
  - `orcazap.com`, `www.orcazap.com`, `api.orcazap.com`, `*.orcazap.com`
- Implementation plan:
  - DNS-01 wildcard certificate (Let's Encrypt) recommended.
- Documented in `docs/infra_domains_tls.md` (to be created in Phase 5).

## Core Architectural Decisions

### 1) Single FastAPI app (initial)
- One app serves public pages, tenant dashboards, and api endpoints.
- Nginx does TLS + reverse proxy to `127.0.0.1:8000`.
- FastAPI routes are restricted by host classification.

### 2) Host-based routing middleware
Implemented in `app/middleware/host_routing.py`:
- Extract host (strip port).
- Classify host:
  - PUBLIC: `orcazap.com`, `www.orcazap.com`
  - API: `api.orcazap.com`
  - TENANT: `{slug}.orcazap.com` (slug must match regex `^[a-z0-9-]{3,32}$`)
- For tenant host:
  - resolve `tenant` by slug from DB
  - attach `request.state.tenant`
- Provide a clear 404/tenant-not-found page with CTA.

### 3) Cross-subdomain sessions
- Auth cookie must be valid across all subdomains:
  - `Domain=.orcazap.com`
  - `Secure`, `HttpOnly`, `SameSite=Lax`
- Session storage: Redis (implemented in `app/core/sessions.py`).
- Central login at apex must redirect to correct `{slug}.orcazap.com`.

### 4) Internal operator admin (on API host)
- `api.orcazap.com/admin` provides an operator-only interface:
  - view tenants
  - impersonate tenant (optional later)
  - view system metrics and queues (basic)
  - view webhook logs / failures
- Protected by separate operator authentication:
  - MVP: Basic Auth via env vars (documented security trade-offs).

## Implementation Status

### Phase 0: Foundations - Host Routing + Skeleton Pages ✅
- [x] Host classification middleware
- [x] Base routers (public, tenant, api)
- [x] Tenant slug field added to model
- [x] Placeholder pages on correct hosts
- [x] Tests for host routing

### Phase 1: Public Site - Landing + Register + Onboarding Wizard ✅
- [x] Landing page with PT-BR copy and warnings
- [x] Registration flow (creates tenant + owner user)
- [x] Login/logout with cross-subdomain sessions
- [x] Onboarding wizard structure (steps 1-5)
- [x] Pricing page and Stripe checkout

### Phase 2: Tenant Dashboard (HTMX) ✅
- [x] Tenant dashboard with metrics
- [x] Approvals queue page
- [x] Navigation structure
- [x] Subscription status banner
- [x] Authentication redirects

### Phase 3: API Host - Webhooks + Internal Operator Admin ✅
- [x] Webhooks gated to API host
- [x] Operator admin UI (dashboard, tenants, logs)
- [x] Basic Auth for operator
- [x] Webhook idempotency utilities
- [x] Tests for API host routing

### Phase 4: Stripe Subscription + Gating ✅
- [x] Stripe integration (checkout, webhooks)
- [x] Subscription status tracking
- [x] Subscription gating (banner in dashboard)
- [x] Webhook event processing (idempotent)

### Phase 5: Wildcard TLS + Nginx Production Routing ✅
- [x] Nginx wildcard config template
- [x] TLS certificate documentation
- [x] DNS configuration documentation

## Slug Rules

- Format: `^[a-z0-9-]{3,32}$`
- Lowercase, digits, hyphen only
- Min 3, max 32 characters
- Unique constraint in database
- Generated from store name using `app/domain/slug.py`

## Session Management

- Storage: Redis
- Cookie: `session_id` with `Domain=.orcazap.com`
- TTL: 7 days
- Attributes: `Secure`, `HttpOnly`, `SameSite=Lax`

## File Structure

```
app/
├── middleware/
│   └── host_routing.py      # Host classification and tenant resolution
├── routers/
│   ├── public.py            # Public site routes
│   ├── tenant.py            # Tenant dashboard routes
│   ├── api.py               # API routes
│   └── auth.py              # Shared auth utilities
├── core/
│   ├── sessions.py          # Redis session management
│   ├── dependencies.py       # FastAPI dependencies
│   └── templates.py         # Template rendering
└── domain/
    └── slug.py              # Slug generation and validation
```

## Testing

- Unit tests: `tests/unit/test_host_routing.py`
- Integration tests: `tests/integration/test_host_routing.py`, `test_public_auth.py`
- All tests must pass with 0 skips after each phase.

