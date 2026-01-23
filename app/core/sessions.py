"""Redis-based session management for cross-subdomain authentication."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import redis

from app.settings import settings

# Redis client for sessions
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# Session key prefix
SESSION_PREFIX = "session:"
# Session TTL (7 days)
SESSION_TTL = 86400 * 7


def create_session(user_id: UUID, tenant_id: UUID) -> str:
    """Create a new session and return session ID.

    Args:
        user_id: User UUID
        tenant_id: Tenant UUID

    Returns:
        Session ID string
    """
    session_id = secrets.token_urlsafe(32)
    session_key = f"{SESSION_PREFIX}{session_id}"

    session_data = {
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    redis_client.setex(
        session_key,
        SESSION_TTL,
        json.dumps(session_data),
    )

    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """Get session data by session ID.

    Args:
        session_id: Session ID

    Returns:
        Session data dict or None if not found/expired
    """
    session_key = f"{SESSION_PREFIX}{session_id}"
    data = redis_client.get(session_key)

    if not data:
        return None

    try:
        return json.loads(data)
    except (json.JSONDecodeError, KeyError):
        return None


def delete_session(session_id: str) -> None:
    """Delete a session.

    Args:
        session_id: Session ID to delete
    """
    session_key = f"{SESSION_PREFIX}{session_id}"
    redis_client.delete(session_key)


def refresh_session(session_id: str) -> bool:
    """Refresh session TTL.

    Args:
        session_id: Session ID

    Returns:
        True if session was refreshed, False if not found
    """
    session_key = f"{SESSION_PREFIX}{session_id}"
    if redis_client.exists(session_key):
        redis_client.expire(session_key, SESSION_TTL)
        return True
    return False


