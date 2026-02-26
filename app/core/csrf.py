"""CSRF protection utilities."""

import secrets
from typing import Optional

from fastapi import HTTPException, Request, status


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def get_csrf_token(request: Request) -> Optional[str]:
    """Get CSRF token from request (cookie or header)."""
    # Try header first (for API/HTMX requests)
    token = request.headers.get("X-CSRF-Token")
    if token:
        return token
    
    # Try cookie (for form submissions)
    token = request.cookies.get("csrf_token")
    return token


def validate_csrf_token(request: Request, token: Optional[str] = None) -> None:
    """Validate CSRF token.
    
    Args:
        request: FastAPI request
        token: Token from form/header (if None, will be extracted from request)
    
    Raises:
        HTTPException: If token is invalid or missing
    """
    # Get token from parameter or request
    if token is None:
        token = get_csrf_token(request)
    
    # Get stored token from session/cookie
    stored_token = request.cookies.get("csrf_token")
    
    if not token or not stored_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )
    
    if not secrets.compare_digest(token, stored_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token invalid",
        )


def require_csrf_token(request: Request, token: Optional[str] = None) -> None:
    """Dependency to require CSRF token on state-changing requests.
    
    Usage:
        @router.post("/endpoint")
        async def endpoint(
            request: Request,
            _: None = Depends(require_csrf_token),
            ...
        ):
            ...
    """
    validate_csrf_token(request, token)








