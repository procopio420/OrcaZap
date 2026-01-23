"""Operator admin router for api.orcazap.com/admin."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.operator_auth import require_operator_auth
from app.db.models import Approval, ApprovalStatus, Message, Quote, Tenant

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
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_operator_auth),
):
    """Recent webhook events and errors (placeholder)."""
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Logs - Operator Admin</title>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                nav a {
                    margin-right: 20px;
                    color: #007bff;
                    text-decoration: none;
                }
            </style>
        </head>
        <body>
            <h1>Webhook Logs</h1>
            <nav>
                <a href="/admin">Dashboard</a>
                <a href="/admin/tenants">Tenants</a>
                <a href="/admin/logs">Logs</a>
            </nav>
            <p>Webhook logs and error tracking will be implemented here.</p>
            <p>This will show recent webhook events, failures, and system errors.</p>
        </body>
        </html>
        """
    )


