"""Tenant router for {slug}.orcazap.com."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.stripe import is_subscription_active
from app.db.models import Approval, ApprovalStatus, Tenant, User
from app.domain.metrics import get_tenant_metrics
from app.middleware.host_routing import HostContext

router = APIRouter()


def require_tenant_host(request: Request):
    """Dependency to ensure request is on tenant host with valid tenant."""
    if request.state.host_context != HostContext.TENANT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This route is only available on tenant subdomains",
        )
    if not request.state.tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Tenant dashboard with metrics."""
    tenant = request.state.tenant
    
    # Check authentication - if not authenticated, redirect to login
    try:
        user = get_current_user(request, db)
        user_email = user.email
    except HTTPException:
        # Not authenticated, redirect to public login
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/",
            status_code=status.HTTP_302_FOUND,
        )

    # Get metrics
    metrics = get_tenant_metrics(db, tenant.id)

    # Get pending approvals count
    pending_approvals = (
        db.query(Approval)
        .filter_by(tenant_id=tenant.id, status=ApprovalStatus.PENDING)
        .count()
    )

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{ color: #007bff; }}
                .metrics {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }}
                .metric-card {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    border: 1px solid #dee2e6;
                }}
                .metric-value {{
                    font-size: 2em;
                    font-weight: bold;
                    color: #007bff;
                }}
                .metric-label {{
                    color: #6c757d;
                    margin-top: 5px;
                }}
                nav {{
                    margin: 20px 0;
                    padding: 10px 0;
                    border-bottom: 1px solid #dee2e6;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
                nav a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <h1>Dashboard - {tenant.name}</h1>
            <p>Logado como: {user_email}</p>
            
            <nav>
                <a href="/">Dashboard</a>
                <a href="/approvals">Aprovações</a>
                <a href="/prices">Preços</a>
                <a href="/freight">Frete</a>
                <a href="/rules">Regras</a>
            </nav>

            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{metrics['quotes_7d']}</div>
                    <div class="metric-label">Orçamentos (7 dias)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['quotes_30d']}</div>
                    <div class="metric-label">Orçamentos (30 dias)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['approvals_pending']}</div>
                    <div class="metric-label">Aprovações Pendentes</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{metrics['messages_processed']}</div>
                    <div class="metric-label">Mensagens Processadas</div>
                </div>
            </div>
            
            {f'<div style="background: #fff3cd; border: 1px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px;"><strong>⚠️ Assinatura Inativa:</strong> Ative sua assinatura para usar o WhatsApp. <a href="https://orcazap.com/pricing">Ver planos</a></div>' if not is_subscription_active(tenant) else ''}
        </body>
        </html>
        """
    )


@router.get("/approvals", response_class=HTMLResponse)
async def approvals_list(
    request: Request,
    _=Depends(require_tenant_host),
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Approvals queue (HTMX)."""
    tenant = request.state.tenant
    
    # Check authentication
    try:
        user = get_current_user(request, db)
    except HTTPException:
        slug = tenant.slug
        return RedirectResponse(
            url=f"https://orcazap.com/login?tenant={slug}&next=/approvals",
            status_code=status.HTTP_302_FOUND,
        )

    # Get pending approvals
    approvals = (
        db.query(Approval)
        .filter_by(tenant_id=tenant.id, status=ApprovalStatus.PENDING)
        .all()
    )

    # Simple placeholder for now - full HTMX implementation in Phase 2 completion
    approvals_html = ""
    for approval in approvals:
        approvals_html += f"<p>Aprovação ID: {approval.id} - Status: {approval.status}</p>"

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Aprovações - {tenant.name}</title>
            <meta charset="utf-8">
            <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        </head>
        <body>
            <h1>Aprovações Pendentes</h1>
            {approvals_html if approvals_html else "<p>Nenhuma aprovação pendente.</p>"}
            <p><a href="/">Voltar ao Dashboard</a></p>
        </body>
        </html>
        """
    )

