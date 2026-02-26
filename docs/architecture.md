# Architecture

## Overview

OrcaZap is a multi-tenant SaaS application built with a clear separation of concerns: API layer, background workers, and data persistence.

## Component Boundaries

### API Layer (FastAPI)

**Responsibilities:**
- Webhook endpoints (WhatsApp Cloud API)
- Admin panel routes (HTMX server-rendered)
- Public pages (landing, registration)
- API endpoints (operator admin, monitoring)
- Authentication and authorization
- Rate limiting and request validation

**Technology:** FastAPI, Uvicorn, HTMX, Jinja2

**Key Modules:**
- `app/routers/` - Route handlers organized by context (public, tenant, api, operator)
- `app/admin/` - Admin panel routes and templates
- `app/middleware/` - Host routing, rate limiting, subscription checks
- `app/core/` - CSRF, sessions, authentication utilities

### Worker Layer (RQ)

**Responsibilities:**
- Process inbound WhatsApp messages
- Generate quotes (pricing, freight, discounts)
- Send WhatsApp messages
- State machine transitions
- Idempotent job processing

**Technology:** RQ (Redis Queue), Redis

**Key Modules:**
- `app/worker/handlers.py` - Job processing logic
- `app/worker/jobs.py` - Job definitions and enqueueing
- `app/domain/` - Business logic (pricing, freight, state machine, parsing)

### Data Layer

**PostgreSQL:**
- Primary database for all persistent data
- 15 models: Tenant, User, Channel, Contact, Conversation, Message, Quote, Approval, Item, PricingRule, FreightRule, etc.
- Alembic migrations for schema management
- Connection pooling via PgBouncer (optional, recommended for production)

**Redis:**
- Job queue (RQ)
- Session storage
- Rate limiting counters
- Optional: caching (future enhancement)

## Multi-Tenancy Architecture

### Host-Based Routing

OrcaZap uses host-based routing to determine tenant context:

- **`orcazap.com`** / **`www.orcazap.com`** → Public context (landing pages, registration, login)
- **`api.orcazap.com`** → API context (webhooks, operator admin, monitoring)
- **`{slug}.orcazap.com`** → Tenant context (tenant dashboard, tenant-specific routes)

**Implementation:**
- Middleware (`app/middleware/host_routing.py`) classifies host on every request
- Sets `request.state.host_context` (PUBLIC, API, TENANT)
- For tenant hosts, resolves tenant from database by slug
- All tenant routes must validate `request.state.tenant` exists

### Tenant Isolation

**Database Level:**
- All tenant-scoped queries include `WHERE tenant_id = ?` filter
- Foreign key relationships enforce tenant boundaries
- Unique constraints scoped to tenant (e.g., `(tenant_id, phone)` for contacts)

