"""Tenant metrics calculation."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Approval, ApprovalStatus, Quote


def get_tenant_metrics(db: Session, tenant_id: UUID) -> dict:
    """Calculate tenant metrics.

    Args:
        db: Database session
        tenant_id: Tenant UUID

    Returns:
        Dictionary with metrics:
        - quotes_7d: Number of quotes generated in last 7 days
        - quotes_30d: Number of quotes generated in last 30 days
        - approvals_pending: Number of pending approvals
        - messages_processed: Number of messages processed (placeholder for now)
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Quotes in last 7 days
    quotes_7d = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id)
        .filter(Quote.created_at >= seven_days_ago)
        .scalar()
        or 0
    )

    # Quotes in last 30 days
    quotes_30d = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id)
        .filter(Quote.created_at >= thirty_days_ago)
        .scalar()
        or 0
    )

    # Pending approvals
    approvals_pending = (
        db.query(func.count(Approval.id))
        .filter(Approval.tenant_id == tenant_id)
        .filter(Approval.status == ApprovalStatus.PENDING)
        .scalar()
        or 0
    )

    # Messages processed (placeholder - would need Message model query)
    # For now, return 0
    messages_processed = 0

    return {
        "quotes_7d": quotes_7d,
        "quotes_30d": quotes_30d,
        "approvals_pending": approvals_pending,
        "messages_processed": messages_processed,
    }


