"""Shared authentication utilities for public and tenant routers."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.sessions import create_session, delete_session
from app.db.models import Tenant, User, UserRole
from app.domain.slug import ensure_unique_slug, slugify

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def authenticate_user(db: Session, email: str, password: str, tenant_id: UUID) -> User | None:
    """Authenticate a user."""
    user = db.query(User).filter_by(email=email, tenant_id=tenant_id).first()

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def register_tenant_and_user(
    db: Session,
    store_name: str,
    email: str,
    password: str,
) -> tuple[Tenant, User]:
    """Register a new tenant and owner user.

    Args:
        db: Database session
        store_name: Store name
        email: Owner email
        password: Owner password (plain text)

    Returns:
        Tuple of (Tenant, User)

    Raises:
        HTTPException: If email already exists or slug generation fails
    """
    # Generate unique slug
    base_slug = slugify(store_name)
    slug = ensure_unique_slug(db, base_slug)

    # Check if email already exists (globally, for simplicity)
    # In production, you might want per-tenant email uniqueness
    existing_user = db.query(User).filter_by(email=email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create tenant
    tenant = Tenant(
        name=store_name,
        slug=slug,
        onboarding_step=1,  # Start at step 1
    )
    db.add(tenant)
    db.flush()  # Get tenant.id

    # Create owner user
    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=get_password_hash(password),
        role=UserRole.OWNER,
    )
    db.add(user)
    db.commit()

    return tenant, user





