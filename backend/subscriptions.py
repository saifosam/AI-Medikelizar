"""
AI-Medikelizar — Subscription System
=====================================
Stripe Checkout integration for subscription billing.

Tiers:
  - Basic  (free):      5 queries/day
  - Premium ($9.99/mo): 50 queries/day, faster priority, detailed citations
  - VIP    ($29.99/mo): unlimited queries, priority support, early access

Flow:
  1. User clicks "Subscribe" on pricing page
  2. Frontend calls POST /api/subscriptions/create-checkout
  3. Backend creates a Stripe Checkout Session, returns the URL
  4. User completes payment on Stripe's hosted page
  5. Stripe redirects back to our app
  6. Stripe sends webhook events to sync subscription status
"""

import logging
from datetime import datetime, date
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import config
from .auth import require_user, get_current_user
from .database import get_db
from .models import UserModel, SubscriptionModel, QueryLogModel

log = logging.getLogger("ai-medikelizar.subscriptions")

# ── Initialize Stripe ────────────────────────────────
stripe.api_key = config.STRIPE_SECRET_KEY

# ── Subscription tier definitions ────────────────────
TIERS = {
    "basic": {
        "label": "Basic",
        "price_cents": 0,
        "queries_per_day": 5,
        "stripe_price_id": "",  # Free tier — no Stripe price
        "features": [
            "5 queries per day",
            "Standard response speed",
            "Basic source citations",
            "Email support",
        ],
    },
    "premium": {
        "label": "Premium",
        "price_cents": 999,  # $9.99
        "queries_per_day": 50,
        "stripe_price_id": config.STRIPE_PREMIUM_PRICE_ID,
        "features": [
            "50 queries per day",
            "Faster response priority",
            "Detailed source citations",
            "Priority email support",
        ],
    },
    "vip": {
        "label": "VIP",
        "price_cents": 2999,  # $29.99
        "queries_per_day": -1,  # unlimited
        "stripe_price_id": config.STRIPE_VIP_PRICE_ID,
        "features": [
            "Unlimited queries",
            "Fastest response priority",
            "Full source citations with abstracts",
            "Priority support (email + chat)",
            "Early access to new features",
        ],
    },
}


def get_tier_limits(tier: str) -> dict:
    """Get the quota limits for a given tier."""
    return TIERS.get(tier, TIERS["basic"])


def get_user_tier(user: Optional[UserModel], db: Session) -> str:
    """Get the user's current subscription tier."""
    if not user:
        return "basic"
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
        SubscriptionModel.status == "active",
    ).first()
    if sub and sub.tier in TIERS:
        return sub.tier
    return "basic"


def get_queries_used_today(user: UserModel, db: Session) -> int:
    """Count queries used by the user today."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    return db.query(QueryLogModel).filter(
        QueryLogModel.user_id == user.id,
        QueryLogModel.created_at >= today_start,
    ).count()


def check_query_limit(user: Optional[UserModel], db: Session) -> bool:
    """
    Check if the user can make a query based on their tier limit.
    Returns True if allowed, False if over the limit.
    """
    tier = get_user_tier(user, db)
    limits = get_tier_limits(tier)
    queries_per_day = limits["queries_per_day"]

    # Unlimited tier
    if queries_per_day == -1:
        return True

    if not user:
        # Anonymous: enforce basic tier limit
        return True  # Allow for now; track anonymously

    used = get_queries_used_today(user, db)
    return used < queries_per_day


# ═══════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/pricing")
async def get_pricing():
    """Return the subscription tier definitions for the pricing page."""
    tiers = []
    for tier_id, tier_info in TIERS.items():
        tiers.append({
            "id": tier_id,
            "label": tier_info["label"],
            "price_cents": tier_info["price_cents"],
            "queries_per_day": tier_info["queries_per_day"],
            "features": tier_info["features"],
        })
    return {"tiers": tiers}


@router.get("/status")
async def get_subscription_status(
    user: Optional[UserModel] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's current subscription details."""
    tier = get_user_tier(user, db)
    limits = get_tier_limits(tier)
    queries_used = 0
    queries_limit = limits["queries_per_day"]

    if user:
        queries_used = get_queries_used_today(user, db)

    sub = None
    if user:
        sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == user.id,
        ).order_by(SubscriptionModel.created_at.desc()).first()

    return {
        "tier": tier,
        "status": sub.status if sub else "active",
        "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        "queries_used_today": queries_used,
        "queries_limit": queries_limit,
    }


