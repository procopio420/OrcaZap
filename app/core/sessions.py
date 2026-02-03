"""Session management with Redis storage."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import redis
from redis.exceptions import RedisError

from app.settings import settings

logger = logging.getLogger(__name__)

# Redis client (lazy initialization)
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Get Redis client (singleton)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


def create_session(user_id: UUID, csrf_token: Optional[str] = None) -> tuple[str, str]:
    """Create a new session and return (session_id, csrf_token).
    
    Args:
        user_id: User UUID
        csrf_token: Optional CSRF token (if None, will be generated)
    
    Returns:
        Tuple of (session_id, csrf_token)
    """
    import secrets
    
    session_id = secrets.token_urlsafe(32)
    if csrf_token is None:
        csrf_token = secrets.token_urlsafe(32)
    
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    session_data = {
        "user_id": str(user_id),
        "csrf_token": csrf_token,
        "expires_at": expires_at.isoformat(),
    }
    
    try:
        redis_client = get_redis_client()
        # Store session with expiration (24 hours = 86400 seconds)
        redis_client.setex(
            f"session:{session_id}",
            86400,  # 24 hours in seconds
            json.dumps(session_data),
        )
        logger.debug(f"Session created: {session_id} for user {user_id}")
    except RedisError as e:
        logger.error(f"Failed to create session in Redis: {e}", exc_info=True)
        raise
    
    return session_id, csrf_token


def get_session(session_id: str) -> Optional[dict]:
    """Get session data.
    
    Args:
        session_id: Session ID
    
    Returns:
        Session data dict or None if not found/expired
    """
    if not session_id:
        return None
    
    try:
        redis_client = get_redis_client()
        data = redis_client.get(f"session:{session_id}")
        
        if not data:
            return None
        
        session_data = json.loads(data)
        
        # Check expiration
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            # Session expired, delete it
            delete_session(session_id)
            return None
        
        return session_data
    except (RedisError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to get session {session_id}: {e}")
        return None


def update_session(session_id: str, **kwargs) -> bool:
    """Update session data.
    
    Args:
        session_id: Session ID
        **kwargs: Fields to update
    
    Returns:
        True if updated, False if session not found
    """
    session_data = get_session(session_id)
    if not session_data:
        return False
    
    # Update fields
    session_data.update(kwargs)
    
    try:
        redis_client = get_redis_client()
        # Get TTL to preserve expiration
        ttl = redis_client.ttl(f"session:{session_id}")
        if ttl > 0:
            redis_client.setex(
                f"session:{session_id}",
                ttl,
                json.dumps(session_data),
            )
            return True
    except RedisError as e:
        logger.error(f"Failed to update session {session_id}: {e}", exc_info=True)
    
    return False


def delete_session(session_id: str) -> None:
    """Delete a session.
    
    Args:
        session_id: Session ID
    """
    if not session_id:
        return
    
    try:
        redis_client = get_redis_client()
        redis_client.delete(f"session:{session_id}")
        logger.debug(f"Session deleted: {session_id}")
    except RedisError as e:
        logger.warning(f"Failed to delete session {session_id}: {e}")


def extend_session(session_id: str, hours: int = 24) -> bool:
    """Extend session expiration.
    
    Args:
        session_id: Session ID
        hours: Hours to extend (default 24)
    
    Returns:
        True if extended, False if session not found
    """
    session_data = get_session(session_id)
    if not session_data:
        return False
    
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    session_data["expires_at"] = expires_at.isoformat()
    
    try:
        redis_client = get_redis_client()
        redis_client.setex(
            f"session:{session_id}",
            hours * 3600,  # Convert to seconds
            json.dumps(session_data),
        )
        return True
    except RedisError as e:
        logger.error(f"Failed to extend session {session_id}: {e}", exc_info=True)
        return False
