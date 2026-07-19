"""
AI-Medikelizar — App Configuration
===================================
All settings in one place. Edit this file directly to configure the app.

API keys should still be set via .env for security (they'll override
the empty strings here).

Provider options: google | openrouter | ollama
"""

# ═══════════════════════════════════════════════════════════
# Active Provider
# ═══════════════════════════════════════════════════════════
# Choose one: "google" | "openrouter" | "ollama"
AI_PROVIDER = "ollama"

# ═══════════════════════════════════════════════════════════
# Google Gemini
# ═══════════════════════════════════════════════════════════
AI_GOOGLE_API_KEY = ""                  # Or set env: GOOGLE_API_KEY
AI_GOOGLE_MODEL   = "gemini-2.0-flash-lite"

# ═══════════════════════════════════════════════════════════
# OpenRouter (OpenAI-compatible proxy)
# ═══════════════════════════════════════════════════════════
AI_OPENROUTER_API_KEY    = ""           # Or set env: OPENROUTER_API_KEY
AI_OPENROUTER_MODEL      = "gpt-4o-mini"
AI_OPENROUTER_BASE_URL   = "https://openrouter.ai/api/v1"

# ═══════════════════════════════════════════════════════════
# Ollama (local)
# ═══════════════════════════════════════════════════════════
AI_OLLAMA_MODEL     = "qwen2.5-coder:7b"
AI_OLLAMA_BASE_URL  = "http://localhost:11434"

# ═══════════════════════════════════════════════════════════
# PubMed E-utilities
# ═══════════════════════════════════════════════════════════
PUBMED_API_KEY = ""                    # Or set env: PUBMED_API_KEY
PUBMED_EMAIL   = "user@example.com"
PUBMED_TOOL    = "AI-Medikelizar"

# ═══════════════════════════════════════════════════════════
# Retrieval Settings
# ═══════════════════════════════════════════════════════════
DEFAULT_CONFIDENCE = "medium"    # "low" | "medium" | "high"
MAX_SOURCES        = 8
MIN_RELEVANCE      = 0.7
CACHE_RESULTS      = True

# ── Confidence presets ──
# Higher confidence = more sources retrieved = slower response
CONFIDENCE_PRESETS = {
    "low": {
        "label": "Fast",
        "max_sources": 3,
        "temperature": 0.5,
        "description": "Quick answer, fewer sources",
    },
    "medium": {
        "label": "Balanced",
        "max_sources": 6,
        "temperature": 0.3,
        "description": "Balanced speed and thoroughness",
    },
    "high": {
        "label": "Thorough",
        "max_sources": 12,
        "temperature": 0.1,
        "description": "Most sources, slower but comprehensive",
    },
}

# ═══════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = (
    "You are a clinical reference assistant. Answer the user's question "
    "using ONLY the provided source texts. Cite every factual claim with "
    "its source number in square brackets, e.g. [1]. Never fabricate "
    "references or infer beyond what the sources state. If the sources are "
    "insufficient to answer, state that clearly. Use precise medical "
    "terminology but explain it briefly. Format your response in clear "
    "paragraphs with bold headings for sections."
)
