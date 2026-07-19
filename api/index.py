"""Vercel serverless entry point for the AI-Medikelizar FastAPI backend.

This file is deployed as a Vercel Serverless Function.
All requests to /api/* are routed here via vercel.json rewrites.

Environment variables (API keys, etc.) should be set in the Vercel
project dashboard — they are passed through automatically.
"""

import sys
from pathlib import Path

# ── Ensure the project root is on sys.path ──────────────────
# Vercel runs from the `api/` directory, so we need to add the
# parent directory to resolve `backend.` imports.
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# ── Import the FastAPI app ──────────────────────────────────
# Vercel auto-detects ASGI apps (which FastAPI is) and serves
# them correctly. No special wrapper needed.
from backend.main import app

# Explicit alias so Vercel picks it up reliably
application = app