@router.post("/create-checkout")
async def create_checkout_session(
    request: Request,
    user: UserModel = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout Session for subscription purchase or upgrade.

    Expects JSON body: { "tier": "premium" | "vip" }
    """
    body = await request.json()
    tier = body.get("tier", "")

    if tier not in TIERS or tier == "basic":
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'premium' or 'vip'.")

    tier_info = TIERS[tier]
    price_id = tier_info["stripe_price_id"]

    if not price_id:
        raise HTTPException(status_code=400, detail=f"No Stripe price configured for tier '{tier}'.")

    # Get or create Stripe customer
    existing_sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
    ).first()

    stripe_customer_id = existing_sub.stripe_customer_id if existing_sub else ""

    if not stripe_customer_id:
        # Create a new Stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name or user.email,
            metadata={"clerk_user_id": user.clerk_id},
        )
        stripe_customer_id = customer.id

    # Determine success/cancel URLs
    base_url = str(request.base_url).rstrip("/")
    success_url = f"{base_url}/#pricing?checkout=success"
    cancel_url = f"{base_url}/#pricing?checkout=cancelled"

    try:
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "clerk_user_id": user.clerk_id,
                    "tier": tier,
                },
            },
        )

        return {"url": session.url}
    except stripe.error.StripeError as e:
        log.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/create-portal-session")
async def create_portal_session(
    request: Request,
    user: UserModel = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    existing_sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
    ).first()

    if not existing_sub or not existing_sub.stripe_customer_id:
        # No subscription yet — redirect to pricing page
        base_url = str(request.base_url).rstrip("/")
        return {"url": f"{base_url}/#pricing"}

    base_url = str(request.base_url).rstrip("/")

    try:
        session = stripe.billing_portal.Session.create(
            customer=existing_sub.stripe_customer_id,
            return_url=f"{base_url}/#pricing",
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        log.error(f"Stripe portal error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")


# ═══════════════════════════════════════════════════════════
# Stripe Webhook
# ═══════════════════════════════════════════════════════════

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive Stripe webhook events to sync subscription status.

    Key events:
      - checkout.session.completed: initial subscription created
      - invoice.payment_succeeded: recurring payment succeeded
      - invoice.payment_failed: payment failed (mark as past_due)
      - customer.subscription.updated: subscription changed
      - customer.subscription.deleted: subscription cancelled
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        log.warning("Stripe webhook: invalid payload")
        return {"status": "ignored"}, 400
    except stripe.error.SignatureVerificationError:
        log.warning("Stripe webhook: invalid signature")
        return {"status": "ignored"}, 400

    event_type = event.type
    log.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event.data.object, db)
    elif event_type == "invoice.payment_succeeded":
        _handle_invoice_succeeded(event.data.object, db)
    elif event_type == "invoice.payment_failed":
        _handle_invoice_failed(event.data.object, db)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(event.data.object, db)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event.data.object, db)

    return {"status": "received"}


def _get_or_create_subscription(user_id: int, db: Session) -> SubscriptionModel:
    """Get existing subscription for a user, or create a new one."""
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user_id,
    ).first()
    if not sub:
        sub = SubscriptionModel(user_id=user_id)
        db.add(sub)
    return sub


def _handle_checkout_completed(session, db: Session):
    """Handle initial subscription purchase."""
    metadata = session.get("metadata", {})
    user_id_str = metadata.get("user_id", "")
    tier = metadata.get("tier", "basic")

    if not user_id_str:
        log.warning("Checkout completed without user_id in metadata")
        return

    user_id = int(user_id_str)
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        log.warning(f"Checkout completed for unknown user: {user_id}")
        return

    subscription = session.get("subscription", "")
    customer = session.get("customer", "")

    sub = _get_or_create_subscription(user_id, db)
    sub.tier = tier
    sub.status = "active"
    sub.stripe_customer_id = customer
    sub.stripe_subscription_id = subscription
    sub.current_period_start = datetime.utcnow()

    # Calculate period end (default 1 month)
    from datetime import timedelta
    sub.current_period_end = datetime.utcnow() + timedelta(days=30)
    sub.updated_at = datetime.utcnow()

    db.commit()
    log.info(f"Subscription activated for user {user.email}: {tier}")


def _handle_invoice_succeeded(invoice, db: Session):
    """Handle successful recurring payment."""
    subscription_id = invoice.get("subscription", "")
    customer = invoice.get("customer", "")
    period_start = invoice.get("period_start", None)
    period_end = invoice.get("period_end", None)

    if not subscription_id:
        return

    # Find the subscription by Stripe subscription ID
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.stripe_subscription_id == subscription_id,
    ).first()
    if not sub:
        log.warning(f"Invoice succeeded for unknown subscription: {subscription_id}")
        return

    sub.status = "active"
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start)
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end)
    sub.updated_at = datetime.utcnow()
    db.commit()
    log.info(f"Subscription renewed: {sub.id}")


def _handle_invoice_failed(invoice, db: Session):
    """Handle failed payment — mark subscription as past_due."""
    subscription_id = invoice.get("subscription", "")
    if not subscription_id:
        return

    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.stripe_subscription_id == subscription_id,
    ).first()
    if sub:
        sub.status = "past_due"
        sub.updated_at = datetime.utcnow()
        db.commit()
        log.warning(f"Subscription past_due: {sub.id}")


def _handle_subscription_updated(subscription, db: Session):
    """Handle subscription changes (upgrade, downgrade, etc.)."""
    sub_id = subscription.get("id", "")
    status = subscription.get("status", "")
    items = subscription.get("items", {}).get("data", [])
    metadata = subscription.get("metadata", {})

    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.stripe_subscription_id == sub_id,
    ).first()
    if not sub:
        log.warning(f"Subscription updated for unknown: {sub_id}")
        return

    # Map Stripe status
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "cancelled",
        "incomplete": "incomplete",
        "incomplete_expired": "cancelled",
        "trialing": "active",
        "unpaid": "past_due",
    }
    sub.status = status_map.get(status, "active")

    # Try to get tier from metadata or item price
    tier = metadata.get("tier", "")
    if not tier and items:
        price_id = items[0].get("price", {}).get("id", "")
        # Map price ID to tier
        if price_id == config.STRIPE_PREMIUM_PRICE_ID:
            tier = "premium"
        elif price_id == config.STRIPE_VIP_PRICE_ID:
            tier = "vip"

    if tier:
        sub.tier = tier
    sub.updated_at = datetime.utcnow()
    db.commit()
    log.info(f"Subscription updated: {sub.id} → {sub.tier} ({sub.status})")


def _handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation."""
    sub_id = subscription.get("id", "")
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.stripe_subscription_id == sub_id,
    ).first()
    if sub:
        sub.status = "cancelled"
        sub.updated_at = datetime.utcnow()
        db.commit()
        log.info(f"Subscription cancelled: {sub.id}")
