"""Shared authentication utilities for public and tenant routers."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
import bcrypt
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.sessions import create_session, delete_session
from app.db.models import Tenant, User, UserRole
from app.domain.slug import ensure_unique_slug, slugify


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    # Truncate password to 72 bytes if needed (bcrypt limit)
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.
    
    Bcrypt has a 72-byte limit. We truncate the password to 72 bytes if needed.
    This is safe because we validate password length before calling this function.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password (as string)
    """
    # Bcrypt has a 72-byte limit. Truncate to 72 bytes if necessary.
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # Truncate to 72 bytes
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash using bcrypt directly
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string (bcrypt hashes are ASCII-safe)
    return hash_bytes.decode('utf-8')


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
        HTTPException: If email already exists, password is invalid, or slug generation fails
    """
    # Validate password length before processing
    # Bcrypt has a 72-byte limit, so we validate early with a user-friendly message
    password_bytes = len(password.encode('utf-8'))
    if password_bytes > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha é muito longa. Por favor, use uma senha com no máximo 72 caracteres.",
        )
    
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
    # get_password_hash will also validate, but we've already checked above
    try:
        password_hash = get_password_hash(password)
    except HTTPException:
        raise  # Re-raise HTTPException as-is
    except Exception as e:
        # Catch any other hashing errors and provide user-friendly message
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao processar a senha: {str(e)}",
        )

    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=password_hash,
        role=str(UserRole.OWNER.value),  # Explicitly convert to string "owner" for PostgreSQL enum
    )
    db.add(user)
    db.commit()

    return tenant, user





