"""Integration tests for onboarding wizard."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, SessionLocal, engine
from app.db.models import FreightRule, Item, PricingRule, Tenant, TenantItem, User, UserRole
from app.main import app
from app.routers.auth import get_password_hash


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
def tenant_and_user(db_session):
    """Create tenant and user for onboarding."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Store", slug="test-store", onboarding_step=1)
    db_session.add(tenant)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()
    return tenant, user


def test_onboarding_step_1_form(client, tenant_and_user):
    """Test onboarding step 1 form rendering."""
    tenant, user = tenant_and_user

    # Login first
    login_response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "password123"},
        headers={"Host": "orcazap.com"},
    )
    session_id = login_response.cookies.get("session_id")

    # Access step 1
    response = client.get(
        "/onboarding/step/1",
        headers={"Host": "orcazap.com"},
        cookies={"session_id": session_id},
    )
    assert response.status_code == 200
    assert "Passo 1: Informações da Loja" in response.text
    assert "Nome da Loja" in response.text


def test_onboarding_step_2_saves_freight_rules(client, db_session, tenant_and_user):
    """Test onboarding step 2 saves freight rules."""
    tenant, user = tenant_and_user

    # Login
    login_response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "password123"},
        headers={"Host": "orcazap.com"},
    )
    session_id = login_response.cookies.get("session_id")

    # Submit step 2 with freight rule
    response = client.post(
        "/onboarding/step/2",
        data={
            "bairro_0": "Centro",
            "base_freight_0": "50.00",
            "per_kg_0": "2.00",
        },
        headers={"Host": "orcazap.com"},
        cookies={"session_id": session_id},
        follow_redirects=False,
    )

    assert response.status_code == 302  # Redirect to step 3

    # Verify freight rule was created
    freight_rules = db_session.query(FreightRule).filter_by(tenant_id=tenant.id).all()
    assert len(freight_rules) == 1
    assert freight_rules[0].bairro == "Centro"
    assert float(freight_rules[0].base_freight) == 50.00

    # Verify onboarding step updated
    db_session.refresh(tenant)
    assert tenant.onboarding_step == 3


def test_onboarding_step_3_saves_pricing_rules(client, db_session, tenant_and_user):
    """Test onboarding step 3 saves pricing rules."""
    tenant, user = tenant_and_user
    tenant.onboarding_step = 3
    db_session.commit()

    # Login
    login_response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "password123"},
        headers={"Host": "orcazap.com"},
    )
    session_id = login_response.cookies.get("session_id")

    # Submit step 3
    response = client.post(
        "/onboarding/step/3",
        data={
            "pix_discount_pct": "0.05",
            "margin_min_pct": "0.10",
            "approval_threshold_total": "1000.00",
        },
        headers={"Host": "orcazap.com"},
        cookies={"session_id": session_id},
        follow_redirects=False,
    )

    assert response.status_code == 302  # Redirect to step 4

    # Verify pricing rule was created
    pricing_rule = db_session.query(PricingRule).filter_by(tenant_id=tenant.id).first()
    assert pricing_rule is not None
    assert float(pricing_rule.pix_discount_pct) == 0.05
    assert float(pricing_rule.margin_min_pct) == 0.10
    assert float(pricing_rule.approval_threshold_total) == 1000.00


def test_onboarding_step_4_saves_items(client, db_session, tenant_and_user):
    """Test onboarding step 4 saves items."""
    tenant, user = tenant_and_user
    tenant.onboarding_step = 4
    db_session.commit()

    # Login
    login_response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "password123"},
        headers={"Host": "orcazap.com"},
    )
    session_id = login_response.cookies.get("session_id")

    # Submit step 4 with manual items
    response = client.post(
        "/onboarding/step/4",
        data={
            "items_manual": "ABC123,Cimento,kg,25.50\nXYZ789,Tijolo,un,0.85",
        },
        headers={"Host": "orcazap.com"},
        cookies={"session_id": session_id},
        follow_redirects=False,
    )

    assert response.status_code == 302  # Redirect to step 5

    # Verify items were created
    items = db_session.query(Item).filter(Item.sku.in_(["ABC123", "XYZ789"])).all()
    assert len(items) == 2

    # Verify tenant_items were created
    tenant_items = db_session.query(TenantItem).filter_by(tenant_id=tenant.id).all()
    assert len(tenant_items) == 2


def test_onboarding_completes_at_step_5(client, db_session, tenant_and_user):
    """Test onboarding completes at step 5."""
    tenant, user = tenant_and_user
    tenant.onboarding_step = 5
    db_session.commit()

    # Login
    login_response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "password123"},
        headers={"Host": "orcazap.com"},
    )
    session_id = login_response.cookies.get("session_id")

    # Submit step 5
    response = client.post(
        "/onboarding/step/5",
        data={},
        headers={"Host": "orcazap.com"},
        cookies={"session_id": session_id},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert f"{tenant.slug}.orcazap.com" in response.headers["location"]

    # Verify onboarding completed
    db_session.refresh(tenant)
    assert tenant.onboarding_step is None
    assert tenant.onboarding_completed_at is not None








