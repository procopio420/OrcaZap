"""Admin panel routes."""

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
from sqlalchemy.orm import Session

from app.admin.auth import authenticate_user, create_session, delete_session, get_current_user, get_db
from app.adapters.whatsapp.sender import send_text_message
from app.db.models import (
    Approval,
    ApprovalStatus,
    Channel,
    Contact,
    Conversation,
    ConversationState,
    Message,
    MessageDirection,
    Quote,
    QuoteStatus,
    User,
)
from app.domain.messages import format_quote_message
from app.domain.state_machine import Event, transition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# Simple template rendering (for MVP)
# In production, use proper Jinja2 environment with file templates
def render_template(template_name: str, context: dict) -> str:
    """Render a template (simplified for MVP)."""
    # For MVP, we'll use simple string templates
    # In production, load from files
    templates = {
        "login.html": """
<!DOCTYPE html>
<html>
<head>
    <title>OrcaZap Admin - Login</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 400px; margin: 50px auto; }
        form { display: flex; flex-direction: column; gap: 10px; }
        input { padding: 8px; }
        button { padding: 10px; background: #007bff; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <h1>OrcaZap Admin</h1>
    <h2>Login</h2>
    <form method="POST" action="/admin/login">
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
    {% if error %}
    <p style="color: red;">{{ error }}</p>
    {% endif %}
</body>
</html>
""",
        "approvals.html": """
<!DOCTYPE html>
<html>
<head>
    <title>OrcaZap Admin - Approvals</title>
    <meta charset="utf-8">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 20px auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border: 1px solid #ddd; }
        th { background: #f4f4f4; }
        button { padding: 5px 10px; margin: 2px; cursor: pointer; }
        .approve { background: #28a745; color: white; border: none; }
        .reject { background: #dc3545; color: white; border: none; }
    </style>
</head>
<body>
    <h1>OrcaZap Admin - Pending Approvals</h1>
    <table>
        <thead>
            <tr>
                <th>Quote ID</th>
                <th>Contact</th>
                <th>Total</th>
                <th>Reason</th>
                <th>Created</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody id="approvals-body">
            {% for approval in approvals %}
            <tr id="approval-{{ approval.id }}">
                <td>{{ approval.quote_id }}</td>
                <td>{{ approval.contact_phone }}</td>
                <td>R$ {{ "%.2f"|format(approval.total) }}</td>
                <td>{{ approval.reason }}</td>
                <td>{{ approval.created_at.strftime("%Y-%m-%d %H:%M") }}</td>
                <td>
                    <button class="approve" 
                            hx-post="/admin/approvals/{{ approval.id }}/approve"
                            hx-target="#approval-{{ approval.id }}"
                            hx-swap="outerHTML">Approve</button>
                    <button class="reject"
                            hx-post="/admin/approvals/{{ approval.id }}/reject"
                            hx-target="#approval-{{ approval.id }}"
                            hx-swap="outerHTML">Reject</button>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
""",
    }

    template_str = templates.get(template_name, "<p>Template not found</p>")
    template = Template(template_str)
    return template.render(**context)


