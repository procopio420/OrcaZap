"""Tenant metrics calculation."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Approval, ApprovalStatus, Conversation, ConversationState, Message, Quote, QuoteStatus


def get_tenant_metrics(db: Session, tenant_id: UUID) -> dict:
    """Calculate tenant metrics.

    Args:
        db: Database session
        tenant_id: Tenant UUID

    Returns:
        Dictionary with metrics:
        - quotes_7d: Number of quotes generated in last 7 days
        - quotes_30d: Number of quotes generated in last 30 days
        - quotes_today: Number of quotes generated today
        - approvals_pending: Number of pending approvals
        - messages_processed: Number of messages processed
        - conversions_won: Number of quotes/conversations won
        - conversions_lost: Number of quotes/conversations lost
        - conversion_rate: Conversion rate (won / (won + lost))
        - ai_usage_count: Number of times AI was used (approvals with "IA utilizada" reason)
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
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

    # Quotes today
    quotes_today = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id)
        .filter(Quote.created_at >= today_start)
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

    # Messages processed
    messages_processed = (
        db.query(func.count(Message.id))
        .filter(Message.tenant_id == tenant_id)
        .scalar()
        or 0
    )

    # Conversions (WON/LOST)
    # Count conversations with WON state
    conversions_won = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.tenant_id == tenant_id)
        .filter(Conversation.state == ConversationState.WON)
        .scalar()
        or 0
    )

    # Count conversations with LOST state
    conversions_lost = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.tenant_id == tenant_id)
        .filter(Conversation.state == ConversationState.LOST)
        .scalar()
        or 0
    )

    # Also count quotes with WON/LOST status
    quotes_won = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id)
        .filter(Quote.status == QuoteStatus.WON)
        .scalar()
        or 0
    )

    quotes_lost = (
        db.query(func.count(Quote.id))
        .filter(Quote.tenant_id == tenant_id)
        .filter(Quote.status == QuoteStatus.LOST)
        .scalar()
        or 0
    )

    # Total conversions (use max of conversation or quote counts)
    total_won = max(conversions_won, quotes_won)
    total_lost = max(conversions_lost, quotes_lost)

    # Conversion rate
    conversion_rate = 0.0
    if total_won + total_lost > 0:
        conversion_rate = (total_won / (total_won + total_lost)) * 100

    # AI usage count (approvals with "IA utilizada" in reason)
    ai_usage_count = (
        db.query(func.count(Approval.id))
        .filter(Approval.tenant_id == tenant_id)
        .filter(Approval.reason.ilike("%IA utilizada%"))
        .scalar()
        or 0
    )

    return {
        "quotes_7d": quotes_7d,
        "quotes_30d": quotes_30d,
        "quotes_today": quotes_today,
        "approvals_pending": approvals_pending,
        "messages_processed": messages_processed,
        "conversions_won": total_won,
        "conversions_lost": total_lost,
        "conversion_rate": round(conversion_rate, 1),
        "ai_usage_count": ai_usage_count,
    }