**Application Level:**
- Dependencies inject tenant from request state
- All data access functions require `tenant_id` parameter
- Session scoped to tenant (tenant users can only access their tenant's data)

**Network Level:**
- Host routing prevents cross-tenant access (tenant A cannot access tenant B's subdomain)
- API endpoints require operator authentication for cross-tenant access

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    WhatsApp Cloud API                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI Application (Uvicorn)                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Host Routing Middleware                                │  │
│  │  - Classifies host (PUBLIC/API/TENANT)                  │  │
│  │  - Resolves tenant from slug                            │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Routers                                                │  │
│  │  - /webhooks/whatsapp (API host only)                   │  │
│  │  - /admin/* (HTMX, tenant host)                         │  │
│  │  - /api/* (API host, operator auth)                     │  │
│  │  - / (public pages)                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Middleware Stack                                       │  │
│  │  - Rate limiting (per tenant/IP)                        │  │
│  │  - Subscription check (Stripe)                           │  │
│  │  - CSRF protection (HTMX forms)                         │  │
│  │  - Session management (Redis)                            │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────┐         ┌──────────────────────┐
│  PostgreSQL  │         │       Redis           │
│              │         │  ┌──────────────────┐  │
│  - Tenants   │         │  │  RQ Job Queue    │  │
│  - Users     │         │  │  - default       │  │
│  - Channels  │         │  └──────────────────┘  │
│  - Contacts  │         │  ┌──────────────────┐  │
│  - Messages  │         │  │  Sessions         │  │
│  - Quotes    │         │  │  - session:{id}  │  │
│  - Items     │         │  └──────────────────┘  │
│  - Rules     │         │  ┌──────────────────┐  │
│              │         │  │  Rate Limits      │  │
│              │         │  │  - tenant:{id}   │  │
│              │         │  └──────────────────┘  │
└──────────────┘         └──────────────────────┘
                                 │
                                 ▼
                        ┌──────────────────────┐
                        │    RQ Workers        │
                        │  ┌────────────────┐  │
                        │  │ process_inbound│  │
                        │  │ _event()       │  │
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │ generate_quote()│  │
                        │  └────────────────┘  │
                        │  ┌────────────────┐  │
                        │  │ send_message()  │  │
                        │  └────────────────┘  │
                        └──────────────────────┘
```

## Technology Choices

### Why HTMX for Admin Panel

**Decision:** Server-rendered admin panel using HTMX instead of React/Vue.

**Rationale:**
- **Fast development**: No build step, no JS framework complexity
- **Minimal JavaScript**: HTMX handles AJAX via HTML attributes
- **Server-side rendering**: Templates rendered on server, SEO-friendly
- **Simple deployment**: No separate frontend build process
- **Progressive enhancement**: Works without JS, enhanced with HTMX

**Tradeoffs:**
- Less interactive than SPA (acceptable for admin panel)
- Server round-trip for every interaction (acceptable for admin workloads)
- Limited client-side state management (not needed for admin panel)

**Consequence:** Admin panel is fast to build, easy to maintain, and works reliably.

### Why RQ (Redis Queue)

**Decision:** RQ for background job processing instead of Celery, Sidekiq, or Kafka.

**Rationale:**
- **Simple**: Minimal setup, Redis-based, no separate broker
- **VPS-friendly**: Runs well on small VPS instances (1GB RAM)
- **Python-native**: Pure Python, easy to debug
- **Sufficient scale**: Handles thousands of jobs/hour (sufficient for MVP)
- **Low overhead**: No complex message broker, direct Redis connection

**Alternatives Considered:**
- **Celery**: More features but heavier, requires message broker (RabbitMQ/Redis)
- **Sidekiq**: Ruby-only, not applicable
- **Kafka**: Overkill for this use case, complex setup

**Tradeoffs:**
- No built-in task scheduling (use cron + RQ for scheduled jobs)
- No distributed task routing (single queue sufficient for MVP)
- Redis single point of failure (acceptable risk for MVP, can add Redis Sentinel later)

**Consequence:** Simple, reliable job processing that scales to early-stage needs.

### Why Host-Based Multitenancy

**Decision:** Host-based routing (`{slug}.orcazap.com`) instead of path-based (`/tenant/{slug}`) or database-per-tenant.

**Rationale:**
- **Clear tenant context**: Host header determines tenant before request processing
- **Security**: Prevents cross-tenant access at network level
- **User experience**: Each tenant gets their own subdomain (feels like dedicated app)
- **Cookie isolation**: Cookies scoped to subdomain (`.orcazap.com` for cross-subdomain auth)
- **Simple routing**: Middleware resolves tenant once, available to all routes

**Alternatives Considered:**
- **Path-based**: `/tenant/{slug}/...` - requires tenant slug in every route
- **Database-per-tenant**: Separate database per tenant - complex migrations, harder to scale
- **Shared database with RLS**: PostgreSQL Row Level Security - adds complexity, harder to debug

**Tradeoffs:**
- Requires wildcard DNS (`*.orcazap.com`)
- SSL certificate must include wildcard (Let's Encrypt supports this)
- More complex nginx configuration (acceptable)

**Consequence:** Clean tenant isolation with good user experience.

### Why Systemd (No Docker in Production)

**Decision:** systemd services directly on VPS instead of Docker containers.

**Rationale:**
- **Simplicity**: No container orchestration, no Docker daemon overhead
- **Resource efficiency**: Direct process execution, no container layer overhead
- **Easier debugging**: Direct access to logs, processes, filesystem
- **VPS-friendly**: Works well on small VPS instances (1GB RAM)
- **Service management**: systemd handles restarts, logging, dependencies

**Tradeoffs:**
- No container isolation (acceptable for single-tenant VPS)
- Manual dependency management (acceptable for controlled environment)
- Less portable (acceptable for dedicated VPS deployment)

**Consequence:** Simple, efficient deployment that's easy to operate.

### Why PgBouncer (Optional)

**Decision:** PgBouncer for connection pooling (optional but recommended).

**Rationale:**
- **Connection efficiency**: Reduces PostgreSQL connection overhead
- **Resource management**: Limits max connections, prevents connection exhaustion
- **Transaction pooling**: Reuses connections across transactions
- **Production best practice**: Standard for production PostgreSQL deployments

**Tradeoffs:**
- Additional component to manage (acceptable complexity)
- Connection pooling mode limitations (transaction pooling sufficient for this app)

**Consequence:** Better resource utilization and connection management.

## Data Flow

1. **Webhook → API**: WhatsApp sends webhook → FastAPI receives → stores message → enqueues job → returns 200
2. **Worker → Processing**: RQ worker picks job → processes message → updates state → sends response
3. **Admin → Approval**: Admin views pending approvals → approves/rejects → worker sends quote
4. **Quote → Customer**: Quote sent via WhatsApp → customer responds → state updated

See [flows.md](flows.md) for detailed flow diagrams.

## Scalability Considerations

**Current Design (MVP):**
- Single API instance
- Single worker instance (can run multiple worker processes)
- Single PostgreSQL instance
- Single Redis instance

**Future Scaling Path:**
- **Horizontal scaling**: Multiple API instances behind load balancer
- **Worker scaling**: Multiple worker instances, RQ supports multiple workers
- **Database scaling**: Read replicas for read-heavy workloads
- **Redis scaling**: Redis Sentinel for high availability

**Bottlenecks:**
- PostgreSQL write capacity (single instance)
- Redis single point of failure (can add Sentinel)
- Worker processing speed (can add more workers)

For early-stage SaaS, single-instance deployment is sufficient and can scale horizontally when needed.




