"""Quote generation and approval checking."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Approval, ApprovalStatus, PricingRule, Quote, QuoteStatus
from app.domain.freight import FreightError, calculate_freight
from app.domain.pricing import PricingError, calculate_quote_totals

logger = logging.getLogger(__name__)


class QuoteGenerationError(Exception):
    """Quote generation error."""

    pass


def check_approval_required(
    db: Session,
    tenant_id: UUID,
    total: Decimal,
    margin_pct: Decimal,
    unknown_skus: list[str] | None = None,
) -> tuple[bool, str]:
    """Check if quote requires human approval.

    Args:
        db: Database session
        tenant_id: Tenant UUID
        total: Quote total amount
        margin_pct: Calculated margin percentage
        unknown_skus: List of unknown SKUs (if any)

    Returns:
        Tuple of (needs_approval, reason)
    """
    pricing_rules = (
        db.query(PricingRule).filter_by(tenant_id=tenant_id).first()
    )

    if not pricing_rules:
        return (True, "Pricing rules not found")

    reasons = []

    # Check for unknown SKUs
    if unknown_skus:
        reasons.append(f"Unknown SKUs: {', '.join(unknown_skus)}")

    # Check total threshold
    if (
        pricing_rules.approval_threshold_total
        and total > Decimal(str(pricing_rules.approval_threshold_total))
    ):
        reasons.append(
            f"Total {total} exceeds threshold {pricing_rules.approval_threshold_total}"
        )

    # Check margin threshold
    if (
        pricing_rules.approval_threshold_margin
        and margin_pct < Decimal(str(pricing_rules.approval_threshold_margin))
    ):
        reasons.append(
            f"Margin {margin_pct} below threshold {pricing_rules.approval_threshold_margin}"
        )

    if reasons:
        return (True, "; ".join(reasons))

    return (False, "")


def generate_quote(
    db: Session,
    tenant_id: UUID,
    conversation_id: UUID,
    items: list[dict[str, Any]],  # [{item_id, quantity, sku?}]
    cep_or_bairro: str,
    payment_method: str,
    delivery_day: str,
    request_id: str | None = None,  # For structured logging (R5)
) -> tuple[Quote, bool]:
    """Generate a quote with pricing and freight.

    Args:
        db: Database session
        tenant_id: Tenant UUID
        conversation_id: Conversation UUID
        items: List of items with item_id and quantity
        cep_or_bairro: CEP or bairro for freight calculation
        payment_method: Payment method
        delivery_day: Delivery day description

    Returns:
        Tuple of (quote, needs_approval)

    Raises:
        QuoteGenerationError: If quote generation fails
    """
    log_extra = {
        "tenant_id": str(tenant_id),
        "conversation_id": str(conversation_id),
    }
    if request_id:
        log_extra["request_id"] = request_id

    try:
        # Calculate pricing
        pricing_result = calculate_quote_totals(db, tenant_id, items, payment_method, request_id)
    except PricingError as e:
        logger.error(f"Pricing calculation failed: {e}", extra=log_extra)
        raise QuoteGenerationError(f"Pricing calculation failed: {e}") from e

    try:
        # Calculate freight (weight calculation would go here if needed)
        freight = calculate_freight(db, tenant_id, cep_or_bairro)
    except FreightError as e:
        logger.warning(f"Freight calculation failed: {e}", extra=log_extra)
        # For MVP, if freight fails, we might need approval
        # For now, set freight to 0 and require approval
        freight = Decimal("0")
        needs_approval = True
        approval_reason = f"Freight calculation failed: {e}"
    else:
        # Check if approval required
        total_with_freight = Decimal(str(pricing_result["total"])) + freight
        # Note: unknown_skus would be passed here if we had them from parsing
        # For now, we check in the worker handler before calling generate_quote
        needs_approval, approval_reason = check_approval_required(
            db,
            tenant_id,
            total_with_freight,
            Decimal(str(pricing_result["margin_pct"])),
            unknown_skus=None,  # Will be enhanced to pass from worker
        )

    # Calculate final total
    total = Decimal(str(pricing_result["total"])) + freight

    # Valid until: 24 hours from now
    valid_until = datetime.now(timezone.utc) + timedelta(hours=24)

    # Create quote
    quote = Quote(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        status=QuoteStatus.DRAFT,
        items_json=pricing_result["items"],
        subtotal=Decimal(str(pricing_result["subtotal"])),
        freight=freight,
        discount_pct=Decimal(str(pricing_result["discount_pct"])),
        total=total,
        margin_pct=Decimal(str(pricing_result["margin_pct"])),
        valid_until=valid_until,
        payload_json={
            "items": items,
            "cep_or_bairro": cep_or_bairro,
            "payment_method": payment_method,
            "delivery_day": delivery_day,
            "pricing": pricing_result,
            "freight": float(freight),
        },
    )

    db.add(quote)
    db.flush()

    # Create approval if needed
    if needs_approval:
        approval = Approval(
            tenant_id=tenant_id,
            quote_id=quote.id,
            status=ApprovalStatus.PENDING,
            reason=approval_reason,
        )
        db.add(approval)
        logger.info(
            f"Quote {quote.id} requires approval: {approval_reason}",
            extra=log_extra,
        )

    return (quote, needs_approval)

