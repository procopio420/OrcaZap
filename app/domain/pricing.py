"""Pricing engine - deterministic pricing calculations."""

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Item, PricingRule, TenantItem, VolumeDiscount

logger = logging.getLogger(__name__)


class PricingError(Exception):
    """Pricing calculation error."""

    pass


def calculate_item_price(
    db: Session,
    tenant_id: UUID,
    item_id: UUID,
    quantity: Decimal,
    request_id: str | None = None,  # For structured logging (R5)
) -> tuple[Decimal, Decimal]:
    """Calculate price for a single item with volume discounts.

    Args:
        db: Database session
        tenant_id: Tenant UUID
        item_id: Item UUID
        quantity: Item quantity

    Returns:
        Tuple of (unit_price, total_price)

    Raises:
        PricingError: If item not found or not active
    """
    # Get tenant item (base price)
    tenant_item = (
        db.query(TenantItem)
        .filter_by(tenant_id=tenant_id, item_id=item_id, is_active=True)
        .first()
    )

    if not tenant_item:
        item = db.query(Item).filter_by(id=item_id).first()
        item_sku = item.sku if item else "unknown"
        log_extra = {"item_id": str(item_id), "item_sku": item_sku, "tenant_id": str(tenant_id)}
        if request_id:
            log_extra["request_id"] = request_id
        logger.warning(f"Item {item_sku} not found or not active", extra=log_extra)
        raise PricingError(f"Item {item_sku} (id: {item_id}) not found or not active for tenant")

    base_price = Decimal(str(tenant_item.price_base))
    unit_price = base_price

    # Apply volume discounts (item-specific first, then global)
    # Get item-specific discounts
    item_discounts = (
        db.query(VolumeDiscount)
        .filter_by(tenant_id=tenant_id, item_id=item_id)
        .order_by(VolumeDiscount.min_quantity.desc())  # Highest quantity first
        .all()
    )

    # Get global discounts (item_id is None)
    global_discounts = (
        db.query(VolumeDiscount)
        .filter_by(tenant_id=tenant_id, item_id=None)
        .order_by(VolumeDiscount.min_quantity.desc())
        .all()
    )

    # Apply best matching discount (item-specific takes precedence)
    best_discount_pct = Decimal("0")
    for discount in item_discounts:
        if quantity >= Decimal(str(discount.min_quantity)):
            best_discount_pct = Decimal(str(discount.discount_pct))
            break

    # If no item-specific discount, check global
    if best_discount_pct == 0:
        for discount in global_discounts:
            if quantity >= Decimal(str(discount.min_quantity)):
                best_discount_pct = Decimal(str(discount.discount_pct))
                break

    # Apply discount
    if best_discount_pct > 0:
        discount_amount = base_price * best_discount_pct
        unit_price = base_price - discount_amount

    total_price = unit_price * quantity

    return (unit_price, total_price)


def calculate_quote_totals(
    db: Session,
    tenant_id: UUID,
    items: list[dict[str, Any]],  # [{item_id, quantity, sku?}]
    payment_method: str,
    request_id: str | None = None,  # For structured logging (R5)
) -> dict[str, Any]:
    """Calculate quote totals with discounts.

    Args:
        db: Database session
        tenant_id: Tenant UUID
        items: List of items with item_id and quantity
        payment_method: Payment method (PIX, Cartão, Boleto)

    Returns:
        Dictionary with:
        - items: List of items with prices
        - subtotal: Subtotal before discounts
        - discount_pct: Discount percentage applied
        - discount_amount: Discount amount
        - total: Total after discount
        - margin_pct: Calculated margin percentage

    Raises:
        PricingError: If pricing rules not found or calculation fails
    """
    # Get pricing rules
    pricing_rules = (
        db.query(PricingRule).filter_by(tenant_id=tenant_id).first()
    )

    if not pricing_rules:
        raise PricingError(f"Pricing rules not found for tenant {tenant_id}")

    # Calculate item prices
    quote_items = []
    subtotal = Decimal("0")

    for item_data in items:
        item_id = UUID(item_data["item_id"])
        quantity = Decimal(str(item_data["quantity"]))

        unit_price, item_total = calculate_item_price(db, tenant_id, item_id, quantity, request_id)

        # Get item details for quote
        item = db.query(Item).filter_by(id=item_id).first()
        quote_items.append({
            "item_id": str(item_id),
            "sku": item.sku if item else "unknown",
            "name": item.name if item else "Unknown",
            "unit": item.unit if item else "un",
            "quantity": float(quantity),
            "unit_price": float(unit_price),
            "total": float(item_total),
        })

        subtotal += item_total

    # Apply payment method discount (PIX)
    discount_pct = Decimal("0")
    if payment_method.upper() == "PIX":
        discount_pct = Decimal(str(pricing_rules.pix_discount_pct))

    discount_amount = subtotal * discount_pct
    total = subtotal - discount_amount

    # Calculate margin (simplified for MVP)
    # Note: Actual margin calculation would be: margin = (total - cost) / total
    # For MVP, we use margin_min_pct from rules as a placeholder
    # In production, this would consider actual cost basis from inventory system
    margin_pct = Decimal(str(pricing_rules.margin_min_pct))  # Simplified - uses rule minimum as placeholder

    return {
        "items": quote_items,
        "subtotal": float(subtotal),
        "discount_pct": float(discount_pct),
        "discount_amount": float(discount_amount),
        "total": float(total),
        "margin_pct": float(margin_pct),
    }

