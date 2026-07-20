"""
AI-Medikelizar — Admin Dashboard
=================================
Admin-only routes for viewing user stats, revenue, and subscription data.

All routes are protected by the require_admin dependency.
"""

import logging
from datetime import datetime, date, timedelta

import stripe
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import config
from .auth import require_admin
from .database import get_db
from .models import UserModel, SubscriptionModel, QueryLogModel, PageViewModel, UserOut

log = logging.getLogger("ai-medikelizar.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/dashboard")
async def dashboard(db: Session = Depends(get_db)):
    """
    Admin dashboard with aggregated stats.

    Pulls:
      - User counts (total, new in 7 days)
      - Query counts (total, in 7 days)
      - Real revenue from Stripe API
      - Subscription counts by tier
      - Recent users list
    """
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # ── User stats ──
    total_users = db.query(func.count(UserModel.id)).scalar() or 0
    new_users_7d = db.query(func.count(UserModel.id)).filter(
        UserModel.created_at >= seven_days_ago
    ).scalar() or 0

    # ── Query stats ──
    total_queries = db.query(func.count(QueryLogModel.id)).scalar() or 0
    queries_7d = db.query(func.count(QueryLogModel.id)).filter(
        QueryLogModel.created_at >= seven_days_ago
    ).scalar() or 0

    # ── Subscription stats ──
    active_subs = db.query(func.count(SubscriptionModel.id)).filter(
        SubscriptionModel.status == "active",
    ).scalar() or 0

    # Users by tier
    users_by_tier = {}
    tier_counts = db.query(
        SubscriptionModel.tier, func.count(SubscriptionModel.id)
    ).filter(
        SubscriptionModel.status == "active",
    ).group_by(SubscriptionModel.tier).all()
    for tier, count in tier_counts:
        users_by_tier[tier] = count

    # ── Revenue from Stripe API (real data, not mocked) ──
    total_revenue_cents = 0
    revenue_7d_cents = 0
    revenue_by_tier = {}

    try:
        # All-time revenue from paid invoices
        seven_days_ago_ts = int((now - timedelta(days=7)).timestamp())
        all_invoices = stripe.Invoice.list(
            status="paid",
            limit=100,
            expand=["data.subscription"],
        )

        for inv in all_invoices.auto_paging_iter():
            amount = inv.get("amount_paid", 0) or 0
            total_revenue_cents += amount

            # Check if this invoice was created in the last 7 days
            created = inv.get("created", 0)
            if created >= seven_days_ago_ts:
                revenue_7d_cents += amount

            # Try to determine tier from subscription metadata
            sub = inv.get("subscription")
            tier = "basic"
            if sub and hasattr(sub, "metadata"):
                tier = sub.metadata.get("tier", "premium")
            elif sub and isinstance(sub, str):
                # String reference — try to fetch it
                pass

            revenue_by_tier[tier] = revenue_by_tier.get(tier, 0) + amount

    except stripe.error.StripeError as e:
        log.warning(f"Could not fetch Stripe revenue data: {e}")

    # ── Recent users ──
    recent_users_raw = db.query(UserModel).order_by(
        UserModel.created_at.desc()
    ).limit(20).all()

    recent_users = []
    for u in recent_users_raw:
        sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == u.id,
        ).order_by(SubscriptionModel.created_at.desc()).first()
        recent_users.append(UserOut(
            id=u.id,
            clerk_id=u.clerk_id,
            email=u.email,
            name=u.name,
            is_admin=u.is_admin,
            tier=sub.tier if sub else "basic",
            subscription_status=sub.status if sub else "",
            created_at=u.created_at,
        ))

    return {
        "total_users": total_users,
        "new_users_7d": new_users_7d,
        "total_queries": total_queries,
        "queries_7d": queries_7d,
        "total_revenue_cents": total_revenue_cents,
        "revenue_7d_cents": revenue_7d_cents,
        "active_subscriptions": active_subs,
        "users_by_tier": users_by_tier,
        "revenue_by_tier": {k: v for k, v in sorted(revenue_by_tier.items(), key=lambda x: -x[1])},
        "recent_users": [u.model_dump() for u in recent_users],
    }


@router.get("/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users with their subscription info."""
    users = db.query(UserModel).order_by(UserModel.created_at.desc()).all()

    result = []
    for u in users:
        sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == u.id,
        ).order_by(SubscriptionModel.created_at.desc()).first()
        result.append({
            "id": u.id,
            "clerk_id": u.clerk_id,
            "email": u.email,
            "name": u.name,
            "is_admin": u.is_admin,
            "tier": sub.tier if sub else "basic",
            "subscription_status": sub.status if sub else "",
            "created_at": u.created_at.isoformat(),
        })

    return {"users": result}
