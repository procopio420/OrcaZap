# Security

This document describes OrcaZap's security model, including tenant isolation, authentication, and protection mechanisms.

## Tenant Isolation

### Host-Based Routing

**Implementation:**
- Middleware (`app/middleware/host_routing.py`) classifies host on every request
- Tenant subdomains: `{slug}.orcazap.com` → resolves tenant from database
- Public hosts: `orcazap.com`, `www.orcazap.com` → no tenant context
- API host: `api.orcazap.com` → no tenant context (operator-only)

**Security:**
- Tenant A cannot access tenant B's subdomain (DNS prevents this)
- Tenant routes validate `request.state.tenant` exists (404 if not found)
- All tenant-scoped queries include `tenant_id` filter

### Database-Level Isolation

**All tenant-scoped queries must include `tenant_id` filter:**
```python
# ✅ Correct
db.query(Contact).filter_by(tenant_id=tenant_id, phone=phone).first()

# ❌ Wrong (missing tenant_id)
db.query(Contact).filter_by(phone=phone).first()
```

**Unique constraints scoped to tenant:**
- `(tenant_id, phone)` for contacts
- `(tenant_id, slug)` for tenants
- Foreign keys enforce tenant boundaries

**Session scoping:**
- Tenant users can only access their tenant's data
- Sessions include `tenant_id` in session data
- Dependencies inject tenant from request state

### Application-Level Isolation

**Dependencies:**
- `get_current_tenant()` dependency requires tenant host and valid tenant
- All route handlers use tenant from dependency (not from user input)
- Tenant ID never comes from request parameters (only from host routing)

**Data access functions:**
- All data access functions require `tenant_id` parameter
- No global queries without tenant filter
- Tenant ID validated before database queries

## Authentication Model

### Tenant Users

**Roles:**
- **Owner**: Full access to tenant settings, pricing, freight rules
- **Attendant**: Can approve/reject quotes, view dashboard

**Authentication:**
- Email + password (bcrypt, 12 rounds)
- Session-based (Redis, 24h expiry)
- Session cookie: `session_id` with `Domain=.orcazap.com` (cross-subdomain)

**Session Management:**
- Sessions stored in Redis: `session:{session_id}`
- Session data: `{user_id, csrf_token, expires_at}`
- Session expiry: 24 hours (extendable on activity)
- Session deletion on logout

**Password Security:**
- Bcrypt hashing (12 rounds)
- Passwords never logged
- Password reset flow (future)

### Operator Accounts

**Purpose:**
- System-wide admin access (cross-tenant)
- Operator admin panel on `api.orcazap.com`
- Create tenants, manage system settings

**Authentication:**
- Username + password (bcrypt, 12 rounds)
- Separate from tenant users
- Session-based (same Redis storage, different session key prefix)

**Access Control:**
- Operator routes require operator authentication
- Operator can access all tenants (for support/admin)
- Operator actions logged for audit

## CSRF Protection

### Implementation

**CSRF tokens:**
- Generated on session creation: `secrets.token_urlsafe(32)`
- Stored in session (Redis): `session:{session_id}.csrf_token`
- Sent to client as cookie: `csrf_token`
- Required on all POST/PUT/DELETE requests

**Validation:**
- Token from header: `X-CSRF-Token` (for HTMX/AJAX)
- Token from cookie: `csrf_token` (for form submissions)
- Constant-time comparison: `secrets.compare_digest()`
- Validation in `app/core/csrf.py`

**HTMX Integration:**
- HTMX automatically sends `X-CSRF-Token` header
- Server validates token on every state-changing request
- CSRF middleware rejects invalid tokens (403 Forbidden)

### Cookie Settings

**Session cookie:**
- `Domain=.orcazap.com` (cross-subdomain access)
- `HttpOnly=true` (not accessible via JavaScript)
- `Secure=true` (HTTPS only in production)
- `SameSite=Lax` (CSRF protection)

**CSRF token cookie:**
- Same settings as session cookie
- Used for form submissions

## Webhook Security

### Verification Token

**WhatsApp webhook verification:**
- Meta sends GET request with `hub.verify_token`
- Server validates token matches `WHATSAPP_VERIFY_TOKEN` env var
- Returns `hub.challenge` if valid, 403 if invalid
- Endpoint: `GET /webhooks/whatsapp` (API host only)

**Implementation:**
- Verify token stored in environment variable
- Never logged or exposed in responses
- Required for webhook subscription

### Signature Verification

**Status:** Not implemented (optional enhancement)

**Conceptual design:**
- Meta can send `X-Hub-Signature-256` header (SHA256 HMAC)
- Compute HMAC-SHA256 of request body using `WHATSAPP_APP_SECRET`
- Compare signatures using constant-time comparison
- Reject if signature invalid (401 Unauthorized)

**Note:** For MVP, verify token is sufficient. Signature verification can be added for additional security.

### Host Restriction

**Webhook endpoints only accessible on API host:**
- `api.orcazap.com` → webhook accessible
- `{slug}.orcazap.com` → 404 (webhook not found)
- `orcazap.com` → 404 (webhook not found)

