"""
AI-Medikelizar — Flexible Subscription System
===============================================
Tiered subscriptions with adjustable daily limits and EGP pricing.

Tiers:
  - Basic  (free):      5 queries/day, fixed
  - Premium (EGP/mo):   10–25 queries/day, user-adjustable
  - VIP    (EGP/mo):    25–60 queries/day, user-adjustable

Pricing Formula:
  Base cost per query:  0.15 EGP
  Monthly cost = daily_limit × 30 × 0.15 × margin_multiplier
  - Premium margin: 1.33×  →  59.85 = round(10×30×0.15×1.33)
  - VIP margin:     1.50×
  Result rounded to nearest clean number.

Payment Flow:
  1. User clicks "Subscribe" on pricing page
  2. Frontend calls POST /api/subscriptions/create-checkout
  3. Backend creates a Paymob Payment Intention, returns the checkout URL
  4. User completes payment on Paymob's hosted unified checkout page
  5. Paymob redirects back to our app on success/cancellation
  6. Paymob sends webhook events to sync subscription status
"""

import hashlib
import hmac
import json
import logging
import math
from datetime import datetime, date, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import config
from .auth import require_user, get_current_user
from .database import get_db
from .models import UserModel, SubscriptionModel, QueryLogModel

log = logging.getLogger("ai-medikelizar.subscriptions")

PAYMOB_BASE = "https://accept.paymob.com"


# ── Pricing constants ────────────────────────────────
COST_PER_QUERY_EGP = 0.15        # Base cost per query in EGP
DAYS_PER_MONTH = 30
PREMIUM_MARGIN = 1.33             # Premium margin multiplier
VIP_MARGIN = 1.50                 # VIP margin multiplier

# ── Tier ranges (min/max daily limit) ────────────────
TIER_RANGES = {
    "basic":    {"min": 5,  "max": 5},
    "premium":  {"min": 10, "max": 25},
    "vip":      {"min": 25, "max": 60},
}


def calculate_price_cents(daily_limit: int, tier: str) -> int:
    """
    Calculate monthly price in EGP cents for a given daily limit and tier.
    Formula: daily_limit × 30 × 0.15 EGP × margin, rounded to clean number.
    """
    if tier == "basic" or daily_limit <= 0:
        return 0
    margin = PREMIUM_MARGIN if tier == "premium" else VIP_MARGIN
    raw = daily_limit * DAYS_PER_MONTH * COST_PER_QUERY_EGP * margin
    # Round to a "clean" number (nearest 5 or 10 depending on magnitude)
    raw_egp = raw  # price in EGP
    if raw_egp < 100:
        rounded = round(raw_egp / 5) * 5       # nearest 5 EGP
    else:
        rounded = round(raw_egp / 10) * 10     # nearest 10 EGP
    # Convert to cents
    return int(round(rounded * 100))


# ── Subscription tier definitions (backend) ──────────
TIERS = {
    "basic": {
        "label": "Basic",
        "price_cents": 0,           # Free
        "daily_limit_default": 5,
        "daily_limit_min": 5,
        "daily_limit_max": 5,
        "features": [
            "5 queries per day",
            "Standard response speed",
            "Basic source citations",
            "Email support",
        ],
    },
    "premium": {
        "label": "Premium",
        "price_cents": calculate_price_cents(15, "premium"),  # Default shown on pricing page
        "daily_limit_default": 15,
        "daily_limit_min": 10,
        "daily_limit_max": 25,
        "features": [
            "10–25 queries per day (adjustable)",
            "Faster response priority",
            "Detailed source citations",
            "Priority email support",
        ],
    },
    "vip": {
        "label": "VIP",
        "price_cents": calculate_price_cents(40, "vip"),  # Default shown on pricing page
        "daily_limit_default": 40,
        "daily_limit_min": 25,
        "daily_limit_max": 60,
        "features": [
            "25–60 queries per day (adjustable)",
            "Fastest response priority",
            "Full source citations with abstracts",
            "Priority support (email + chat)",
            "Early access to new features",
        ],
    },
}

