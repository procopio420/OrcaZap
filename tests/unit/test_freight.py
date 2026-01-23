"""Unit tests for freight calculation."""

import uuid
from decimal import Decimal

import pytest

from app.db.base import Base, SessionLocal, engine
from app.db.models import FreightRule, Tenant
from app.domain.freight import FreightError, calculate_freight, cep_in_range, normalize_cep


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
def tenant(db_session):
    """Create a test tenant."""
    tenant = Tenant(id=uuid.uuid4(), name="Test Store")
    db_session.add(tenant)
    db_session.commit()
    return tenant


def test_normalize_cep():
    """Test CEP normalization."""
    assert normalize_cep("01310-100") == "01310100"
    assert normalize_cep("01310 100") == "01310100"
    assert normalize_cep("01310100") == "01310100"


def test_cep_in_range():
    """Test CEP range checking."""
    assert cep_in_range("01310-100", "01310-000", "01310-999") is True
    assert cep_in_range("01310-100", "01320-000", "01320-999") is False
    assert cep_in_range("01315-500", "01310-000", "01320-999") is True


def test_calculate_freight_by_bairro(db_session, tenant):
    """Test freight calculation by bairro."""
    rule = FreightRule(
        tenant_id=tenant.id,
        bairro="Centro",
        base_freight=Decimal("45.00"),
    )
    db_session.add(rule)
    db_session.commit()

    freight = calculate_freight(db_session, tenant.id, "Centro")
    assert freight == Decimal("45.00")


def test_calculate_freight_by_cep_range(db_session, tenant):
    """Test freight calculation by CEP range."""
    rule = FreightRule(
        tenant_id=tenant.id,
        cep_range_start="01310-000",
        cep_range_end="01310-999",
        base_freight=Decimal("50.00"),
    )
    db_session.add(rule)
    db_session.commit()

    freight = calculate_freight(db_session, tenant.id, "01310-100")
    assert freight == Decimal("50.00")


def test_calculate_freight_with_per_kg(db_session, tenant):
    """Test freight calculation with per-kg additional cost."""
    rule = FreightRule(
        tenant_id=tenant.id,
        bairro="Centro",
        base_freight=Decimal("30.00"),
        per_kg_additional=Decimal("2.50"),
    )
    db_session.add(rule)
    db_session.commit()

    freight = calculate_freight(db_session, tenant.id, "Centro", total_weight_kg=Decimal("10"))
    # 30.00 + (2.50 * 10) = 55.00
    assert freight == Decimal("55.00")


def test_calculate_freight_not_found(db_session, tenant):
    """Test error when freight rule not found."""
    with pytest.raises(FreightError, match="No freight rule found"):
        calculate_freight(db_session, tenant.id, "Unknown Location")


def test_calculate_freight_cep_precedence(db_session, tenant):
    """Test that bairro takes precedence over CEP range."""
    # Create both bairro and CEP rules
    bairro_rule = FreightRule(
        tenant_id=tenant.id,
        bairro="Centro",
        base_freight=Decimal("40.00"),
    )
    cep_rule = FreightRule(
        tenant_id=tenant.id,
        cep_range_start="01310-000",
        cep_range_end="01310-999",
        base_freight=Decimal("50.00"),
    )
    db_session.add(bairro_rule)
    db_session.add(cep_rule)
    db_session.commit()

    # Should use bairro rule
    freight = calculate_freight(db_session, tenant.id, "Centro")
    assert freight == Decimal("40.00")