**Implementation:**
- Middleware checks `request.state.host_context == HostContext.API`
- Returns 404 if not API host

## Rate Limiting

### Implementation

**Technology:** slowapi (Redis-backed)

**Rate limit keys:**
- Per tenant: `tenant:{tenant_id}` (for tenant hosts)
- Per IP: `{ip_address}` (for public/API hosts)

**Limits:**
- Webhook endpoints: 1000/hour
- API endpoints: 100/hour
- Tenant dashboard: 200/hour
- Default: 1000/hour (if not specified)

**Storage:**
- Redis: `slowapi:rate_limit:{key}:{window}`
- Sliding window algorithm
- Automatic expiry

### Rate Limit Headers

**Response headers:**
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Remaining requests in window
- `X-RateLimit-Reset`: Unix timestamp when window resets

**Rate limit exceeded:**
- Returns 429 Too Many Requests
- Logs warning with rate limit key
- Client should back off and retry

## Idempotency

### Webhook Idempotency

**Key:** `provider_message_id` (from WhatsApp)

**Implementation:**
- Unique constraint on `messages.provider_message_id`
- Check before insert: if exists, skip processing (idempotent)
- Log idempotency hits for monitoring

**Benefits:**
- Prevents duplicate message processing
- Safe to retry webhook (WhatsApp may send duplicates)
- Idempotent response (200 OK even if already processed)

### Worker Idempotency

**Key:** `message.conversation_id` (set after processing)

**Implementation:**
- Worker checks if `message.conversation_id` is set
- If set, skip processing (already processed)
- If not set, process and set `conversation_id`

**Benefits:**
- Prevents duplicate job processing
- Safe to retry failed jobs
- Idempotent job execution

## Input Validation

### Pydantic Models

**All inputs validated with Pydantic:**
- Request bodies (webhooks, API endpoints)
- Query parameters
- Path parameters
- Form data

**Validation:**
- Type checking
- Required fields
- String length limits
- Enum validation
- Custom validators

### SQL Injection Prevention

**SQLAlchemy ORM:**
- All queries use ORM (no raw SQL)
- Parameterized queries (automatic)
- No string concatenation in queries

**Example:**
```python
# ✅ Safe (ORM)
db.query(Contact).filter_by(tenant_id=tenant_id, phone=phone).first()

# ❌ Never do this
db.execute(f"SELECT * FROM contacts WHERE phone = '{phone}'")
```

### XSS Prevention

**Jinja2 autoescape:**
- All templates use Jinja2 autoescape
- User input automatically escaped in templates
- No `|safe` filter on user input

**HTMX:**
- Server-rendered HTML (no client-side template rendering)
- XSS risk minimized

## Logging Security

### Never Log Secrets

**Prohibited:**
- Passwords (hashed or plain)
- Access tokens
- API keys
- Session IDs (log session_id hash if needed)
- CSRF tokens

**Allowed:**
- Request IDs (for tracing)
- Tenant IDs (for debugging)
- User IDs (for audit)
- Provider message IDs (for tracing)

### Structured Logging

**Log format:**
- JSON in production (structured)
- Human-readable in development
- Request ID in every log entry
- Tenant ID in tenant-scoped logs

**Log levels:**
- DEBUG: Detailed debugging info
- INFO: Normal operations
- WARNING: Recoverable errors
- ERROR: Unrecoverable errors

## Infrastructure Security

### Network Security

**Firewall rules (ufw):**
- Only necessary ports open (22, 80, 443, 51820)
- Database/Redis only accessible via WireGuard VPN
- No public access to database/Redis

**WireGuard VPN:**
- Private network: `10.10.0.0/24`
- Encrypted communication between servers
- No public IPs for internal services

### Service Security

**Systemd services:**
- Run as non-root user (`orcazap`)
- Limited file permissions
- No sudo access

**Database:**
- Strong passwords (generated, not hardcoded)
- Connection pooling (PgBouncer)
- No public access

**Redis:**
- Password protected (`requirepass`)
- No public access
- Bind to WireGuard interface only

## Security Checklist

### Development
- [ ] All queries include `tenant_id` filter
- [ ] CSRF tokens on all POST/PUT/DELETE
- [ ] Input validation with Pydantic
- [ ] No secrets in code or logs
- [ ] Password hashing (bcrypt, 12 rounds)

### Production
- [ ] HTTPS enabled (TLS 1.2+)
- [ ] Secure cookies (HttpOnly, Secure, SameSite)
- [ ] Rate limiting enabled
- [ ] Firewall rules configured
- [ ] Database backups encrypted
- [ ] Environment variables secured
- [ ] Webhook verify token set
- [ ] Operator accounts with strong passwords

## Incident Response

**If security issue discovered:**
1. Assess impact (tenant isolation breach, data leak, etc.)
2. Contain issue (disable affected endpoints, revoke tokens)
3. Notify affected tenants (if applicable)
4. Fix issue and deploy
5. Review logs for unauthorized access
6. Rotate secrets if compromised

**Security contact:** [To be determined]




