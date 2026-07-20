"""
AI-Medikelizar — Admin Dashboard
=================================
Admin-only routes for viewing user stats, revenue, and subscription data.

All routes are protected by the require_admin dependency.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import config as app_config
from .auth import require_admin
from .database import get_db
from .models import UserModel, SubscriptionModel, QueryLogModel, UserOut

log = logging.getLogger("ai-medikelizar.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

CLERK_API_BASE = "https://api.clerk.com/v1"


# ═══════════════════════════════════════════════════════════
# Clerk API Helpers
# ═══════════════════════════════════════════════════════════


def _fetch_clerk_users(limit: int = 100, offset: int = 0) -> Optional[dict]:
    """
    Fetch users from Clerk's API.

    Returns a dict with 'data' (list of users) and 'total_count',
    or None if Clerk is not configured or the API call fails.
    """
    if not app_config.CLERK_SECRET_KEY:
        log.info("CLERK_SECRET_KEY not set — cannot fetch Clerk users")
        return None

    try:
        resp = requests.get(
            f"{CLERK_API_BASE}/users",
            params={"limit": limit, "offset": offset, "order_by": "-created_at"},
            headers={"Authorization": f"Bearer {app_config.CLERK_SECRET_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.warning(f"Failed to fetch Clerk users: {e}")
        return None


def _parse_clerk_user(u: dict) -> dict:
    """Convert a Clerk API user object to our response format."""
    email_addr_obj = (u.get("email_addresses") or [{}])[0]
    email = email_addr_obj.get("email_address", "")
    first = u.get("first_name", "") or ""
    last = u.get("last_name", "") or ""
    name = f"{first} {last}".strip()
    if not name:
        name = email

    # Convert Clerk's ms timestamp to datetime (UTC)
    created_ms = u.get("created_at", 0)
    created_at = datetime.utcfromtimestamp(created_ms / 1000) if created_ms else datetime.utcnow()

    is_admin = email.lower() in app_config.ADMIN_EMAILS

    return {
        "id": 0,  # Placeholder — no local DB id
        "clerk_id": u.get("id", ""),
        "email": email,
        "name": name,
        "is_admin": is_admin,
        "tier": "basic",  # No subscription data from Clerk alone
        "subscription_status": "",
        "created_at": created_at,
    }


# ═══════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════


@router.get("/dashboard")
async def dashboard(db: Session = Depends(get_db)):
    """
    Admin dashboard with aggregated stats.

    Pulls from local database when available. If the local DB
    is empty (e.g. on Vercel serverless), falls back to fetching
    user data directly from Clerk's API.
    """
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    # ── User stats from local DB ──
    total_users = db.query(func.count(UserModel.id)).scalar() or 0

    # ── If local DB is empty, fall back to Clerk API ──
    if total_users == 0:
        clerk_data = _fetch_clerk_users()
        if clerk_data:
            return _build_dashboard_from_clerk(clerk_data, now, seven_days_ago)

    # ── Local DB path (everything below here) ──
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

    users_by_tier = {}
    tier_counts = db.query(
        SubscriptionModel.tier, func.count(SubscriptionModel.id)
    ).filter(
        SubscriptionModel.status == "active",
    ).group_by(SubscriptionModel.tier).all()
    for tier, count in tier_counts:
        users_by_tier[tier] = count

    # ── Revenue (estimated from active subscriptions) ──
    total_revenue_cents = 0
    revenue_7d_cents = 0
    revenue_by_tier = {}

    for tier, count in tier_counts:
        if tier == "premium":
            price = app_config.PAYMOB_PREMIUM_PRICE_CENTS
        elif tier == "vip":
            price = app_config.PAYMOB_VIP_PRICE_CENTS
        else:
            price = 0
        revenue_by_tier[tier] = count * price
        total_revenue_cents += count * price

    recent_subs = db.query(SubscriptionModel).filter(
        SubscriptionModel.created_at >= seven_days_ago
    ).all()
    for sub in recent_subs:
        if sub.tier == "premium":
            revenue_7d_cents += app_config.PAYMOB_PREMIUM_PRICE_CENTS
        elif sub.tier == "vip":
            revenue_7d_cents += app_config.PAYMOB_VIP_PRICE_CENTS

    # ── Recent users from local DB ──
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
        "data_source": "local_db",
        "revenue_by_tier": {k: v for k, v in sorted(revenue_by_tier.items(), key=lambda x: -x[1])},
        "recent_users": [u.model_dump() for u in recent_users],
    }


def _build_dashboard_from_clerk(clerk_data: dict, now: datetime, seven_days_ago: datetime) -> dict:
    """Build dashboard response using Clerk API data when local DB is unavailable."""
    raw_users = clerk_data.get("data", [])
    total_count = clerk_data.get("total_count", len(raw_users))
    recent_users_raw = raw_users[:20]

    # Parse users
    recent_users = []
    new_users_7d = 0
    for u in raw_users:
        parsed = _parse_clerk_user(u)
        recent_users.append(parsed)

        # Check if created in last 7 days
        created_ms = u.get("created_at", 0)
        if created_ms:
            created_at = datetime.utcfromtimestamp(created_ms / 1000)
            if created_at >= seven_days_ago:
                new_users_7d += 1

    return {
        "total_users": total_count,
        "new_users_7d": new_users_7d,
        "total_queries": 0,
        "queries_7d": 0,
        "total_revenue_cents": 0,
        "revenue_7d_cents": 0,
        "active_subscriptions": 0,
        "users_by_tier": {"basic": total_count},
        "data_source": "clerk_api",
        "revenue_by_tier": {},
        "recent_users": recent_users,
    }


# ═══════════════════════════════════════════════════════════
# Users List
# ═══════════════════════════════════════════════════════════


@router.get("/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users with their subscription info."""
    users = db.query(UserModel).order_by(UserModel.created_at.desc()).all()

    # Fall back to Clerk API if local DB is empty
    if not users:
        clerk_data = _fetch_clerk_users(limit=500)
        if clerk_data:
            parsed = [_parse_clerk_user(u) for u in clerk_data.get("data", [])]
            return {"users": parsed, "data_source": "clerk_api"}

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

    return {"users": result, "data_source": "local_db"}
