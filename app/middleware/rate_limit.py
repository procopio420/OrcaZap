"""Rate limiting middleware using slowapi."""

import logging
from typing import Callable

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.dependencies import get_db
from app.middleware.host_routing import HostContext
from app.settings import settings

logger = logging.getLogger(__name__)


def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key (tenant_id or IP address).
    
    Args:
        request: FastAPI request
    
    Returns:
        Rate limit key string
    """
    # Try to get tenant_id from request state (for tenant hosts)
    if hasattr(request.state, "tenant") and request.state.tenant:
        return f"tenant:{request.state.tenant.id}"
    
    # Fallback to IP address
    return get_remote_address(request)


# Initialize limiter with Redis backend
limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=settings.redis_url,
    default_limits=["1000/hour"],  # Default limit if not specified
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    logger.warning(
        f"Rate limit exceeded for {get_rate_limit_key(request)}",
        extra={"rate_limit_key": get_rate_limit_key(request)},
    )
    return _rate_limit_exceeded_handler(request, exc)


# Rate limit decorators for common endpoints
def webhook_rate_limit(func: Callable) -> Callable:
    """Rate limit for webhook endpoints (higher limit)."""
    return limiter.limit("1000/hour")(func)


def api_rate_limit(func: Callable) -> Callable:
    """Rate limit for API endpoints."""
    return limiter.limit("100/hour")(func)


def tenant_rate_limit(func: Callable) -> Callable:
    """Rate limit for tenant dashboard endpoints."""
    return limiter.limit("200/hour")(func)





