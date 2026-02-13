"""Integration tests for API host routing and operator admin."""

import base64
import os
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
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def operator_credentials():
    """Set operator credentials for testing."""
    os.environ["OPERATOR_USERNAME"] = "admin"
    os.environ["OPERATOR_PASSWORD"] = "secret123"
    yield
    os.environ.pop("OPERATOR_USERNAME", None)
    os.environ.pop("OPERATOR_PASSWORD", None)


def test_api_health_on_api_host(client):
    """Test health endpoint on API host."""
    response = client.get("/health", headers={"Host": "api.orcazap.com"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "orcazap"}


def test_api_health_blocked_on_public_host(client):
    """Test health endpoint blocked on public host."""
    response = client.get("/health", headers={"Host": "orcazap.com"})
    assert response.status_code == 404


def test_api_health_blocked_on_tenant_host(client, db_session):
    """Test health endpoint blocked on tenant host."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Store", slug="test-store")
    db_session.add(tenant)
    db_session.commit()

    response = client.get("/health", headers={"Host": "test-store.orcazap.com"})
    assert response.status_code == 404


def test_operator_admin_requires_auth(client, operator_credentials):
    """Test operator admin requires Basic Auth."""
    response = client.get("/admin", headers={"Host": "api.orcazap.com"})
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_operator_admin_with_valid_credentials(client, operator_credentials):
    """Test operator admin with valid credentials."""
    credentials = base64.b64encode(b"admin:secret123").decode("utf-8")
    response = client.get(
        "/admin",
        headers={
            "Host": "api.orcazap.com",
            "Authorization": f"Basic {credentials}",
        },
    )
    assert response.status_code == 200
    assert "Operator Admin Dashboard" in response.text


def test_operator_admin_with_invalid_credentials(client, operator_credentials):
    """Test operator admin with invalid credentials."""
    credentials = base64.b64encode(b"admin:wrongpassword").decode("utf-8")
    response = client.get(
        "/admin",
        headers={
            "Host": "api.orcazap.com",
            "Authorization": f"Basic {credentials}",
        },
    )
    assert response.status_code == 401


def test_operator_admin_blocked_on_public_host(client, operator_credentials):
    """Test operator admin blocked on public host."""
    credentials = base64.b64encode(b"admin:secret123").decode("utf-8")
    response = client.get(
        "/admin",
        headers={
            "Host": "orcazap.com",
            "Authorization": f"Basic {credentials}",
        },
    )
    assert response.status_code == 404


def test_operator_tenants_list(client, db_session, operator_credentials):
    """Test operator tenants list."""
    # Create test tenants
    tenant1 = Tenant(id=uuid.uuid4(), name="Store 1", slug="store-1")
    tenant2 = Tenant(id=uuid.uuid4(), name="Store 2", slug="store-2")
    db_session.add(tenant1)
    db_session.add(tenant2)
    db_session.commit()

    credentials = base64.b64encode(b"admin:secret123").decode("utf-8")
    response = client.get(
        "/admin/tenants",
        headers={
            "Host": "api.orcazap.com",
            "Authorization": f"Basic {credentials}",
        },
    )
    assert response.status_code == 200
    assert "Store 1" in response.text
    assert "Store 2" in response.text


def test_webhook_blocked_on_public_host(client):
    """Test webhook blocked on public host."""
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_token",
            "hub.challenge": "test_challenge",
        },
        headers={"Host": "orcazap.com"},
    )
    assert response.status_code == 404


def test_webhook_allowed_on_api_host(client, monkeypatch):
    """Test webhook allowed on API host."""
    from app.settings import settings

    monkeypatch.setattr(settings, "whatsapp_verify_token", "test_token")
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_token",
            "hub.challenge": "test_challenge",
        },
        headers={"Host": "api.orcazap.com"},
    )
    assert response.status_code == 200








