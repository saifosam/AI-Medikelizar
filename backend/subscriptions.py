"""
AI-Medikelizar — Subscription System
=====================================
Paymob payment gateway integration for subscription billing (Egypt/MENA).

Tiers:
  - Basic  (free):      5 queries/day
  - Premium (EGP/mo):   50 queries/day, faster priority, detailed citations
  - VIP    (EGP/mo):    unlimited queries, priority support, early access

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


# ── Subscription tier definitions ────────────────────
TIERS = {
    "basic": {
        "label": "Basic",
        "price_cents": 0,           # Free
        "queries_per_day": 5,
        "features": [
            "5 queries per day",
            "Standard response speed",
            "Basic source citations",
            "Email support",
        ],
    },
    "premium": {
        "label": "Premium",
        "price_cents": config.PAYMOB_PREMIUM_PRICE_CENTS,   # e.g. 2999 = 29.99 EGP
        "queries_per_day": 50,
        "features": [
            "50 queries per day",
            "Faster response priority",
            "Detailed source citations",
            "Priority email support",
        ],
    },
    "vip": {
        "label": "VIP",
        "price_cents": config.PAYMOB_VIP_PRICE_CENTS,       # e.g. 8999 = 89.99 EGP
        "queries_per_day": -1,  # unlimited
        "features": [
            "Unlimited queries",
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
        return True  # Allow anonymous

    used = get_queries_used_today(user, db)
    return used < queries_per_day


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
        tiers.append({
            "id": tier_id,
            "label": tier_info["label"],
            "price_cents": tier_info["price_cents"],
            "queries_per_day": tier_info["queries_per_day"],
            "features": tier_info["features"],
        })
    return {"tiers": tiers, "currency": "EGP"}


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
        "payment_type": sub.payment_type if sub else "one_time",
        "payment_method": sub.payment_method if sub else "",
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
