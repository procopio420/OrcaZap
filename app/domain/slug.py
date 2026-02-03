"""Slug generation and validation utilities."""

import re
import unicodedata

from sqlalchemy.orm import Session

from app.db.models import Tenant

# Slug validation regex: lowercase, alphanumeric, hyphens only, 3-32 chars
SLUG_PATTERN = re.compile(r"^[a-z0-9-]{3,32}$")


def slugify(name: str) -> str:
    """Generate a URL-friendly slug from a name.

    Args:
        name: Store name or other text

    Returns:
        URL-friendly slug (lowercase, alphanumeric, hyphens)
    """
    # Normalize unicode characters (e.g., ç -> c)
    name = unicodedata.normalize("NFKD", name)
    # Convert to lowercase
    name = name.lower()
    # Replace spaces and underscores with hyphens
    name = re.sub(r"[_\s]+", "-", name)
    # Remove all non-alphanumeric characters except hyphens
    name = re.sub(r"[^a-z0-9-]", "", name)
    # Replace multiple hyphens with single hyphen
    name = re.sub(r"-+", "-", name)
    # Remove leading/trailing hyphens
    name = name.strip("-")
    # Ensure minimum length
    if len(name) < 3:
        name = name + "-" + "x" * (3 - len(name))
    # Truncate to max length
    if len(name) > 32:
        name = name[:32].rstrip("-")
    return name


def validate_slug(slug: str) -> bool:
    """Validate slug format.

    Args:
        slug: Slug to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(SLUG_PATTERN.match(slug))


def ensure_unique_slug(db: Session, base_slug: str) -> str:
    """Ensure slug is unique by appending number if needed.

    Args:
        db: Database session
        base_slug: Base slug to make unique

    Returns:
        Unique slug
    """
    slug = base_slug
    counter = 1

    while db.query(Tenant).filter_by(slug=slug).first() is not None:
        # Append counter, but keep within 32 char limit
        suffix = f"-{counter}"
        if len(base_slug) + len(suffix) > 32:
            # Truncate base to make room
            truncate_len = 32 - len(suffix)
            slug = base_slug[:truncate_len] + suffix
        else:
            slug = base_slug + suffix
        counter += 1

    return slug





