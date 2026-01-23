"""Admin authentication."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import User

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Simple session storage (in production, use Redis or database)
# For MVP, we'll use a simple in-memory dict
_sessions: dict[str, dict] = {}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Get current authenticated user from session.

    For MVP, we use a simple session cookie.
    In production, use proper session management with Redis/database.
    """
    session_id = request.cookies.get("admin_session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )

    session_data = _sessions.get(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    # Check session expiration (24 hours)
    if datetime.now(timezone.utc) > session_data["expires_at"]:
        del _sessions[session_id]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    user_id = session_data["user_id"]
    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def create_session(user_id: UUID) -> str:
    """Create a new session and return session ID."""
    import secrets

    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return session_id


def delete_session(session_id: str) -> None:
    """Delete a session."""
    _sessions.pop(session_id, None)


def authenticate_user(db: Session, email: str, password: str, tenant_id: UUID) -> User | None:
    """Authenticate a user."""
    user = (
        db.query(User)
        .filter_by(email=email, tenant_id=tenant_id)
        .first()
    )

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user

