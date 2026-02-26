# ADR 0003: Host-Based Multitenancy

**Status:** Accepted  
**Date:** 2024-12  
**Deciders:** Platform Engineering Team

## Context

OrcaZap is a multi-tenant SaaS application. We need to:
- Isolate tenant data (tenant A cannot access tenant B's data)
- Provide each tenant with their own subdomain (e.g., `loja-exemplo.orcazap.com`)
- Route requests to the correct tenant context
- Support public pages (`orcazap.com`) and API endpoints (`api.orcazap.com`)

We need a multi-tenancy strategy that:
- Provides strong tenant isolation
- Is easy to implement and maintain
- Provides good user experience (each tenant feels like dedicated app)
- Scales to hundreds of tenants

## Decision

We will use **host-based routing** with tenant subdomains (`{slug}.orcazap.com`).

## Decision Drivers

- **Clear tenant context**: Host header determines tenant before request processing
- **Security**: Prevents cross-tenant access at network level
- **User experience**: Each tenant gets their own subdomain (feels like dedicated app)
- **Cookie isolation**: Cookies scoped to subdomain (`.orcazap.com` for cross-subdomain auth)
- **Simple routing**: Middleware resolves tenant once, available to all routes

## Considered Options

### Option 1: Host-Based Routing (`{slug}.orcazap.com`) ✅

**Pros:**
- Clear tenant context (host header determines tenant)
- Strong isolation (DNS prevents cross-tenant access)
- Good UX (each tenant gets dedicated subdomain)
- Cookie scoping (cookies work per subdomain)
- Simple middleware (resolve tenant once per request)

**Cons:**
- Requires wildcard DNS (`*.orcazap.com`)
- SSL certificate must include wildcard (Let's Encrypt supports this)
- More complex nginx configuration (acceptable)

**Implementation:**
- Middleware classifies host: `{slug}.orcazap.com` → tenant, `api.orcazap.com` → API, `orcazap.com` → public
- Tenant resolved from database by slug
- All routes have access to `request.state.tenant`

### Option 2: Path-Based Routing (`/tenant/{slug}/...`)

**Pros:**
- No DNS configuration needed
- Simple SSL (single certificate)
- Works with any domain

**Cons:**
- Tenant slug in every route (verbose)
- Less intuitive UX (tenant slug in URL path)
- Easier to make mistakes (forgetting tenant context)
- Cookie scoping more complex

**Why not chosen:** Less intuitive UX, more error-prone.

### Option 3: Database-Per-Tenant

**Pros:**
- Strongest isolation (separate databases)
- Easy to scale per tenant
- Can backup/restore per tenant

**Cons:**
- Complex migrations (run on all databases)
- Harder to do cross-tenant queries (if needed)
- More complex deployment
- Higher operational overhead

**Why not chosen:** Too complex for early-stage SaaS, unnecessary overhead.

### Option 4: Shared Database with Row-Level Security (RLS)

**Pros:**
- Database-enforced isolation
- Single database (simpler migrations)

**Cons:**
- PostgreSQL RLS adds complexity
- Harder to debug (RLS policies can be opaque)
- Less flexible (harder to do cross-tenant queries if needed)

**Why not chosen:** Adds complexity without clear benefit over application-level filtering.

## Consequences

### Positive

- **Strong isolation**: DNS + middleware prevents cross-tenant access
- **Good UX**: Each tenant feels like they have a dedicated app
- **Simple routing**: Middleware resolves tenant once, available everywhere
- **Cookie scoping**: Cookies work naturally with subdomains
- **Clear context**: Host header makes tenant context obvious

### Negative

- **DNS complexity**: Requires wildcard DNS record
- **SSL complexity**: Wildcard certificate needed (Let's Encrypt supports this)
- **Nginx complexity**: More complex nginx configuration (acceptable)

### Neutral

- **Tenant slug validation**: Must validate slug format (regex: `^[a-z0-9-]{3,32}$`)
- **Tenant lookup**: Database query per request (acceptable, can cache if needed)

## Implementation Notes

- Middleware (`app/middleware/host_routing.py`) classifies host on every request
- Sets `request.state.host_context` (PUBLIC, API, TENANT)
- For tenant hosts, resolves tenant from database by slug
- All tenant routes validate `request.state.tenant` exists (404 if not found)
- All data queries include `tenant_id` filter

## Security Considerations

- **DNS prevents cross-tenant access**: Tenant A cannot access tenant B's subdomain
- **Middleware validation**: Tenant must exist in database (404 if not found)
- **Database filtering**: All queries include `tenant_id` filter
- **Session scoping**: Sessions include `tenant_id`, users can only access their tenant

## Example Flow

```
Request: GET https://loja-exemplo.orcazap.com/admin/approvals
    │
    ▼
Host Routing Middleware
    │
    ├─► Extract host: "loja-exemplo.orcazap.com"
    ├─► Classify: TENANT
    ├─► Extract slug: "loja-exemplo"
    ├─► Query database: SELECT * FROM tenants WHERE slug = 'loja-exemplo'
    ├─► Set request.state.tenant = Tenant(...)
    └─► Continue to route handler
    │
    ▼
Route Handler
    │
    ├─► Get tenant from request.state.tenant
    ├─► Query approvals: SELECT * FROM approvals WHERE tenant_id = ?
    └─► Return response
```

## Future Considerations

- **Caching**: Cache tenant lookups if needed (Redis)
- **Tenant slug validation**: Enforce slug format at database level
- **Subdomain validation**: Validate subdomain matches tenant slug
- **Custom domains**: Allow tenants to use custom domains (future feature)

## References

- [Multi-Tenancy Patterns](https://docs.microsoft.com/en-us/azure/sql-database/saas-tenancy-app-design-patterns)
- [Host-Based Routing in FastAPI](https://fastapi.tiangolo.com/advanced/middleware/)




