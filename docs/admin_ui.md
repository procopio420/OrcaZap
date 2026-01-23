# Admin Panel (HTMX)

## Overview

The admin panel is server-rendered using HTMX for dynamic interactions. All routes are under `/admin` and require authentication.

## Authentication

### `/admin/login`
- GET: Show login form
- POST: Authenticate user, set session, redirect to `/admin`

**Session Management:**
- Use secure cookies
- Session expires after 24h of inactivity
- CSRF protection on POST requests

## Routes

### `/admin` (Home)
Dashboard with:
- Pending approvals count
- Recent quotes
- Active conversations count
- Quick stats (quotes sent today, conversion rate)

**HTMX:** None (static page)

### `/admin/approvals`
List of pending approvals with filters:
- Status: pending / approved / rejected
- Date range
- Tenant (if multi-tenant admin)

**Table Columns:**
- Quote ID
- Contact phone
- Total amount
- Reason for approval
- Created at
- Actions (Approve / Reject buttons)

**HTMX Behaviors:**
- Approve button: POST to `/admin/approvals/{id}/approve`, swap row with success message
- Reject button: POST to `/admin/approvals/{id}/reject`, swap row with rejection message
- Filter form: GET with query params, swap table body

### `/admin/prices`
Search and edit prices for tenant items.

**Features:**
- Search by SKU or item name
- Inline edit: Click price, edit in place, save
- Bulk update modal: Select multiple items, set new price

**HTMX Behaviors:**
- Inline edit: PUT to `/admin/prices/{id}`, swap cell with updated value
- Bulk update: POST to `/admin/prices/bulk`, swap table with updated rows
- Search: GET with query, swap table body

### `/admin/freight`
Manage freight rules by bairro or CEP range.

**Features:**
- List all freight rules
- Add new rule (form modal)
- Edit rule (inline or modal)
- Delete rule (with confirmation)

**HTMX Behaviors:**
- Add rule: POST to `/admin/freight`, append new row to table
- Edit rule: PUT to `/admin/freight/{id}`, swap row
- Delete rule: DELETE to `/admin/freight/{id}`, remove row

### `/admin/rules`
Manage pricing rules (PIX discount, margin thresholds, approval thresholds).

**Features:**
- Edit tenant pricing rules (single form)
- Save updates

**HTMX Behaviors:**
- Save: POST to `/admin/rules`, swap form with success message

### `/admin/audit`
View audit log with filters:
- Entity type
- Action
- Date range
- User

**Features:**
- Paginated table
- View before/after JSON in modal

**HTMX Behaviors:**
- Filter: GET with query params, swap table body
- Pagination: GET with page param, swap table body
- View details: GET to `/admin/audit/{id}/details`, show modal

## HTMX Patterns

### Inline Edit
```html
<td hx-get="/admin/prices/123/edit" hx-target="this" hx-swap="outerHTML">
  R$ 45.00
</td>
```

### Partial Swap
All HTMX endpoints return HTML partials, not full pages:
- Table rows: Return `<tr>...</tr>`
- Table body: Return `<tbody>...</tbody>`
- Forms: Return form HTML

### Error Handling
- On error, swap target with error message
- Use `hx-swap-oob="true"` for notifications

## Templates

Use Jinja2 templates in `app/admin/templates/`:
- `base.html`: Base layout with navigation
- `approvals/list.html`: Approvals list
- `prices/list.html`: Prices list with inline edit
- `freight/list.html`: Freight rules list
- `rules/edit.html`: Pricing rules form
- `audit/list.html`: Audit log table

## Testing

### HTMX Endpoint Tests
- Test that endpoints return HTML partials (not full pages)
- Test swap behavior (snapshot HTML)
- Test error cases (return error partial)

### Integration Tests
- Test full flows: login -> navigate -> approve -> verify state
- Use test client with cookie handling

## Security

- All routes require authentication
- CSRF tokens on state-changing requests
- Tenant isolation: Users can only access their tenant's data
- Input validation and sanitization


