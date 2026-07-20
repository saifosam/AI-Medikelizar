"""
AI-Medikelizar — Configuration Module
=======================================
Reads settings from environment variables (with hardcoded fallbacks).

The single source of truth for provider and model configuration is
.env (or .env.example for reference). Copy .env.example to .env and
edit it — that's the only file you need to touch.

Priority:  .env / env vars  >  hardcoded defaults below

╔═══════════════════════════════════════════════════════════╗
║  Security: Server-Side Only                              ║
║  ─────────────────────────────                           ║
║  Server-Side Only — The Critical Guard                   ║
║  This module runs 100% on the server, never in the       ║
║  browser. Python modules are inherently server-only —    ║
║  no import guard needed (unlike Next.js `server-only`).  ║
║                                                           ║
║  require_env() — Fail-Fast Safety Net                    ║
║  Crashes the server IMMEDIATELY at module import time    ║
║  if a required environment variable is missing.           ║
║  No silent failures, no running in a broken state.        ║
╚═══════════════════════════════════════════════════════════╝
"""

import os
import sys
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

# ═══════════════════════════════════════════════════════════
# require_env() — Fail fast at module import time
# ═══════════════════════════════════════════════════════════
# Mirrors the Next.js reference pattern EXACTLY:
#   function requireEnv(name: string): string {
#     const value = process.env[name]
#     if (!value) { throw new Error(`Missing required ...`) }
#     return value
#   }
# This crashes IMMEDIATELY at module import time if a
# critical key is missing — no silent failures.

def require_env(name: str) -> str:
    """
    Return the environment variable, or crash IMMEDIATELY at module
    import time if it's not set. This is a compile-time safety net
    that prevents the server from running with missing configuration.

    Mirrors the reference pattern:
      function requireEnv(name: string): string {
        const value = process.env[name]
        if (!value) { throw new Error(`Missing required ...`) }
        return value
      }
    """
    value = os.getenv(name)
    if not value:
        print(f"  ❌  FATAL: Missing required environment variable: {name}", file=sys.stderr)
        print(f"  💡  Set it in backend/.env or export it before starting.", file=sys.stderr)
        sys.exit(1)
    return value


# ═══════════════════════════════════════════════════════════
# Startup validation — check table at lifespan start
# ═══════════════════════════════════════════════════════════
# Defines which env vars are CRITICAL (server won't start without)
# vs OPTIONAL (nice to have, fallback or degraded mode).

CRITICAL_ENV_VARS: dict[str, str] = {
    # (none required — app can run without Clerk)
}

OPTIONAL_ENV_VARS: dict[str, str] = {
    # Clerk authentication (optional — app works without it, just no auth)
    "CLERK_SECRET_KEY": "Clerk API secret for session verification",

    # AI Providers
    "AI_PROVIDER": "Active AI provider (ollama, google, groq, openrouter)",
    "GOOGLE_API_KEY": "Google Gemini API key",
    "GROQ_API_KEY": "Groq API key (free, no credit card)",
    "OPENROUTER_API_KEY": "OpenRouter API key",
    # Paymob (Egyptian payment gateway)
    "PAYMOB_API_KEY": "Paymob secret API key",
    "PAYMOB_PUBLIC_KEY": "Paymob public key for checkout",
    "PAYMOB_WEBHOOK_SECRET": "Paymob webhook HMAC secret",
    "PAYMOB_INTEGRATION_ID_CARDS": "Paymob integration ID for card payments",
    "PAYMOB_INTEGRATION_ID_WALLETS": "Paymob integration ID for mobile wallets",
    "PAYMOB_PREMIUM_PRICE_CENTS": "Premium tier price in EGP piastres (e.g. 2999 = 29.99 EGP)",
    "PAYMOB_VIP_PRICE_CENTS": "VIP tier price in EGP piastres (e.g. 8999 = 89.99 EGP)",
    # Clerk
    "CLERK_WEBHOOK_SECRET": "Clerk webhook signing secret",
    # PubMed
    "PUBMED_API_KEY": "PubMed E-utilities API key (higher rate limit)",
    # Admin
    "ADMIN_EMAILS": "Comma-separated list of admin email addresses",
}


def validate_startup_env() -> list[dict[str, str]]:
    """
    Check all critical and optional env vars at startup.
    Returns a list of var status dicts for display.
    Exits with code 1 if any critical var is missing.
    """
    statuses: list[dict[str, str]] = []
    missing_critical = False

    for name, purpose in CRITICAL_ENV_VARS.items():
        value = os.getenv(name)
        if value:
            statuses.append({"name": name, "status": "✅ set", "purpose": purpose})
        else:
            statuses.append({"name": name, "status": "❌ MISSING", "purpose": purpose})
            missing_critical = True

    for name, purpose in OPTIONAL_ENV_VARS.items():
        value = os.getenv(name)
        if value:
            statuses.append({"name": name, "status": "✅ set", "purpose": purpose})
        else:
            statuses.append({"name": name, "status": "  —", "purpose": purpose})

    if missing_critical:
        print()
        print("  ╔═══════════════════════════════════════════════════════════╗")
        print("  ║  FATAL: Missing required environment variables           ║")
        print("  ║  The server cannot start without these.                  ║")
        print("  ╚═══════════════════════════════════════════════════════════╝")
        print()
        for s in statuses:
            if s["status"] == "❌ MISSING":
                print(f"  {s['status']}  {s['name']:30s}  {s['purpose']}")
        print()
        print(f"  💡  Create backend/.env or export the missing variables.")
        print()
        sys.exit(1)

    return statuses


# Helper: env var > fallback (non-critical, returns fallback if not set)
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
# Paymob (Egyptian payment gateway)
# ══════════════════════════════════════════════════════
PAYMOB_API_KEY              = _env("PAYMOB_API_KEY", "")
PAYMOB_PUBLIC_KEY           = _env("PAYMOB_PUBLIC_KEY", "")
PAYMOB_WEBHOOK_SECRET       = _env("PAYMOB_WEBHOOK_SECRET", "")
PAYMOB_INTEGRATION_ID_CARDS = _env("PAYMOB_INTEGRATION_ID_CARDS", "")
PAYMOB_INTEGRATION_ID_WALLETS = _env("PAYMOB_INTEGRATION_ID_WALLETS", "")
PAYMOB_PREMIUM_PRICE_CENTS  = int(_env("PAYMOB_PREMIUM_PRICE_CENTS", "2999"))   # 29.99 EGP
PAYMOB_VIP_PRICE_CENTS      = int(_env("PAYMOB_VIP_PRICE_CENTS", "8999"))       # 89.99 EGP

# ══════════════════════════════════════════════════════
# Clerk
# ══════════════════════════════════════════════════════
# Optional — use _env() so the server can start without Clerk configured.
# On Vercel, Clerk env vars aren't present; auth endpoints return 401.
CLERK_SECRET_KEY = _env("CLERK_SECRET_KEY", "")

CLERK_WEBHOOK_SECRET = _env("CLERK_WEBHOOK_SECRET", "")

# ══════════════════════════════════════════════════════
# Admin
# ══════════════════════════════════════════════════════
ADMIN_EMAILS_RAW = _env("ADMIN_EMAILS", "admin@ai-medikelizar.com,saifosam.business@gmail.com,yassinadeleid95@gmail.com,youssef.shabayek56@gmail.com,yjhf04508@gmail.com")
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
