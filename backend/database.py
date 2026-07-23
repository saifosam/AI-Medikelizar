"""
AI-Medikelizar — Database Setup
================================
SQLAlchemy engine and session configuration for SQLite.

The database file lives at backend/ai_medikelizar.db by default.
Override with the DATABASE_URL environment variable.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BACKEND_DIR / "ai_medikelizar.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# SQLite needs check_same_thread=False for FastAPI async usage
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call on app startup."""
    from .models import UserModel, SubscriptionModel, QueryLogModel, PageViewModel, CreditPurchaseModel, SA_Base  # noqa
    SA_Base.metadata.create_all(bind=engine)
