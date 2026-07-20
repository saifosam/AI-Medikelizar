"""
AI-Medikelizar — Configuration Module
=======================================
Reads settings from environment variables (with hardcoded fallbacks).

The single source of truth for provider and model configuration is
.env (or .env.example for reference). Copy .env.example to .env and
edit it — that's the only file you need to touch.

Priority:  .env / env vars  >  hardcoded defaults below
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from . import app as app_config

# ── Paths ──────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"

# ── Load .env ──────────────────────────────────────────
# Backend/.env
load_dotenv(ENV_PATH, override=True)
# Project root .env (takes priority)
PROJECT_ENV_PATH = BACKEND_DIR.parent / ".env"
if PROJECT_ENV_PATH.exists():
    load_dotenv(PROJECT_ENV_PATH, override=True)

# Helper: env var > fallback
def _env(key: str, fallback):
    """Return env var if set, else fallback value."""
    return os.getenv(key, fallback)

# ══════════════════════════════════════════════════════
# Active Provider
# ══════════════════════════════════════════════════════
# Configured ONLY via .env — edit .env to change.
# See .env.example for all options.
PROVIDER = os.getenv("AI_PROVIDER", "ollama")

# ══════════════════════════════════════════════════════
# Google Gemini
# ══════════════════════════════════════════════════════
GOOGLE_API_KEY = _env("GOOGLE_API_KEY", "")
GOOGLE_MODEL   = _env("GOOGLE_MODEL",   "gemini-2.0-flash-lite")

# ══════════════════════════════════════════════════════
# Groq (free, no credit card needed)
# ══════════════════════════════════════════════════════
GROQ_API_KEY   = _env("GROQ_API_KEY",   "")
GROQ_MODEL     = _env("GROQ_MODEL",     "llama-3.1-8b-instant")
GROQ_BASE_URL  = _env("GROQ_BASE_URL",  "https://api.groq.com/openai/v1")

# ══════════════════════════════════════════════════════
# OpenRouter
# ══════════════════════════════════════════════════════
OPENROUTER_API_KEY   = _env("OPENROUTER_API_KEY",   "")
OPENROUTER_MODEL     = _env("OPENROUTER_MODEL",     "gpt-4o-mini")
OPENROUTER_BASE_URL  = _env("OPENROUTER_BASE_URL",  "https://openrouter.ai/api/v1")

# ══════════════════════════════════════════════════════
# Ollama (local)
# ══════════════════════════════════════════════════════
OLLAMA_MODEL     = _env("OLLAMA_MODEL",     "qwen2.5-coder:7b")
OLLAMA_BASE_URL  = _env("OLLAMA_BASE_URL",  "http://localhost:11434")

# ══════════════════════════════════════════════════════
# PubMed E-utilities
# ══════════════════════════════════════════════════════
PUBMED_API_KEY = _env("PUBMED_API_KEY", app_config.PUBMED_API_KEY)
PUBMED_EMAIL   = _env("PUBMED_EMAIL",   app_config.PUBMED_EMAIL)
PUBMED_TOOL    = _env("PUBMED_TOOL",    app_config.PUBMED_TOOL)

# ══════════════════════════════════════════════════════
# Retrieval
# ══════════════════════════════════════════════════════
DEFAULT_CONFIDENCE = _env("DEFAULT_CONFIDENCE", app_config.DEFAULT_CONFIDENCE)
CONFIDENCE_PRESETS = app_config.CONFIDENCE_PRESETS
MAX_SOURCES    = int(_env("MAX_SOURCES",    app_config.MAX_SOURCES))
MIN_RELEVANCE  = float(_env("MIN_RELEVANCE",  app_config.MIN_RELEVANCE))
CACHE_RESULTS  = _env("CACHE_RESULTS", str(app_config.CACHE_RESULTS)).lower() == "true"

# ══════════════════════════════════════════════════════
# Legacy Providers (OpenAI, Anthropic, Custom)
# Still supported if you switch AI_PROVIDER, but configurable
# via env vars only (not in app.py).
# ══════════════════════════════════════════════════════
OPENAI_API_KEY     = _env("OPENAI_API_KEY", "")
OPENAI_MODEL       = _env("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_ENDPOINT    = _env("OPENAI_ENDPOINT", "https://api.openai.com/v1")
ANTHROPIC_API_KEY  = _env("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL    = _env("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
CUSTOM_API_KEY     = _env("CUSTOM_API_KEY", "")
CUSTOM_ENDPOINT    = _env("CUSTOM_ENDPOINT", "")
CUSTOM_MODEL       = _env("CUSTOM_MODEL", "")

# ══════════════════════════════════════════════════════
# Stripe
# ══════════════════════════════════════════════════════
STRIPE_SECRET_KEY      = _env("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = _env("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET  = _env("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PREMIUM_PRICE_ID = _env("STRIPE_PREMIUM_PRICE_ID", "")
STRIPE_VIP_PRICE_ID     = _env("STRIPE_VIP_PRICE_ID", "")

# ══════════════════════════════════════════════════════
# Clerk
# ══════════════════════════════════════════════════════
CLERK_WEBHOOK_SECRET = _env("CLERK_WEBHOOK_SECRET", "")
CLERK_SECRET_KEY      = _env("CLERK_SECRET_KEY", "")

# ══════════════════════════════════════════════════════
# Admin
# ══════════════════════════════════════════════════════
ADMIN_EMAILS_RAW = _env("ADMIN_EMAILS", "admin@ai-medikelizar.com")
ADMIN_EMAILS = set(e.strip().lower() for e in ADMIN_EMAILS_RAW.split(",") if e.strip())

# ══════════════════════════════════════════════════════
# Rate Limiting
# ══════════════════════════════════════════════════════
RATE_LIMIT_ENABLED = _env("RATE_LIMIT_ENABLED", "true").lower() == "true"
LOGIN_RATE_LIMIT   = _env("LOGIN_RATE_LIMIT", "10/minute")

# ══════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════
SYSTEM_PROMPT = _env("SYSTEM_PROMPT", app_config.SYSTEM_PROMPT)
