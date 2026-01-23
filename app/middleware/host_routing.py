"""Host-based routing middleware for multi-domain SaaS."""

import re
from enum import Enum
from typing import Optional

from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import Tenant


class HostContext(str, Enum):
    """Host context classification."""

    PUBLIC = "public"  # orcazap.com, www.orcazap.com
    API = "api"  # api.orcazap.com
    TENANT = "tenant"  # {slug}.orcazap.com


# Slug validation regex: lowercase, alphanumeric, hyphens only, 3-32 chars
SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")


def extract_slug(host: str) -> Optional[str]:
    """Extract tenant slug from host.

    Args:
        host: Host header value (e.g., "tenant1.orcazap.com")

    Returns:
        Slug if host matches tenant pattern, None otherwise
    """
    # Remove port if present
    host = host.split(":")[0]

    # Check if it's a tenant subdomain: {slug}.orcazap.com
    parts = host.split(".")
    if len(parts) >= 3:
        # Could be a tenant subdomain
        slug = parts[0]
        # Verify it's not a reserved subdomain
        if slug not in ("www", "api") and SLUG_PATTERN.match(slug):
            # Check if the rest matches orcazap.com
            domain = ".".join(parts[1:])
            if domain == "orcazap.com" or domain.endswith(".orcazap.com"):
                return slug

    return None


def classify_host(host: str) -> tuple[HostContext, Optional[str]]:
    """Classify host and extract tenant slug if applicable.

    Args:
        host: Host header value

    Returns:
        Tuple of (HostContext, slug or None)
    """
    # Remove port if present
    host = host.split(":")[0].lower()

    # API host
    if host == "api.orcazap.com":
        return (HostContext.API, None)

    # Public hosts
    if host in ("orcazap.com", "www.orcazap.com"):
        return (HostContext.PUBLIC, None)

    # Try to extract tenant slug
    slug = extract_slug(host)
    if slug:
        return (HostContext.TENANT, slug)

    # Default to public for unknown hosts (development)
    return (HostContext.PUBLIC, None)


async def host_routing_middleware(request: Request, call_next):
    """Middleware to classify host and resolve tenant.

    Sets:
        - request.state.host_context: HostContext enum
        - request.state.tenant_slug: str | None (for tenant hosts)
        - request.state.tenant: Tenant | None (for tenant hosts, resolved from DB)
    """
    host = request.headers.get("host", "")
    context, slug = classify_host(host)

    request.state.host_context = context
    request.state.tenant_slug = slug
    request.state.tenant = None

    # For tenant hosts, resolve tenant from DB
    if context == HostContext.TENANT and slug:
        db: Session = SessionLocal()
        try:
            tenant = db.query(Tenant).filter_by(slug=slug).first()
            if not tenant:
                # Tenant not found - return 404 with user-friendly message
                db.close()
                from fastapi.responses import HTMLResponse

                return HTMLResponse(
                    content=f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Loja não encontrada - OrcaZap</title>
                        <meta charset="utf-8">
                        <style>
                            body {{
                                font-family: Arial, sans-serif;
                                max-width: 600px;
                                margin: 50px auto;
                                padding: 20px;
                                text-align: center;
                            }}
                            h1 {{ color: #333; }}
                            p {{ color: #666; }}
                            a {{
                                display: inline-block;
                                margin-top: 20px;
                                padding: 10px 20px;
                                background: #007bff;
                                color: white;
                                text-decoration: none;
                                border-radius: 5px;
                            }}
                        </style>
                    </head>
                    <body>
                        <h1>Loja não encontrada</h1>
                        <p>A loja com o endereço <strong>{slug}.orcazap.com</strong> não foi encontrada.</p>
                        <p>Verifique o endereço ou entre em contato conosco.</p>
                        <a href="https://orcazap.com">Voltar para OrcaZap</a>
                    </body>
                    </html>
                    """,
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            request.state.tenant = tenant
        finally:
            db.close()

    response = await call_next(request)
    return response

