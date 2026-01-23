"""Unit tests for pricing engine."""

import uuid
from decimal import Decimal

import pytest

from app.db.base import Base, SessionLocal, engine
from app.db.models import Item, PricingRule, Tenant, TenantItem, VolumeDiscount
from app.domain.pricing import PricingError, calculate_item_price, calculate_quote_totals


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


@pytest.fixture
def pricing_rules(db_session, tenant):
    """Create pricing rules."""
    rules = PricingRule(
        tenant_id=tenant.id,
        pix_discount_pct=Decimal("0.05"),  # 5%
        margin_min_pct=Decimal("0.10"),  # 10%
        approval_threshold_total=Decimal("10000.00"),
        approval_threshold_margin=Decimal("0.05"),
    )
    db_session.add(rules)
    db_session.commit()
    return rules


@pytest.fixture
def item(db_session):
    """Create a test item."""
    item = Item(sku="CEMENT-50KG", name="Cimento 50kg", unit="saco")
    db_session.add(item)
    db_session.commit()
    return item


@pytest.fixture
def tenant_item(db_session, tenant, item):
    """Create tenant item with price."""
    tenant_item = TenantItem(
        tenant_id=tenant.id,
        item_id=item.id,
        price_base=Decimal("45.00"),
        is_active=True,
    )
    db_session.add(tenant_item)
    db_session.commit()
    return tenant_item


def test_calculate_item_price_no_discount(db_session, tenant, tenant_item):
    """Test item price calculation without volume discount."""
    unit_price, total = calculate_item_price(
        db_session, tenant.id, tenant_item.item_id, Decimal("10")
    )

    assert unit_price == Decimal("45.00")
    assert total == Decimal("450.00")


def test_calculate_item_price_with_volume_discount(db_session, tenant, tenant_item):
    """Test item price calculation with volume discount."""
    # Create volume discount: 10% off for 20+ units
    discount = VolumeDiscount(
        tenant_id=tenant.id,
        item_id=tenant_item.item_id,
        min_quantity=Decimal("20"),
        discount_pct=Decimal("0.10"),
    )
    db_session.add(discount)
    db_session.commit()

    # Quantity below threshold - no discount
    unit_price, total = calculate_item_price(
        db_session, tenant.id, tenant_item.item_id, Decimal("10")
    )
    assert unit_price == Decimal("45.00")
    assert total == Decimal("450.00")

    # Quantity at threshold - discount applied
    unit_price, total = calculate_item_price(
        db_session, tenant.id, tenant_item.item_id, Decimal("20")
    )
    # 45.00 - (45.00 * 0.10) = 40.50
    assert unit_price == Decimal("40.50")
    assert total == Decimal("810.00")  # 40.50 * 20


def test_calculate_item_price_global_discount(db_session, tenant, tenant_item):
    """Test item price calculation with global volume discount."""
    # Create global discount (item_id is None)
    discount = VolumeDiscount(
        tenant_id=tenant.id,
        item_id=None,  # Global
        min_quantity=Decimal("50"),
        discount_pct=Decimal("0.15"),
    )
    db_session.add(discount)
    db_session.commit()

    unit_price, total = calculate_item_price(
        db_session, tenant.id, tenant_item.item_id, Decimal("50")
    )
    # 45.00 - (45.00 * 0.15) = 38.25
    assert unit_price == Decimal("38.25")
    assert total == Decimal("1912.50")  # 38.25 * 50


def test_calculate_item_price_item_not_found(db_session, tenant):
    """Test error when item not found."""
    fake_item_id = uuid.uuid4()

    with pytest.raises(PricingError, match="not found or not active"):
        calculate_item_price(db_session, tenant.id, fake_item_id, Decimal("10"))


def test_calculate_quote_totals_pix_discount(db_session, tenant, pricing_rules, tenant_item):
    """Test quote totals with PIX discount."""
    items = [
        {"item_id": str(tenant_item.item_id), "quantity": 10},
    ]

    result = calculate_quote_totals(
        db_session, tenant.id, items, "PIX"
    )

    assert result["subtotal"] == 450.00
    assert result["discount_pct"] == 0.05  # 5% PIX discount
    assert result["discount_amount"] == 22.50  # 450 * 0.05
    assert result["total"] == 427.50  # 450 - 22.50
    assert len(result["items"]) == 1


def test_calculate_quote_totals_no_discount(db_session, tenant, pricing_rules, tenant_item):
    """Test quote totals without discount (non-PIX payment)."""
    items = [
        {"item_id": str(tenant_item.item_id), "quantity": 10},
    ]

    result = calculate_quote_totals(
        db_session, tenant.id, items, "Cartão"
    )

    assert result["subtotal"] == 450.00
    assert result["discount_pct"] == 0.0
    assert result["discount_amount"] == 0.0
    assert result["total"] == 450.00


def test_calculate_quote_totals_multiple_items(db_session, tenant, pricing_rules, tenant_item):
    """Test quote totals with multiple items."""
    # Create second item
    item2 = Item(sku="SAND-MED", name="Areia média", unit="m³")
    db_session.add(item2)
    db_session.commit()

    tenant_item2 = TenantItem(
        tenant_id=tenant.id,
        item_id=item2.id,
        price_base=Decimal("90.00"),
        is_active=True,
    )
    db_session.add(tenant_item2)
    db_session.commit()

    items = [
        {"item_id": str(tenant_item.item_id), "quantity": 10},
        {"item_id": str(tenant_item2.item_id), "quantity": 2},
    ]

    result = calculate_quote_totals(
        db_session, tenant.id, items, "PIX"
    )

    assert result["subtotal"] == 630.00  # 450 + 180
    assert result["discount_amount"] == 31.50  # 630 * 0.05
    assert result["total"] == 598.50
    assert len(result["items"]) == 2


