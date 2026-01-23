"""API router for api.orcazap.com."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.adapters.whatsapp.webhook import router as whatsapp_router
from app.core.dependencies import get_db
from app.core.stripe import process_stripe_webhook
from app.middleware.host_routing import HostContext
from app.routers.operator import router as operator_router

router = APIRouter()


def require_api_host(request: Request):
    """Dependency to ensure request is on API host."""
    if request.state.host_context != HostContext.API:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This route is only available on the API host",
        )


@router.get("/health")
async def health_check(request: Request, _=Depends(require_api_host)) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok", "service": "orcazap"})


# Include webhook router (with API host requirement)
# Note: Individual webhook routes should also check API host
router.include_router(whatsapp_router, prefix="/webhooks")

# Include operator admin router
router.include_router(operator_router)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)] = None,
    _=Depends(require_api_host),
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    result = process_stripe_webhook(payload, signature, db)

    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    return {"status": "ok"}

