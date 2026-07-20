"""
AI-Medikelizar — Pydantic & SQLAlchemy Models
===============================================
Request/response schemas (Pydantic) and database models (SQLAlchemy).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

# ═══════════════════════════════════════════════════════
# SQLAlchemy Base (shared with database.py)
# ═══════════════════════════════════════════════════════

SA_Base = declarative_base()


# ═══════════════════════════════════════════════════════
# Database Models (SQLAlchemy)
# ═══════════════════════════════════════════════════════

class UserModel(SA_Base):
    """Local user record, synced from Clerk."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clerk_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255), default="")
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscriptions = relationship("SubscriptionModel", back_populates="user", lazy="dynamic")


class SubscriptionModel(SA_Base):
    """User subscription record, synced from Stripe."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tier = Column(String(50), default="basic")       # basic | premium | vip
    status = Column(String(50), default="active")     # active | cancelled | past_due | incomplete
    stripe_customer_id = Column(String(255), default="")
    stripe_subscription_id = Column(String(255), default="")
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("UserModel", back_populates="subscriptions")


class QueryLogModel(SA_Base):
    """Log of user queries for usage tracking and analytics."""
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query = Column(Text, nullable=False)
    sources_count = Column(Integer, default=0)
    confidence = Column(String(50), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)


class PageViewModel(SA_Base):
    """Simple page view tracking for analytics."""
    __tablename__ = "page_views"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    path = Column(String(500), nullable=False)
    ip_address = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════
# Pydantic Schemas (API request/response)
# ═══════════════════════════════════════════════════════

class QueryRequest(BaseModel):
    """Incoming user query."""
    query: str
    confidence: str = "medium"  # "low" | "medium" | "high"
    context: Optional[dict] = None  # For follow-up queries: { previousQuery, previousAnswer }


class SourceModel(BaseModel):
    """A single source / citation returned with the answer."""
    id: int
    title: str
    authors: str
    journal: str
    date: str
    volume: str = ""
    doi: str = ""
    pmid: str = ""
    url: str = ""
    abstract: str = ""
    publisher: str = ""
    relevance: float = 0.0


class QueryResponse(BaseModel):
    """Full response returned to the frontend."""
    answer: str
    sources: list[SourceModel]
    confidence: str  # "high" | "moderate" | "limited"
    provider: str
    model: str


class ConfidencePreset(BaseModel):
    """Confidence preset configuration."""
    label: str
    max_sources: int
    temperature: float
    description: str


class HealthResponse(BaseModel):
    """Health-check endpoint response."""
    status: str
    provider: str
    model: str
    version: str = "1.0.0"
    confidence_presets: dict = {}
    default_confidence: str = "medium"


# ── Admin / Auth Schemas ──

class UserOut(BaseModel):
    """Public user data (sent to frontend)."""
    id: int
    clerk_id: str
    email: str
    name: str
    is_admin: bool
    tier: str = "basic"
    subscription_status: str = ""
    created_at: datetime


class AdminDashboardStats(BaseModel):
    """Admin dashboard aggregated stats."""
    total_users: int
    new_users_7d: int
    total_queries: int
    queries_7d: int
    total_revenue_cents: int
    revenue_7d_cents: int
    active_subscriptions: int
    users_by_tier: dict
    recent_users: list[UserOut]


class CheckoutSessionResponse(BaseModel):
    """Response from create-checkout-session."""
    url: str


class SubscriptionStatusResponse(BaseModel):
    """User's current subscription status."""
    tier: str
    status: str
    current_period_end: Optional[str] = None
    queries_used_today: int = 0
    queries_limit: int = 0
