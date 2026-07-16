"""
AI-Medikelizar — Configuration Module
======================================
Reads AI provider settings from:
  1. ../js/config.js  (frontend config, parsed via regex)
  2. .env              (environment variables, fallback)

All settings are exposed as module-level constants.
"""

import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
JS_CONFIG_PATH = PROJECT_DIR / "js" / "config.js"
ENV_PATH = BACKEND_DIR / ".env"

# ── Load .env if present ───────────────────────────────
load_dotenv(ENV_PATH)

# ── Simple JS-object parser for config.js ──────────────
def _parse_js_config(path: Path) -> dict:
    """Extract key-value pairs from the JS config file using regex."""
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")

    def _find(pattern: str, default=None):
        m = re.search(pattern, text, re.MULTILINE)
        return m.group(1).strip() if m else default

    # Determine active provider
    provider = (
        _find(r'provider\s*:\s*"([^"]+)"')
        or os.getenv("AI_PROVIDER", "openai")
    )

    cfg = {"provider": provider}

    # Provider-specific settings
    provider_key_patterns = {
        "openai": {
            "apiKey": r'apiKey\s*:\s*"([^"]*)"',
            "model": r'openai\s*:\s*\{[^}]*?model\s*:\s*"([^"]*)"',
            "endpoint": r'openai\s*:\s*\{[^}]*?endpoint\s*:\s*"([^"]*)"',
        },
        "ollama": {
            "baseUrl": r'baseUrl\s*:\s*"([^"]*)"',
            "model": r'ollama\s*:\s*\{[^}]*?model\s*:\s*"([^"]*)"',
        },
        "anthropic": {
            "apiKey": r'anthropic\s*:\s*\{[^}]*?apiKey\s*:\s*"([^"]*)"',
            "model": r'anthropic\s*:\s*\{[^}]*?model\s*:\s*"([^"]*)"',
        },
        "google": {
            "apiKey": r'google\s*:\s*\{[^}]*?apiKey\s*:\s*"([^"]*)"',
            "model": r'google\s*:\s*\{[^}]*?model\s*:\s*"([^"]*)"',
        },
        "custom": {
            "apiKey": r'custom\s*:\s*\{[^}]*?apiKey\s*:\s*"([^"]*)"',
            "endpoint": r'custom\s*:\s*\{[^}]*?endpoint\s*:\s*"([^"]*)"',
            "model": r'custom\s*:\s*\{[^}]*?model\s*:\s*"([^"]*)"',
        },
    }

    for prov, patterns in provider_key_patterns.items():
        for key, pattern in patterns.items():
            value = _find(pattern)
            if value is not None:
                cfg.setdefault(prov, {})[key] = value

    # System prompt
    sp = re.search(r"systemPrompt\s*:\s*`([^`]*)`", text, re.DOTALL)
    if sp:
        cfg["systemPrompt"] = sp.group(1).strip()

    # Retrieval settings
    cfg.setdefault("retrieval", {})
    for key in ("maxSources", "minRelevance", "cacheResults"):
        val = _find(rf"{key}\s*:\s*([^,\n}}]+)")
        if val is not None:
            try:
                cfg["retrieval"][key] = json.loads(val)
            except json.JSONDecodeError:
                cfg["retrieval"][key] = val

    return cfg


# ── Read config ────────────────────────────────────────
_js_cfg = _parse_js_config(JS_CONFIG_PATH)

PROVIDER = _js_cfg.get("provider", os.getenv("AI_PROVIDER", "openai"))

# Retrieve provider-specific settings with env var fallback
def _get(key: str, provider_key: str, env_var: str, default=None):
    """Get value from JS config with env var fallback."""
    prov_cfg = _js_cfg.get(PROVIDER, {})
    return prov_cfg.get(provider_key) or os.getenv(env_var) or default


if PROVIDER == "openai":
    OPENAI_API_KEY = _get("openai", "apiKey", "OPENAI_API_KEY", "")
    OPENAI_MODEL = _get("openai", "model", "OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_ENDPOINT = _get("openai", "endpoint", "OPENAI_ENDPOINT",
                           "https://api.openai.com/v1")
elif PROVIDER == "ollama":
    OLLAMA_BASE_URL = _get("ollama", "baseUrl", "OLLAMA_BASE_URL",
                           "http://localhost:11434")
    OLLAMA_MODEL = _get("ollama", "model", "OLLAMA_MODEL", "llama3.2")
elif PROVIDER == "anthropic":
    ANTHROPIC_API_KEY = _get("anthropic", "apiKey", "ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = _get("anthropic", "model", "ANTHROPIC_MODEL",
                           "claude-3-haiku-20240307")
elif PROVIDER == "google":
    GOOGLE_API_KEY = _get("google", "apiKey", "GOOGLE_API_KEY", "")
    GOOGLE_MODEL = _get("google", "model", "GOOGLE_MODEL", "gemini-1.5-flash")
elif PROVIDER == "custom":
    CUSTOM_API_KEY = _get("custom", "apiKey", "CUSTOM_API_KEY", "")
    CUSTOM_ENDPOINT = _get("custom", "endpoint", "CUSTOM_ENDPOINT", "")
    CUSTOM_MODEL = _get("custom", "model", "CUSTOM_MODEL", "")

# ── PubMed API ────────────────────────────────────────
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "user@example.com")
PUBMED_TOOL = os.getenv("PUBMED_TOOL", "AI-Medikelizar")

# ── Retrieval ─────────────────────────────────────────
MAX_SOURCES = _js_cfg.get("retrieval", {}).get("maxSources",
                   int(os.getenv("MAX_SOURCES", "8")))
MIN_RELEVANCE = _js_cfg.get("retrieval", {}).get("minRelevance",
                   float(os.getenv("MIN_RELEVANCE", "0.7")))
CACHE_RESULTS = _js_cfg.get("retrieval", {}).get("cacheResults",
                   os.getenv("CACHE_RESULTS", "true").lower() == "true")

# ── System prompt ─────────────────────────────────────
SYSTEM_PROMPT = _js_cfg.get("systemPrompt") or (
    "You are a clinical reference assistant. Answer the user's question "
    "using ONLY the provided source texts. Cite every factual claim with "
    "its source number in square brackets, e.g. [1]. Never fabricate "
    "references or infer beyond what the sources state. If the sources are "
    "insufficient to answer, state that clearly. Use precise medical "
    "terminology but explain it briefly. Format your response in clear "
    "paragraphs with bold headings for sections."
)