# ── Cache for Paymob auth token (valid 1 hour) ──────
_paymob_token: str = ""
_paymob_token_expiry: datetime = datetime.min


# ═══════════════════════════════════════════════════════════
# Paymob API Helpers
# ═══════════════════════════════════════════════════════════


def _get_paymob_token() -> str:
    """Get an auth token from Paymob API (cached with expiry)."""
    global _paymob_token, _paymob_token_expiry

    if _paymob_token and datetime.utcnow() < _paymob_token_expiry:
        return _paymob_token

    if not config.PAYMOB_API_KEY:
        log.warning("PAYMOB_API_KEY not configured")
        return ""

    try:
        resp = requests.post(
            f"{PAYMOB_BASE}/api/auth/tokens",
            json={"api_key": config.PAYMOB_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _paymob_token = data.get("token", "")
        # Token expires in 1 hour — cache for 55 minutes
        _paymob_token_expiry = datetime.utcnow() + timedelta(minutes=55)
        return _paymob_token
    except requests.RequestException as e:
        log.error(f"Failed to get Paymob token: {e}")
        return ""


def create_payment_intention(
    amount_cents: int,
    currency: str,
    user: UserModel,
    tier: str,
    base_url: str,
) -> dict:
    """
    Create a Paymob Payment Intention and return the checkout details.

    Returns: { "client_secret": "...", "id": 12345, "checkout_url": "..." }
    Raises HTTPException on failure.
    """
    token = _get_paymob_token()
    if not token:
        raise HTTPException(status_code=500, detail="Payment service not configured")

    # Build payment methods list from configured integration IDs
    payment_methods = []
    if config.PAYMOB_INTEGRATION_ID_CARDS:
        try:
            payment_methods.append(int(config.PAYMOB_INTEGRATION_ID_CARDS))
        except ValueError:
            pass
    if config.PAYMOB_INTEGRATION_ID_WALLETS:
        try:
            payment_methods.append(int(config.PAYMOB_INTEGRATION_ID_WALLETS))
        except ValueError:
            pass

    if not payment_methods:
        raise HTTPException(
            status_code=500,
            detail="No payment methods configured. Set PAYMOB_INTEGRATION_ID env vars."
        )

    # Split user name into first/last
    name_parts = (user.name or user.email).strip().split(" ", 1)
    first_name = name_parts[0] if name_parts else "User"
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Convert cents to EGP (Paymob accepts decimal amounts)
    amount = amount_cents / 100.0

    intention_data = {
        "amount": amount,
        "currency": currency,
        "payment_methods": payment_methods,
        "billing_data": {
            "first_name": first_name,
            "last_name": last_name,
            "email": user.email,
            "phone_number": "01000000000",
            "apartment": "NA",
            "floor": "NA",
            "street": "NA",
            "building": "NA",
            "city": "NA",
            "country": "EG",
            "state": "NA",
        },
        "customer": {
            "first_name": first_name,
            "last_name": last_name,
            "email": user.email,
        },
        "notification_url": f"{base_url}/api/subscriptions/webhook",
        "redirection_url": f"{base_url}/#pricing?checkout=success",
        "custom_data": {
            "user_id": str(user.id),
            "clerk_id": user.clerk_id,
            "tier": tier,
        },
    }

    try:
        resp = requests.post(
            f"{PAYMOB_BASE}/v1/intention/",
            json=intention_data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        intention_id = data.get("id", "")
        client_secret = data.get("client_secret", "")

        # Build the unified checkout URL
        checkout_url = (
            f"{PAYMOB_BASE}/unifiedcheckout/"
            f"?publicKey={config.PAYMOB_PUBLIC_KEY}"
            f"&clientSecret={client_secret}"
        )

        return {
            "id": intention_id,
            "client_secret": client_secret,
            "checkout_url": checkout_url,
        }
    except requests.RequestException as e:
        log.error(f"Paymob intention creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment session")


def verify_webhook_signature(payload: bytes, hmac_header: str) -> bool:
    """
    Verify Paymob webhook HMAC-SHA512 signature.

    Paymob calculates the HMAC over the raw request body using the webhook secret.
    """
    if not config.PAYMOB_WEBHOOK_SECRET:
        log.warning("PAYMOB_WEBHOOK_SECRET not set — skipping webhook verification")
        return True

    if not hmac_header:
        log.warning("Paymob webhook: missing HMAC header")
        return False

    expected = hmac.new(
        config.PAYMOB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(expected, hmac_header)


# ═══════════════════════════════════════════════════════════
# Subscription Logic
# ═══════════════════════════════════════════════════════════


def get_tier_limits(tier: str) -> dict:
    """Get the quota limits for a given tier. Returns daily_limit bounds."""
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


def get_user_daily_limit(user: Optional[UserModel], db: Session) -> int:
    """
    Get the user's effective daily query limit.
    - Basic: fixed 5/day
    - Premium/VIP: stored daily_limit, or tier default if not set
    """
    if not user:
        return 5  # Anonymous basic
    tier = get_user_tier(user, db)
    tier_info = TIERS.get(tier, TIERS["basic"])
    if tier == "basic":
        return tier_info["daily_limit_default"]
    # For paid tiers, check stored daily_limit
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
        SubscriptionModel.status == "active",
    ).first()
    if sub and sub.daily_limit is not None:
        return max(tier_info["daily_limit_min"], min(sub.daily_limit, tier_info["daily_limit_max"]))
    return tier_info["daily_limit_default"]


def get_queries_used_today(user: UserModel, db: Session) -> int:
    """Count queries used by the user today (midnight-reset window)."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    return db.query(QueryLogModel).filter(
        QueryLogModel.user_id == user.id,
        QueryLogModel.created_at >= today_start,
    ).count()


def check_query_limit(user: Optional[UserModel], db: Session) -> bool:
    """
    Check if the user can make a query based on their daily limit.
    Returns True if allowed, False if over the limit.
    """
    if not user:
        return True  # Allow anonymous
    daily_limit = get_user_daily_limit(user, db)
    used = get_queries_used_today(user, db)
    return used < daily_limit


def get_user_payment_type(user: UserModel, db: Session) -> str:
    """Check if user has a saved card token for recurring payments."""
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
        SubscriptionModel.paymob_card_token != "",
        SubscriptionModel.paymob_card_token.isnot(None),
    ).first()
    return "recurring" if sub else "one_time"


# ═══════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/pricing")
async def get_pricing():
    """Return the subscription tier definitions for the pricing page."""
    tiers = []
    for tier_id, tier_info in TIERS.items():
        daily_limit = tier_info["daily_limit_default"]
        tiers.append({
            "id": tier_id,
            "label": tier_info["label"],
            "price_cents": calculate_price_cents(daily_limit, tier_id),
            "daily_limit": daily_limit,
            "daily_limit_min": tier_info["daily_limit_min"],
            "daily_limit_max": tier_info["daily_limit_max"],
            "features": tier_info["features"],
        })
    return {"tiers": tiers, "currency": "EGP"}


@router.get("/pricing/calculate")
async def calculate_price(tier: str = "premium", daily_limit: int = 15):
    """
    Live price calculation for the pricing slider.
    Query params: tier, daily_limit
    Returns: { price_cents, daily_limit, tier }
    """
    if tier not in TIERS or tier == "basic":
        return {"price_cents": 0, "daily_limit": 5, "tier": "basic"}
    tier_info = TIERS[tier]
    clamped = max(tier_info["daily_limit_min"], min(daily_limit, tier_info["daily_limit_max"]))
    price = calculate_price_cents(clamped, tier)
    return {"price_cents": price, "daily_limit": clamped, "tier": tier}


@router.get("/status")
async def get_subscription_status(
    user: Optional[UserModel] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's current subscription details with daily limit info."""
    tier = get_user_tier(user, db)
    daily_limit = get_user_daily_limit(user, db) if user else 5
    queries_used = 0
    queries_limit = daily_limit

    if user:
        queries_used = get_queries_used_today(user, db)

    sub = None
    if user:
        sub = db.query(SubscriptionModel).filter(
            SubscriptionModel.user_id == user.id,
        ).order_by(SubscriptionModel.created_at.desc()).first()

    # Get tier range info
    tier_info = TIERS.get(tier, TIERS["basic"])

    return {
        "tier": tier,
        "status": sub.status if sub else "active",
        "payment_type": sub.payment_type if sub else "one_time",
        "payment_method": sub.payment_method if sub else "",
        "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        "queries_used_today": queries_used,
        "queries_limit": queries_limit,
        "daily_limit": daily_limit,
        "daily_limit_min": tier_info["daily_limit_min"],
        "daily_limit_max": tier_info["daily_limit_max"],
        "price_cents": calculate_price_cents(daily_limit, tier),
    }


@router.get("/credits")
async def get_credits(
    user: Optional[UserModel] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return lightweight credit/usage info for real-time UI indicators.
    Called frequently (after each query) — keep it fast.
    """
    if not user:
        return {"used": 0, "limit": 5, "remaining": 5, "tier": "basic"}
    tier = get_user_tier(user, db)
    daily_limit = get_user_daily_limit(user, db)
    used = get_queries_used_today(user, db)
    remaining = max(0, daily_limit - used)
    return {
        "used": used,
        "limit": daily_limit,
        "remaining": remaining,
        "tier": tier,
    }


@router.post("/update-limit")
async def update_daily_limit(
    request: Request,
    user: UserModel = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Update the user's chosen daily query limit within their tier range.
    Expects JSON body: { "daily_limit": 20 }
    Only works for premium/vip tiers.
    Resets usage count so the new limit takes effect immediately.
    """
    body = await request.json()
    new_limit = body.get("daily_limit")
    if not isinstance(new_limit, int) or new_limit < 1:
        raise HTTPException(status_code=400, detail="daily_limit must be a positive integer")

    tier = get_user_tier(user, db)
    if tier not in TIERS or tier == "basic":
        raise HTTPException(status_code=400, detail="Cannot change daily limit on Basic tier")

    tier_info = TIERS[tier]
    clamped = max(tier_info["daily_limit_min"], min(new_limit, tier_info["daily_limit_max"]))

    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
        SubscriptionModel.status == "active",
    ).first()
    if not sub:
        raise HTTPException(status_code=400, detail="No active subscription found")

    sub.daily_limit = clamped
    sub.updated_at = datetime.utcnow()
    db.commit()

    new_price = calculate_price_cents(clamped, tier)
    log.info(f"User {user.email} changed daily limit to {clamped} ({tier}, {new_price} EGP cents)")

    return {
        "tier": tier,
        "daily_limit": clamped,
        "price_cents": new_price,
    }


@router.post("/create-checkout")
async def create_checkout_session(
    request: Request,
    user: UserModel = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Create a Paymob Payment Intention for subscription purchase.

    Expects JSON body: { "tier": "premium" | "vip" }
    """
    body = await request.json()
    tier = body.get("tier", "")

    if tier not in TIERS or tier == "basic":
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'premium' or 'vip'.")

    tier_info = TIERS[tier]
    amount_cents = tier_info["price_cents"]

    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Free tier cannot be purchased.")

    base_url = str(request.base_url).rstrip("/")

    # Create Paymob payment intention
    result = create_payment_intention(
        amount_cents=amount_cents,
        currency="EGP",
        user=user,
        tier=tier,
        base_url=base_url,
    )

    # Save the intention ID to the subscription record
    sub = db.query(SubscriptionModel).filter(
        SubscriptionModel.user_id == user.id,
    ).first()
    if not sub:
        sub = SubscriptionModel(user_id=user.id)
        db.add(sub)

    sub.paymob_intention_id = str(result["id"])
    sub.tier = tier
    sub.status = "incomplete"
    sub.payment_type = get_user_payment_type(user, db)
    sub.updated_at = datetime.utcnow()
    db.commit()

    log.info(f"Checkout created for user {user.email}: {tier} ({amount_cents} EGP cents)")

    return {"url": result["checkout_url"]}


@router.post("/create-portal-session")
async def create_portal_session(
    request: Request,
    user: UserModel = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Redirect user to the subscription management page (pricing page for now)."""
    base_url = str(request.base_url).rstrip("/")
    return {"url": f"{base_url}/#pricing"}


# ═══════════════════════════════════════════════════════════
# Paymob Webhook
# ═══════════════════════════════════════════════════════════

@router.post("/webhook")
async def paymob_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive Paymob webhook events to sync subscription status.

    Key events:
      - transaction.processed:    Payment succeeded (new or recurring)
      - transaction.failed:       Payment failed
      - transaction.voided:       Payment voided/refunded
    """
    payload = await request.body()
    hmac_header = request.headers.get("hmac", "")

    # Verify HMAC signature
    if not verify_webhook_signature(payload, hmac_header):
        log.warning("Paymob webhook: invalid HMAC signature")
        return {"status": "ignored"}

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        log.warning("Paymob webhook: invalid JSON payload")
        return {"status": "ignored"}

    event_type = data.get("type", "")

    if event_type == "transaction.processed":
        _handle_transaction_processed(data.get("obj", {}), db)
    elif event_type == "transaction.failed":
        _handle_transaction_failed(data.get("obj", {}), db)
    elif event_type == "transaction.voided":
        _handle_transaction_voided(data.get("obj", {}), db)
    else:
        log.info(f"Paymob webhook: unhandled event type '{event_type}'")

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


def _handle_transaction_processed(obj: dict, db: Session):
    """Handle successful payment — activate subscription."""
    success = obj.get("success", False)
    if not success:
        return

    # Extract custom data passed during intention creation
    data = obj.get("data") or {}
    custom_data = data.get("custom_data") or {}
    intention_id = data.get("intention_id", "")

    user_id_str = custom_data.get("user_id", "")
    tier = custom_data.get("tier", "basic")

    if not user_id_str:
        log.warning("Transaction processed without user_id in custom_data")
        return

    user_id = int(user_id_str)
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        log.warning(f"Transaction processed for unknown user: {user_id}")
        return

    # Extract payment details
    card_token = obj.get("card_token", "") or obj.get("saved_card_token", "")
    card_num = obj.get("card_num", "")
    payment_method = "card" if card_num else "wallet"
    order_id = str(obj.get("order", {}).get("id", "")) if isinstance(obj.get("order"), dict) else ""

    sub = _get_or_create_subscription(user_id, db)
    sub.tier = tier
    sub.status = "active"
    sub.payment_method = payment_method
    sub.paymob_intention_id = intention_id or sub.paymob_intention_id
    sub.paymob_order_id = order_id or sub.paymob_order_id
    sub.current_period_start = datetime.utcnow()
    sub.current_period_end = datetime.utcnow() + timedelta(days=30)

    # Save card token for recurring payments
    if card_token:
        sub.paymob_card_token = card_token
        sub.payment_type = "recurring"

    sub.updated_at = datetime.utcnow()
    db.commit()

    log.info(
        f"Subscription activated for {user.email}: {tier} "
        f"({payment_method}, recurring={bool(card_token)})"
    )


def _handle_transaction_failed(obj: dict, db: Session):
    """Handle failed payment."""
    data = obj.get("data", {}) or {}
    custom_data = data.get("custom_data", {}) or {}
    user_id_str = custom_data.get("user_id", "")

    if user_id_str:
        user_id = int(user_id_str)
        sub = _get_or_create_subscription(user_id, db)
        if sub.status == "active":
            sub.status = "past_due"
            sub.updated_at = datetime.utcnow()
            db.commit()
            log.warning(f"Subscription past_due due to failed payment: user {user_id}")


def _handle_transaction_voided(obj: dict, db: Session):
    """Handle voided/refunded payment — cancel subscription."""
    data = obj.get("data", {}) or {}
    custom_data = data.get("custom_data", {}) or {}
    user_id_str = custom_data.get("user_id", "")

    if user_id_str:
        user_id = int(user_id_str)
        sub = _get_or_create_subscription(user_id, db)
        sub.status = "cancelled"
        sub.updated_at = datetime.utcnow()
        db.commit()
        log.info(f"Subscription cancelled due to void/refund: user {user_id}")