@router.get("/login", response_class=HTMLResponse)
async def login_page() -> str:
    """Show login page."""
    return render_template("login.html", {})


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Annotated[Session, Depends(get_db)] = None,
) -> RedirectResponse:
    """Handle login."""
    # For MVP, assume single tenant (tenant_id from first tenant)
    # In production, tenant selection would be part of login
    from app.db.models import Tenant

    tenant = db.query(Tenant).first()
    if not tenant:
        return HTMLResponse(
            render_template("login.html", {"error": "No tenant configured"}),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate_user(db, email, password, tenant.id)
    if not user:
        return HTMLResponse(
            render_template("login.html", {"error": "Invalid email or password"}),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    session_id = create_session(user.id)
    response = RedirectResponse(url="/admin/approvals", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="admin_session_id",
        value=session_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=86400,  # 24 hours
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> RedirectResponse:
    """Logout and invalidate session."""
    session_id = request.cookies.get("admin_session_id")
    if session_id:
        # Remove session from storage
        delete_session(session_id)

    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="admin_session_id")
    return response


@router.get("/approvals", response_class=HTMLResponse)
async def approvals_list(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> str:
    """List pending approvals."""
    # Get pending approvals for user's tenant
    approvals = (
        db.query(Approval)
        .filter_by(tenant_id=user.tenant_id, status=ApprovalStatus.PENDING)
        .order_by(Approval.created_at.desc())
        .all()
    )

    # Enrich with quote and contact info
    approvals_data = []
    for approval in approvals:
        quote = db.query(Quote).filter_by(id=approval.quote_id).first()
        if not quote:
            continue

        conversation = (
            db.query(Conversation).filter_by(id=quote.conversation_id).first()
        )
        contact = None
        if conversation:
            contact = db.query(Contact).filter_by(id=conversation.contact_id).first()

        approvals_data.append({
            "id": str(approval.id),
            "quote_id": str(quote.id),
            "contact_phone": contact.phone if contact else "Unknown",
            "total": float(quote.total),
            "reason": approval.reason or "N/A",
            "created_at": approval.created_at,
        })

    return render_template("approvals.html", {"approvals": approvals_data})


@router.post("/approvals/{approval_id}/approve", response_class=HTMLResponse)
async def approve_quote(
    request: Request,
    approval_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> str:
    """Approve a quote and send it."""
    # Validate UUID format
    try:
        approval_uuid = UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    approval = db.query(Approval).filter_by(id=approval_uuid, tenant_id=user.tenant_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != ApprovalStatus.PENDING:
        return f'<tr><td colspan="6">Approval already {approval.status}</td></tr>'

    quote = db.query(Quote).filter_by(id=approval.quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    conversation = db.query(Conversation).filter_by(id=quote.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    contact = db.query(Contact).filter_by(id=conversation.contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    channel = db.query(Channel).filter_by(id=conversation.channel_id, tenant_id=user.tenant_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        # Format quote message first (before any DB changes)
        payload = quote.payload_json
        discount_amount = quote.subtotal * quote.discount_pct

        quote_text = format_quote_message(
            items=quote.items_json,
            subtotal=float(quote.subtotal),
            freight=float(quote.freight),
            discount_pct=float(quote.discount_pct),
            discount_amount=float(discount_amount),
            total=float(quote.total),
            payment_method=payload.get("payment_method", "N/A"),
            delivery_day=payload.get("delivery_day", "N/A"),
            valid_until=quote.valid_until,
        )

        # Send message BEFORE any DB changes
        try:
            provider_msg_id = send_text_message(
                channel=channel,
                to_phone=contact.phone,
                message_text=quote_text,
            )
        except Exception as send_error:
            logger.error(
                f"Failed to send quote message: {send_error}",
                extra={"approval_id": str(approval.id), "quote_id": str(quote.id), "user_id": str(user.id)},
                exc_info=True,
            )
            raise HTTPException(status_code=500, detail=f"Failed to send quote: {send_error}")

        if not provider_msg_id:
            logger.warning(
                f"Quote message send returned None",
                extra={"approval_id": str(approval.id), "quote_id": str(quote.id)},
            )
            raise HTTPException(status_code=500, detail="Failed to send quote message (returned None)")

        # Only update DB if message was sent successfully
        # Update approval
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by_user_id = user.id
        approval.approved_at = datetime.now(timezone.utc)

        # Transition conversation state
        new_state = transition(conversation.state, Event.ADMIN_APPROVED)
        conversation.state = new_state

        # Save quote message
        quote_message = Message(
            tenant_id=user.tenant_id,
            conversation_id=conversation.id,
            provider_message_id=provider_msg_id,
            direction=MessageDirection.OUTBOUND,
            message_type="text",
            raw_payload={"text": {"body": quote_text}},
            text_content=quote_text,
        )
        db.add(quote_message)

        # Update quote status
        quote.status = QuoteStatus.SENT

        # Update window expiration
        from datetime import timedelta
        conversation.window_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        # Create audit log entry
        from app.db.models import AuditLog
        audit_log = AuditLog(
            tenant_id=user.tenant_id,
            entity_type="approval",
            entity_id=approval.id,
            action="approve",
            user_id=user.id,
            after_json={"status": "approved", "quote_id": str(quote.id)},
        )
        db.add(audit_log)

        # Commit everything
        db.commit()

        logger.info(
            f"Quote {quote.id} approved and sent by user {user.id}",
            extra={"approval_id": str(approval.id), "quote_id": str(quote.id), "user_id": str(user.id)},
        )

        return f'<tr><td colspan="6" style="background: #d4edda;">Quote {quote.id} approved and sent</td></tr>'

    except Exception as e:
        db.rollback()
        logger.error(f"Error approving quote: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error approving quote: {e}")


@router.post("/approvals/{approval_id}/reject", response_class=HTMLResponse)
async def reject_quote(
    request: Request,
    approval_id: str,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> str:
    """Reject a quote."""
    # Validate UUID format
    try:
        approval_uuid = UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    approval = db.query(Approval).filter_by(id=approval_uuid, tenant_id=user.tenant_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != ApprovalStatus.PENDING:
        return f'<tr><td colspan="6">Approval already {approval.status}</td></tr>'

    quote = db.query(Quote).filter_by(id=approval.quote_id).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    conversation = db.query(Conversation).filter_by(id=quote.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        # Update approval
        approval.status = ApprovalStatus.REJECTED
        approval.approved_by_user_id = user.id
        approval.approved_at = datetime.now(timezone.utc)

        # Transition conversation to LOST
        new_state = transition(conversation.state, Event.ADMIN_REJECTED)
        conversation.state = new_state

        # Update quote status
        quote.status = QuoteStatus.LOST

        # Create audit log entry
        from app.db.models import AuditLog
        audit_log = AuditLog(
            tenant_id=user.tenant_id,
            entity_type="approval",
            entity_id=approval.id,
            action="reject",
            user_id=user.id,
            after_json={"status": "rejected", "quote_id": str(quote.id)},
        )
        db.add(audit_log)

        db.commit()

        logger.info(
            f"Quote {quote.id} rejected by user {user.id}",
            extra={"approval_id": str(approval.id), "quote_id": str(quote.id), "user_id": str(user.id)},
        )

        return f'<tr><td colspan="6" style="background: #f8d7da;">Quote {quote.id} rejected</td></tr>'

    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting quote: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error rejecting quote: {e}")

