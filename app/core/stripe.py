"""Stripe integration for subscriptions."""

import os
from typing import Optional
from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from app.db.models import Tenant
from app.domain.webhooks import check_idempotency, mark_processed
from app.settings import settings

# Initialize Stripe (will be set from settings)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def create_checkout_session(
    tenant_id: UUID,
    tenant_slug: str,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    """Create Stripe Checkout session for subscription.

    Args:
        tenant_id: Tenant UUID
        tenant_slug: Tenant slug for metadata
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect after cancellation

    Returns:
        Stripe Checkout Session object
    """
    session_params = {
        "payment_method_types": ["card"],
        "line_items": [
            {
                "price": os.getenv("STRIPE_PRICE_ID", ""),  # Set in env
                "quantity": 1,
            }
        ],
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "tenant_id": str(tenant_id),
            "tenant_slug": tenant_slug,
        },
    }

    if customer_id:
        session_params["customer"] = customer_id

    session = stripe.checkout.Session.create(**session_params)

    return session


def process_stripe_webhook(
    payload: bytes,
    signature: str,
    db: Session,
) -> dict:
    """Process Stripe webhook event.

    Args:
        payload: Raw webhook payload
        signature: Stripe signature header
        db: Database session

    Returns:
        Processing result dict
    """
    from app.domain.webhooks import verify_stripe_signature

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # Verify signature
    if not verify_stripe_signature(payload, signature, webhook_secret):
        return {"error": "Invalid signature"}

    event = stripe.Webhook.construct_event(payload, signature, webhook_secret)

    # Check idempotency
    event_id = event.get("id")
    if check_idempotency("stripe", event_id):
        return {"status": "already_processed"}

    # Process event
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        # Subscription activated
        session = data
        tenant_id = UUID(session["metadata"]["tenant_id"])
        tenant = db.query(Tenant).filter_by(id=tenant_id).first()
        if tenant:
            tenant.stripe_customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                tenant.stripe_subscription_id = subscription_id
                tenant.subscription_status = subscription["status"]
            db.commit()

    elif event_type == "customer.subscription.updated":
        # Subscription status updated
        subscription = data
        customer_id = subscription["customer"]
        tenant = db.query(Tenant).filter_by(stripe_customer_id=customer_id).first()
        if tenant:
            tenant.stripe_subscription_id = subscription["id"]
            tenant.subscription_status = subscription["status"]
            db.commit()

    elif event_type == "customer.subscription.deleted":
        # Subscription canceled
        subscription = data
        customer_id = subscription["customer"]
        tenant = db.query(Tenant).filter_by(stripe_customer_id=customer_id).first()
        if tenant:
            tenant.subscription_status = "canceled"
            db.commit()

    # Mark as processed
    mark_processed("stripe", event_id)

    return {"status": "processed", "event_type": event_type}


def is_subscription_active(tenant: Tenant) -> bool:
    """Check if tenant has active subscription.

    Args:
        tenant: Tenant object

    Returns:
        True if subscription is active, False otherwise
    """
    return tenant.subscription_status in ("active", "trialing")

