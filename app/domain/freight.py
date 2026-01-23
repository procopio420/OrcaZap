"""Freight calculation engine."""

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import FreightRule

logger = logging.getLogger(__name__)


class FreightError(Exception):
    """Freight calculation error."""

    pass


def normalize_cep(cep: str) -> str:
    """Normalize CEP format (remove dashes, spaces).

    Args:
        cep: CEP string (e.g., "01310-100" or "01310100")

    Returns:
        Normalized CEP (digits only)
    """
    return "".join(c for c in cep if c.isdigit())


def cep_in_range(cep: str, start: str, end: str) -> bool:
    """Check if CEP is in range.

    Args:
        cep: CEP to check
        start: Start of range
        end: End of range

    Returns:
        True if CEP is in range
    """
    cep_normalized = normalize_cep(cep)
    start_normalized = normalize_cep(start)
    end_normalized = normalize_cep(end)

    return start_normalized <= cep_normalized <= end_normalized


def calculate_freight(
    db: Session,
    tenant_id: UUID,
    cep_or_bairro: str,
    total_weight_kg: Decimal | None = None,
) -> Decimal:
    """Calculate freight cost based on CEP or bairro.

    Args:
        db: Database session
        tenant_id: Tenant UUID
        cep_or_bairro: CEP (e.g., "01310-100") or bairro name
        total_weight_kg: Total weight in kg (optional, for per_kg calculation)

    Returns:
        Freight cost as Decimal

    Raises:
        FreightError: If no freight rule found
    """
    # Try to find rule by bairro first
    freight_rule = (
        db.query(FreightRule)
        .filter_by(tenant_id=tenant_id, bairro=cep_or_bairro)
        .first()
    )

    # If not found by bairro, try CEP range
    if not freight_rule:
        # Assume it's a CEP if it looks like one (has digits)
        if any(c.isdigit() for c in cep_or_bairro):
            cep_normalized = normalize_cep(cep_or_bairro)

            # Find rule where CEP is in range
            all_rules = (
                db.query(FreightRule)
                .filter_by(tenant_id=tenant_id)
                .filter(FreightRule.cep_range_start.isnot(None))
                .all()
            )

            for rule in all_rules:
                if (
                    rule.cep_range_start
                    and rule.cep_range_end
                    and cep_in_range(cep_normalized, rule.cep_range_start, rule.cep_range_end)
                ):
                    freight_rule = rule
                    break

    if not freight_rule:
        raise FreightError(
            f"No freight rule found for tenant {tenant_id}, location: {cep_or_bairro}"
        )

    base_freight = Decimal(str(freight_rule.base_freight))

    # Add per-kg cost if applicable
    if freight_rule.per_kg_additional and total_weight_kg:
        per_kg = Decimal(str(freight_rule.per_kg_additional))
        additional = per_kg * total_weight_kg
        return base_freight + additional

    return base_freight


