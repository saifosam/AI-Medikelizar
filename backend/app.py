"""
AI-Medikelizar — App Configuration
===================================
Non-sensitive app behaviour settings. Everything related to the AI
provider (which provider, which model, API keys, base URLs) is
configured exclusively in .env — see .env.example for the full list.

⚠️  To change the AI provider or model, edit .env, NOT this file.
    Copy .env.example (from the project root) to .env and edit it.
"""

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
