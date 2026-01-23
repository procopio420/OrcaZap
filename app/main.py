"""FastAPI application entry point."""

from fastapi import FastAPI

from app.middleware.host_routing import host_routing_middleware
from app.routers import api, public, tenant
from app.admin.routes import router as admin_router

app = FastAPI(
    title="OrcaZap",
    description="WhatsApp-first quoting assistant for Brazilian construction material stores",
    version="0.1.0",
)

# Add host routing middleware
app.middleware("http")(host_routing_middleware)

# Include routers
# Public router (orcazap.com, www.orcazap.com)
app.include_router(public.router)

# Tenant router ({slug}.orcazap.com)
app.include_router(tenant.router)

# API router (api.orcazap.com)
app.include_router(api.router)

# Legacy admin router (kept for backward compatibility)
# New operator admin is in app.routers.operator (on API host)
app.include_router(admin_router)

