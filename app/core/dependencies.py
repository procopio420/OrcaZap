"""FastAPI dependencies for authentication and tenant access."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.sessions import get_session
from app.db.base import SessionLocal
from app.db.models import Tenant, User


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Get current authenticated user from session (works across subdomains).

    Returns:
        User object

    Raises:
        HTTPException: If not authenticated
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    try:
        user_id = UUID(session_data["user_id"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_tenant(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Tenant:
    """Get current tenant from request state (set by middleware).

    Returns:
        Tenant object

    Raises:
        HTTPException: If tenant not found in request state
    """
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


def require_tenant(request: Request) -> Tenant:
    """Dependency to require tenant host with valid tenant."""
    from app.middleware.host_routing import HostContext

    if request.state.host_context != HostContext.TENANT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This route is only available on tenant subdomains",
        )

    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant





