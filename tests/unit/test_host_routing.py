"""Unit tests for host routing middleware."""

import pytest

from app.middleware.host_routing import (
    HostContext,
    classify_host,
    extract_slug,
    SLUG_PATTERN,
)


def test_extract_slug_valid():
    """Test slug extraction from valid tenant hosts."""
    assert extract_slug("tenant1.orcazap.com") == "tenant1"
    assert extract_slug("my-store.orcazap.com") == "my-store"
    assert extract_slug("test123.orcazap.com") == "test123"
    assert extract_slug("a-b-c.orcazap.com") == "a-b-c"


def test_extract_slug_with_port():
    """Test slug extraction with port number."""
    assert extract_slug("tenant1.orcazap.com:8000") == "tenant1"
    assert extract_slug("my-store.orcazap.com:443") == "my-store"


def test_extract_slug_invalid():
    """Test slug extraction from invalid hosts."""
    assert extract_slug("orcazap.com") is None
    assert extract_slug("www.orcazap.com") is None
    assert extract_slug("api.orcazap.com") is None
    assert extract_slug("invalid") is None
    assert extract_slug("subdomain.example.com") is None


def test_extract_slug_reserved():
    """Test that reserved subdomains are not extracted as slugs."""
    assert extract_slug("www.orcazap.com") is None
    assert extract_slug("api.orcazap.com") is None


def test_slug_pattern():
    """Test slug pattern validation."""
    # Valid slugs
    assert SLUG_PATTERN.match("abc") is not None
    assert SLUG_PATTERN.match("test-123") is not None
    assert SLUG_PATTERN.match("my-store") is not None
    assert SLUG_PATTERN.match("a" * 32) is not None  # Max length

    # Invalid slugs
    assert SLUG_PATTERN.match("ab") is None  # Too short
    assert SLUG_PATTERN.match("a" * 33) is None  # Too long
    assert SLUG_PATTERN.match("Test") is None  # Uppercase
    assert SLUG_PATTERN.match("test_123") is None  # Underscore
    assert SLUG_PATTERN.match("test.123") is None  # Dot
    assert SLUG_PATTERN.match("test 123") is None  # Space


def test_classify_host_public():
    """Test classification of public hosts."""
    context, slug = classify_host("orcazap.com")
    assert context == HostContext.PUBLIC
    assert slug is None

    context, slug = classify_host("www.orcazap.com")
    assert context == HostContext.PUBLIC
    assert slug is None

    context, slug = classify_host("ORCAZAP.COM")  # Case insensitive
    assert context == HostContext.PUBLIC
    assert slug is None


def test_classify_host_api():
    """Test classification of API host."""
    context, slug = classify_host("api.orcazap.com")
    assert context == HostContext.API
    assert slug is None


def test_classify_host_tenant():
    """Test classification of tenant hosts."""
    context, slug = classify_host("tenant1.orcazap.com")
    assert context == HostContext.TENANT
    assert slug == "tenant1"

    context, slug = classify_host("my-store.orcazap.com")
    assert context == HostContext.TENANT
    assert slug == "my-store"


def test_classify_host_unknown():
    """Test classification of unknown hosts (defaults to public)."""
    context, slug = classify_host("unknown.com")
    assert context == HostContext.PUBLIC
    assert slug is None








