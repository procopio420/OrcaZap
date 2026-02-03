"""Monitoring and metrics endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.middleware.host_routing import HostContext

router = APIRouter()


def require_api_host(request: Request):
    """Dependency to ensure request is on API host."""
    if request.state.host_context != HostContext.API:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metrics endpoint only available on API host",
        )


@router.get("/metrics")
async def metrics(
    request: Request,
    _=Depends(require_api_host),
) -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/health")
async def health():
    """Health check endpoint - returns 200 if service is up."""
    return {"status": "healthy"}


@router.get("/ready")
async def ready(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _=Depends(require_api_host),
):
    """Readiness check endpoint - returns 200 if service is ready to serve traffic.
    
    Checks:
    - Database connectivity
    - Database can execute queries
    """
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        return {"status": "ready", "checks": {"database": "ok"}}
    except Exception as e:
        return Response(
            content=f'{{"status": "not_ready", "error": "{str(e)}"}}',
            status_code=503,
            media_type="application/json",
        )

