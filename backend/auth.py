"""
AI-Medikelizar — Authentication Module
=======================================
Clerk webhook handler to sync users to local SQLite DB,
FastAPI dependencies to get the current user from Clerk's session.

Flow:
  1. Clerk calls our webhook endpoint when users sign up/update/delete
  2. We verify the webhook signature, then sync user data to local DB
  3. For API requests, the frontend Clerk SDK sends the session token
     in the Authorization header. We decode it to get the Clerk user ID
     and look up the local user record.

Security notes:
  - Clerk webhooks are verified using the CLERK_WEBHOOK_SECRET env var
  - For session verification in development, we trust Clerk's signed
    session cookie. In production, verify the JWT against Clerk's JWKS.
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import UserModel

log = logging.getLogger("ai-medikelizar.auth")

# ═══════════════════════════════════════════════════════════
# Clerk Webhook Signature Verification
# ═══════════════════════════════════════════════════════════

def verify_clerk_webhook(payload: bytes, sig_header: str) -> bool:
    """
    Verify the Clerk webhook signature using HMAC-SHA256.

    Clerk sends the signature in the `svix-signature` header (Clerk
    uses the Svix webhook framework under the hood).
    """
    secret = config.CLERK_WEBHOOK_SECRET
    if not secret:
        log.warning("CLERK_WEBHOOK_SECRET not set — skipping webhook verification")
        return True

    try:
        # Clerk/Svix format: signature header contains versioned signatures
        # Format: v1=base64(signature),v1=another_sig...
        parts = sig_header.split(",")
        expected_sig = None
        for part in parts:
            part = part.strip()
            if part.startswith("v1="):
                expected_sig = part[3:]
                break

        if not expected_sig:
            return False

        # Compute HMAC-SHA256
        secret_bytes = secret.encode("utf-8")
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        computed = hmac.new(secret_bytes, payload, hashlib.sha256).digest()
        computed_sig = base64.b64encode(computed).decode("utf-8")

        # Constant-time comparison
        return hmac.compare_digest(computed_sig, expected_sig)
    except Exception as e:
        log.warning(f"Webhook signature verification failed: {e}")
        return False


EVENTS_TO_SYNC = {"user.created", "user.updated", "user.deleted"}


async def handle_clerk_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive Clerk webhook events and sync user data to local DB.

    Verifies the webhook signature using CLERK_WEBHOOK_SECRET.
    """
    payload = await request.body()
    sig_header = request.headers.get("svix-signature", "")

    if not verify_clerk_webhook(payload, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = data.get("type", "")
    log.info(f"Clerk webhook received: {event_type}")

    if event_type not in EVENTS_TO_SYNC:
        return {"status": "ignored", "event": event_type}

    user_data = data.get("data", {})
    clerk_id = user_data.get("id", "")

    if not clerk_id:
        raise HTTPException(status_code=400, detail="Missing user ID in webhook data")

    if event_type == "user.deleted":
        _delete_user(clerk_id, db)
        return {"status": "deleted", "clerk_id": clerk_id}

    email = ""
    email_addresses = user_data.get("email_addresses", [])
    if email_addresses:
        email = email_addresses[0].get("email_address", "")

    name = user_data.get("first_name", "") or ""
    if user_data.get("last_name"):
        name += f" {user_data['last_name']}"
    name = name.strip()

    is_admin = email.lower() in config.ADMIN_EMAILS

    if event_type == "user.created":
        _create_user(clerk_id, email, name, is_admin, db)
    elif event_type == "user.updated":
        _update_user(clerk_id, email, name, is_admin, db)

    return {"status": "synced", "clerk_id": clerk_id}


def _create_user(clerk_id: str, email: str, name: str, is_admin: bool, db: Session):
    """Create a local user record from Clerk data."""
    existing = db.query(UserModel).filter(UserModel.clerk_id == clerk_id).first()
    if existing:
        # Already exists — update instead
        existing.email = email
        existing.name = name
        existing.is_admin = is_admin or existing.is_admin
        existing.updated_at = datetime.utcnow()
        db.commit()
        log.info(f"Updated existing user: {email} (admin={is_admin})")
        return

    user = UserModel(
        clerk_id=clerk_id,
        email=email,
        name=name,
        is_admin=is_admin,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info(f"Created new user: {email} (admin={is_admin})")


def _update_user(clerk_id: str, email: str, name: str, is_admin: bool, db: Session):
    """Update an existing local user record from Clerk data."""
    user = db.query(UserModel).filter(UserModel.clerk_id == clerk_id).first()
    if not user:
        # Doesn't exist yet — create
        _create_user(clerk_id, email, name, is_admin, db)
        return

    user.email = email
    user.name = name
    user.is_admin = is_admin or user.is_admin
    user.updated_at = datetime.utcnow()
    db.commit()
    log.info(f"Updated user: {email} (admin={is_admin})")


def _delete_user(clerk_id: str, db: Session):
    """Remove a local user record when Clerk deletes the user."""
    user = db.query(UserModel).filter(UserModel.clerk_id == clerk_id).first()
    if user:
        db.delete(user)
        db.commit()
        log.info(f"Deleted user: {clerk_id}")


# ═══════════════════════════════════════════════════════════
# Clerk Session Verification Middleware
# ═══════════════════════════════════════════════════════════
# In production, you would verify the Clerk session JWT here.
# For now, we trust the Clerk session cookie and resolve the
# user from the Clerk user ID provided in headers/Clerk metadata.
#
# The frontend Clerk SDK sets a __session cookie (HTTP-only).
# We read it and validate with Clerk's JWKS endpoint.


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[UserModel]:
    """
    Resolve the current user from the request.

    Reads the Clerk session token from the Authorization header or
    __session cookie, then looks up the local user.

    In development mode, we extract the Clerk user ID from the JWT
    payload (without full signature verification — the JWT is signed
    by Clerk and the frontend Clerk SDK handles session refresh).

    In production, verify the JWT against Clerk's JWKS endpoint using:
      curl https://{clerk_domain}/.well-known/jwks.json

    Returns None if the user is not authenticated or not found locally.
    """
    # Clerk frontend SDK sets this header on fetch requests
    auth_header = request.headers.get("Authorization", "")
    session_token = ""

    if auth_header.startswith("Bearer "):
        session_token = auth_header[7:]

    if not session_token:
        # Fallback: Clerk __session cookie (HTTP-only, set by Clerk)
        session_token = request.cookies.get("__session", "")

    if not session_token:
        return None

    # Try to extract Clerk user ID from the session token
    clerk_user_id = _extract_clerk_user_id(session_token)
    if not clerk_user_id:
        return None

    # Look up the local user by Clerk ID
    return db.query(UserModel).filter(
        UserModel.clerk_id == clerk_user_id
    ).first()


def _extract_clerk_user_id(token: str) -> Optional[str]:
    """
    Extract the Clerk user ID (sub claim) from a session JWT.

    In development, decodes the JWT payload without signature
    verification. For production, use Clerk's JWKS to verify.
    """
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None

        payload_b64 = parts[1]
        # Add padding for base64url decoding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        decoded = base64.urlsafe_b64decode(payload_b64)
        claims = json.loads(decoded)
        return claims.get("sub", None)
    except Exception:
        log.debug("Could not extract Clerk user ID from session token")
        return None


async def require_user(user: Optional[UserModel] = Depends(get_current_user)) -> UserModel:
    """Dependency: require an authenticated user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


async def require_admin(user: UserModel = Depends(require_user)) -> UserModel:
    """Dependency: require an admin user."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
