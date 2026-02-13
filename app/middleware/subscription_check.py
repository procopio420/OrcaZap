"""Subscription status check middleware."""

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, RedirectResponse

from app.core.stripe import is_subscription_active
from app.middleware.host_routing import HostContext


class SubscriptionCheckMiddleware(BaseHTTPMiddleware):
    """Middleware to check subscription status and block access if inactive."""

    # Paths that don't require active subscription
    ALLOWED_PATHS = {
        "/",
        "/login",
        "/register",
        "/pricing",
        "/onboarding",
    }

    async def dispatch(self, request: Request, call_next):
        """Check subscription status before processing request."""
        # Only check for tenant hosts
        if hasattr(request.state, "host_context") and request.state.host_context == HostContext.TENANT:
            if hasattr(request.state, "tenant") and request.state.tenant:
                tenant = request.state.tenant
                
                # Check if path is allowed without subscription
                path = request.url.path
                if path not in self.ALLOWED_PATHS and not path.startswith("/onboarding"):
                    # Check subscription status
                    if not is_subscription_active(tenant):
                        # Block access to dashboard and other features
                        # But allow onboarding to complete
                        if path.startswith("/onboarding"):
                            return await call_next(request)
                        
                        # Return subscription required message
                        return HTMLResponse(
                            content=f"""
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <title>Assinatura Necessária - {tenant.name}</title>
                                <meta charset="utf-8">
                                <style>
                                    body {{
                                        font-family: Arial, sans-serif;
                                        max-width: 600px;
                                        margin: 50px auto;
                                        padding: 20px;
                                        text-align: center;
                                    }}
                                    .warning {{
                                        background: #fff3cd;
                                        border: 1px solid #ffc107;
                                        padding: 20px;
                                        border-radius: 8px;
                                        margin: 20px 0;
                                    }}
                                    a {{
                                        display: inline-block;
                                        margin-top: 20px;
                                        padding: 12px 24px;
                                        background: #007bff;
                                        color: white;
                                        text-decoration: none;
                                        border-radius: 5px;
                                    }}
                                </style>
                            </head>
                            <body>
                                <h1>Assinatura Necessária</h1>
                                <div class="warning">
                                    <strong>⚠️ Sua assinatura está inativa.</strong>
                                    <p>Para continuar usando o OrçaZap, é necessário ter uma assinatura ativa.</p>
                                    <p>Status atual: <strong>{tenant.subscription_status or 'Não configurado'}</strong></p>
                                </div>
                                <a href="https://orcazap.com/pricing">Ativar Assinatura</a>
                            </body>
                            </html>
                            """,
                            status_code=status.HTTP_403_FORBIDDEN,
                        )
        
        return await call_next(request)





