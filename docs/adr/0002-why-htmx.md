# ADR 0002: Why HTMX for Admin Panel

**Status:** Accepted  
**Date:** 2024-12  
**Deciders:** Platform Engineering Team

## Context

OrcaZap needs an admin panel for:
- Quote approvals (view pending quotes, approve/reject)
- Price management (view/edit item prices)
- Freight rule management (view/edit freight rules)
- Dashboard with stats (quotes, conversions, etc.)

We need a frontend technology that:
- Is fast to develop and maintain
- Works well for admin/internal tools (not customer-facing)
- Integrates with FastAPI server-side rendering
- Has minimal JavaScript complexity
- Is easy to deploy (no separate build step)

## Decision

We will use **HTMX** with **Jinja2 templates** for the admin panel.

## Decision Drivers

- **Fast development**: No build step, no JS framework complexity
- **Minimal JavaScript**: HTMX handles AJAX via HTML attributes
- **Server-side rendering**: Templates rendered on server, SEO-friendly (not needed but nice)
- **Simple deployment**: No separate frontend build process
- **Progressive enhancement**: Works without JS, enhanced with HTMX

## Considered Options

### Option 1: HTMX + Jinja2 ✅

**Pros:**
- No build step (just templates)
- Minimal JavaScript (HTMX library only)
- Server-side rendering (fast, SEO-friendly)
- Simple deployment (no webpack/vite/etc.)
- Fast development (just write HTML templates)
- Works without JS (progressive enhancement)

**Cons:**
- Less interactive than SPA (acceptable for admin panel)
- Server round-trip for every interaction (acceptable for admin workloads)
- Limited client-side state management (not needed for admin panel)

**Implementation:**
- Jinja2 templates in `app/admin/templates/`
- HTMX attributes for AJAX interactions
- FastAPI route handlers return HTML responses

### Option 2: React + Vite

**Pros:**
- Rich interactivity
- Client-side routing
- Component reusability
- Large ecosystem

**Cons:**
- Build step required (webpack/vite)
- More complex deployment (separate frontend build)
- More JavaScript complexity
- Overkill for admin panel needs

**Why not chosen:** Too complex for admin panel, unnecessary overhead.

### Option 3: Vue.js

**Pros:**
- Simpler than React
- Good documentation

**Cons:**
- Still requires build step
- More complex than HTMX
- Overkill for admin panel

**Why not chosen:** Still more complex than needed.

### Option 4: Plain HTML + Vanilla JS

**Pros:**
- No dependencies
- Simple

**Cons:**
- More manual AJAX handling
- More boilerplate code
- Less declarative

**Why not chosen:** HTMX provides better developer experience with minimal overhead.

## Consequences

### Positive

- **Fast development**: Admin panel built quickly with templates
- **Simple deployment**: No frontend build process, just serve templates
- **Easy maintenance**: Templates are easy to understand and modify
- **Low complexity**: Minimal JavaScript, server-side logic
- **Good enough UX**: Admin panel doesn't need SPA-level interactivity

### Negative

- **Less interactive**: Can't do complex client-side interactions (acceptable for admin)
- **Server round-trips**: Every interaction requires server request (acceptable for admin workloads)
- **Limited offline**: No offline capability (acceptable for admin panel)

### Neutral

- **SEO**: Not needed for admin panel, but server-side rendering is still nice
- **Initial load**: Full page loads (acceptable for admin panel)

## Implementation Notes

- HTMX library loaded from CDN (or bundled if needed)
- Jinja2 templates with HTMX attributes (`hx-get`, `hx-post`, `hx-swap`, etc.)
- CSRF tokens included in HTMX requests (`X-CSRF-Token` header)
- Server returns HTML fragments for HTMX swaps

## Example Usage

```html
<!-- Template: app/admin/templates/approvals.html -->
<div hx-get="/admin/approvals" hx-trigger="load">
  <!-- Approval list -->
</div>

<button hx-post="/admin/approvals/{{ approval.id }}/approve"
        hx-target="#approval-{{ approval.id }}"
        hx-swap="outerHTML">
  Approve
</button>
```

## Future Considerations

- **SPA migration**: If admin panel needs more interactivity, can migrate to React/Vue later
- **Component library**: Can add HTMX component patterns for reusability
- **Real-time updates**: Can add Server-Sent Events (SSE) or WebSockets if needed

## References

- [HTMX Documentation](https://htmx.org/)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)




