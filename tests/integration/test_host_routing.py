"""Integration tests for host routing."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, SessionLocal, engine
from app.db.models import Tenant
from app.main import app


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def test_tenant(db_session):
    """Create a test tenant with slug."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Store", slug="test-store")
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_public_host_landing(client):
    """Test landing page on public host."""
    response = client.get("/", headers={"Host": "orcazap.com"})
    assert response.status_code == 200
    assert "OrcaZap" in response.text
    assert "Assistente de orçamentos" in response.text


def test_public_host_login(client):
    """Test login page on public host."""
    response = client.get("/login", headers={"Host": "orcazap.com"})
    assert response.status_code == 200
    assert "Login" in response.text


def test_public_host_www(client):
    """Test public routes work on www subdomain."""
    response = client.get("/", headers={"Host": "www.orcazap.com"})
    assert response.status_code == 200


def test_tenant_host_dashboard(client, test_tenant):
    """Test tenant dashboard on tenant host."""
    response = client.get("/", headers={"Host": f"{test_tenant.slug}.orcazap.com"})
    assert response.status_code == 200
    assert test_tenant.name in response.text
    assert test_tenant.slug in response.text


def test_tenant_host_not_found(client):
    """Test tenant host with non-existent slug returns 404."""
    response = client.get("/", headers={"Host": "nonexistent.orcazap.com"})
    assert response.status_code == 404
    assert "Loja não encontrada" in response.text
    assert "nonexistent.orcazap.com" in response.text


def test_api_host_health(client):
    """Test health endpoint on API host."""
    response = client.get("/health", headers={"Host": "api.orcazap.com"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "orcazap"}


def test_route_blocking_public_from_tenant(client, test_tenant):
    """Test that public routes are blocked from tenant host."""
    # Try to access public landing from tenant host
    response = client.get("/", headers={"Host": f"{test_tenant.slug}.orcazap.com"})
    # Should get tenant dashboard, not public landing
    assert response.status_code == 200
    assert test_tenant.name in response.text  # Tenant dashboard content


def test_route_blocking_tenant_from_public(client, test_tenant):
    """Test that tenant routes are blocked from public host."""
    # The tenant dashboard should not be accessible from public host
    # Since we're using the same "/" route, it will show public landing
    response = client.get("/", headers={"Host": "orcazap.com"})
    assert response.status_code == 200
    assert "OrcaZap" in response.text
    # Should not contain tenant-specific content
    assert test_tenant.name not in response.text


def test_route_blocking_api_from_public(client):
    """Test that API routes are blocked from public host."""
    response = client.get("/health", headers={"Host": "orcazap.com"})
    assert response.status_code == 404  # API route not available on public host


def test_route_blocking_api_from_tenant(client, test_tenant):
    """Test that API routes are blocked from tenant host."""
    response = client.get("/health", headers={"Host": f"{test_tenant.slug}.orcazap.com"})
    assert response.status_code == 404  # API route not available on tenant host


def test_tenant_slug_case_insensitive(client, db_session):
    """Test that tenant slug matching is case-insensitive."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Store", slug="test-store")
    db_session.add(tenant)
    db_session.commit()

    # Try with uppercase
    response = client.get("/", headers={"Host": "TEST-STORE.orcazap.com"})
    assert response.status_code == 200
    assert tenant.name in response.text


def test_multiple_tenants_isolation(client, db_session):
    """Test that different tenants are isolated."""
    tenant1 = Tenant(id=uuid.uuid4(), name="Store 1", slug="store-1")
    tenant2 = Tenant(id=uuid.uuid4(), name="Store 2", slug="store-2")
    db_session.add(tenant1)
    db_session.add(tenant2)
    db_session.commit()

    # Access tenant1
    response1 = client.get("/", headers={"Host": "store-1.orcazap.com"})
    assert response1.status_code == 200
    assert tenant1.name in response1.text
    assert tenant2.name not in response1.text

    # Access tenant2
    response2 = client.get("/", headers={"Host": "store-2.orcazap.com"})
    assert response2.status_code == 200
    assert tenant2.name in response2.text
    assert tenant1.name not in response2.text











