"""
AI-Medikelizar — Configuration Module
=======================================
Reads settings from app.py (the single source of truth) and allows
individual overrides via environment variables (useful for secrets).

Priority:  .env / env vars  >  app.py defaults
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

# Helper: env var > app.py default
def _env(key: str, fallback):
    """Return env var if set, else fallback value."""
    return os.getenv(key, fallback)

# ══════════════════════════════════════════════════════
# Active Provider
# ══════════════════════════════════════════════════════
PROVIDER = os.getenv("AI_PROVIDER", app_config.AI_PROVIDER)

# ══════════════════════════════════════════════════════
# Google Gemini
# ══════════════════════════════════════════════════════
GOOGLE_API_KEY = _env("GOOGLE_API_KEY", app_config.AI_GOOGLE_API_KEY)
GOOGLE_MODEL   = _env("GOOGLE_MODEL",   app_config.AI_GOOGLE_MODEL)

# ══════════════════════════════════════════════════════
# OpenRouter
# ══════════════════════════════════════════════════════
OPENROUTER_API_KEY   = _env("OPENROUTER_API_KEY",   app_config.AI_OPENROUTER_API_KEY)
OPENROUTER_MODEL     = _env("OPENROUTER_MODEL",     app_config.AI_OPENROUTER_MODEL)
OPENROUTER_BASE_URL  = _env("OPENROUTER_BASE_URL",  app_config.AI_OPENROUTER_BASE_URL)

# ══════════════════════════════════════════════════════
# Ollama (local)
# ══════════════════════════════════════════════════════
OLLAMA_MODEL     = _env("OLLAMA_MODEL",     app_config.AI_OLLAMA_MODEL)
OLLAMA_BASE_URL  = _env("OLLAMA_BASE_URL",  app_config.AI_OLLAMA_BASE_URL)

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
# System Prompt
# ══════════════════════════════════════════════════════
SYSTEM_PROMPT = _env("SYSTEM_PROMPT", app_config.SYSTEM_PROMPT)
