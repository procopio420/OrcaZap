"""Operator admin router for api.orcazap.com/admin."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.operator_auth import require_operator_auth
from app.db.models import Approval, ApprovalStatus, AuditLog, Message, Quote, Tenant
from sqlalchemy import desc

router = APIRouter(prefix="/admin", tags=["operator"])


@router.get("", response_class=HTMLResponse)
async def operator_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_operator_auth),
):
    """Operator dashboard with system health and metrics."""
    # System metrics
    total_tenants = db.query(func.count(Tenant.id)).scalar() or 0
    total_quotes = db.query(func.count(Quote.id)).scalar() or 0
    pending_approvals = (
        db.query(func.count(Approval.id))
        .filter(Approval.status == ApprovalStatus.PENDING)
        .scalar()
        or 0
    )
    total_messages = db.query(func.count(Message.id)).scalar() or 0

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Operator Admin - OrcaZap</title>
            <meta charset="utf-8">
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
            <h1>Operator Admin Dashboard</h1>
            
            <nav>
                <a href="/admin">Dashboard</a>
                <a href="/admin/tenants">Tenants</a>
                <a href="/admin/logs">Logs</a>
            </nav>

            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{total_tenants}</div>
                    <div class="metric-label">Total Tenants</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{total_quotes}</div>
                    <div class="metric-label">Total Quotes</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{pending_approvals}</div>
                    <div class="metric-label">Pending Approvals</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{total_messages}</div>
                    <div class="metric-label">Total Messages</div>
                </div>
            </div>
        </body>
        </html>
        """
    )


@router.get("/tenants", response_class=HTMLResponse)
async def operator_tenants(
    request: Request,
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_operator_auth),
):
    """List all tenants with status."""
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()

    tenants_html = ""
    for tenant in tenants:
        status = "Active" if tenant.onboarding_completed_at else "Onboarding"
        tenants_html += f"""
        <tr>
            <td>{tenant.name}</td>
            <td>{tenant.slug or "N/A"}</td>
            <td>{status}</td>
            <td>{tenant.onboarding_step or "N/A"}</td>
            <td>{tenant.created_at.strftime("%Y-%m-%d %H:%M") if tenant.created_at else "N/A"}</td>
        </tr>
        """

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Tenants - Operator Admin</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                nav a {{
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <h1>Tenants</h1>
            <nav>
                <a href="/admin">Dashboard</a>
                <a href="/admin/tenants">Tenants</a>
                <a href="/admin/logs">Logs</a>
            </nav>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Slug</th>
                        <th>Status</th>
                        <th>Onboarding Step</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
                    {tenants_html if tenants_html else "<tr><td colspan='5'>No tenants found</td></tr>"}
                </tbody>
            </table>
        </body>
        </html>
        """
    )


@router.get("/logs", response_class=HTMLResponse)
async def operator_logs(
    request: Request,
    tenant_id: str | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_operator_auth),
):
    """View logs with tenant filtering."""
    # Get filter
    tenant_filter = request.query_params.get("tenant_id", tenant_id)
    
    # Get all tenants for filter dropdown
    all_tenants = db.query(Tenant).order_by(Tenant.name).all()
    
    # Get audit logs
    query = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(100)
    
    if tenant_filter:
        try:
            from uuid import UUID
            tenant_uuid = UUID(tenant_filter)
            query = query.filter_by(tenant_id=tenant_uuid)
            selected_tenant = db.query(Tenant).filter_by(id=tenant_uuid).first()
            filter_label = selected_tenant.name if selected_tenant else f"Tenant {tenant_filter}"
        except ValueError:
            filter_label = "Invalid tenant ID"
    else:
        filter_label = "Todos os tenants"
    
    logs = query.all()
    
    # Get recent messages (for webhook tracking)
    messages_query = db.query(Message).order_by(desc(Message.created_at)).limit(50)
    if tenant_filter:
        try:
            from uuid import UUID
            tenant_uuid = UUID(tenant_filter)
            messages_query = messages_query.filter_by(tenant_id=tenant_uuid)
        except ValueError:
            pass
    recent_messages = messages_query.all()
    
    logs_html = ""
    for log in logs:
        tenant = db.query(Tenant).filter_by(id=log.tenant_id).first()
        tenant_name = tenant.name if tenant else "Unknown"
        logs_html += f"""
        <tr>
            <td>{tenant_name}</td>
            <td>{log.entity_type}</td>
            <td>{log.action}</td>
            <td>{log.created_at.strftime('%d/%m/%Y %H:%M:%S') if log.created_at else 'N/A'}</td>
        </tr>
        """
    
    messages_html = ""
    for msg in recent_messages:
        tenant = db.query(Tenant).filter_by(id=msg.tenant_id).first()
        tenant_name = tenant.name if tenant else "Unknown"
        direction_badge = '<span style="background: #17a2b8; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Recebida</span>' if msg.direction.value == "inbound" else '<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">Enviada</span>'
        messages_html += f"""
        <tr>
            <td>{tenant_name}</td>
            <td>{direction_badge}</td>
            <td>{msg.provider_message_id[:20]}...</td>
            <td>{msg.text_content[:50] + '...' if msg.text_content and len(msg.text_content) > 50 else (msg.text_content or 'N/A')}</td>
            <td>{msg.created_at.strftime('%d/%m/%Y %H:%M:%S') if msg.created_at else 'N/A'}</td>
        </tr>
        """
    
    tenants_options = ""
    for tenant in all_tenants:
        selected = 'selected' if tenant_filter == str(tenant.id) else ''
        tenants_options += f'<option value="{tenant.id}" {selected}>{tenant.name}</option>'
    
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Logs - Operator Admin</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 20px;
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
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border: 1px solid #dee2e6;
                }}
                th {{
                    background: #f8f9fa;
                }}
                select {{
                    padding: 8px;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }}
                h2 {{
                    margin-top: 40px;
                }}
            </style>
        </head>
        <body>
            <h1>Logs do Sistema</h1>
            <nav>
                <a href="/admin">Dashboard</a>
                <a href="/admin/tenants">Tenants</a>
                <a href="/admin/logs">Logs</a>
            </nav>
            
            <div style="margin: 20px 0;">
                <form method="GET" style="display: flex; gap: 10px; align-items: center;">
                    <label>
                        <strong>Filtrar por Tenant:</strong>
                        <select name="tenant_id" onchange="this.form.submit()">
                            <option value="">Todos</option>
                            {tenants_options}
                        </select>
                    </label>
                </form>
                <p><strong>Filtro ativo:</strong> {filter_label}</p>
            </div>
            
            <h2>Audit Logs (Últimas 100)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Tenant</th>
                        <th>Tipo</th>
                        <th>Ação</th>
                        <th>Data/Hora</th>
                    </tr>
                </thead>
                <tbody>
                    {logs_html if logs_html else "<tr><td colspan='4'>Nenhum log encontrado.</td></tr>"}
                </tbody>
            </table>
            
            <h2>Mensagens Recentes (Últimas 50)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Tenant</th>
                        <th>Direção</th>
                        <th>Message ID</th>
                        <th>Conteúdo</th>
                        <th>Data/Hora</th>
                    </tr>
                </thead>
                <tbody>
                    {messages_html if messages_html else "<tr><td colspan='5'>Nenhuma mensagem encontrada.</td></tr>"}
                </tbody>
            </table>
        </body>
        </html>
        """
    )




