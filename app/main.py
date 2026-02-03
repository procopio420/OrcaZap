"""FastAPI application entry point."""

from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.middleware.host_routing import host_routing_middleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.subscription_check import SubscriptionCheckMiddleware
from app.routers import api, monitoring, public, tenant
from app.admin.routes import router as admin_router
from slowapi.errors import RateLimitExceeded

# Setup structured logging
setup_logging()

app = FastAPI(
    title="OrcaZap",
    description="WhatsApp-first quoting assistant for Brazilian construction material stores",
    version="0.1.0",
)

# Add host routing middleware
app.middleware("http")(host_routing_middleware)

# Add subscription check middleware (after host routing to access tenant)
app.add_middleware(SubscriptionCheckMiddleware)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Include routers
# Public router (orcazap.com, www.orcazap.com)
app.include_router(public.router)

# Tenant router ({slug}.orcazap.com)
app.include_router(tenant.router)

# API router (api.orcazap.com)
app.include_router(api.router)

# Monitoring router (api.orcazap.com)
app.include_router(monitoring.router)

# Legacy admin router (kept for backward compatibility)
# New operator admin is in app.routers.operator (on API host)
app.include_router(admin_router)

