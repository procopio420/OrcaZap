"""Operator authentication for internal admin."""

import base64
import os
from typing import Optional

from fastapi import HTTPException, Request, status

# Operator credentials from environment
OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "")
OPERATOR_PASSWORD = os.getenv("OPERATOR_PASSWORD", "")


def verify_operator_auth(request: Request) -> bool:
    """Verify operator Basic Auth credentials.

    Args:
        request: FastAPI request

    Returns:
        True if authenticated, False otherwise

    Raises:
        HTTPException: If credentials are invalid
    """
    if not OPERATOR_USERNAME or not OPERATOR_PASSWORD:
        # If credentials not set, allow access in development
        # In production, this should be required
        return True

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    try:
        encoded = auth_header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)

        if username == OPERATOR_USERNAME and password == OPERATOR_PASSWORD:
            return True
    except (ValueError, IndexError):
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_operator_auth(request: Request):
    """Dependency to require operator authentication."""
    from app.middleware.host_routing import HostContext

    # Must be on API host
    if request.state.host_context != HostContext.API:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Operator admin only available on API host",
        )

    verify_operator_auth(request)
    return True





