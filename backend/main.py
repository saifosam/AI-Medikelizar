"""
AI-Medikelizar — FastAPI Backend
=================================
RAG pipeline API server.

Endpoints:
    POST /api/query    — Submit a clinical question, get cited answer
    GET  /api/health   — Health check with active provider info

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import config
from .models import QueryRequest, QueryResponse, HealthResponse
from .rag_pipeline import run_pipeline

# ── Project root for serving frontend ────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent

# ═══ Logging ═══════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("ai-medikelizar")

# ═══ App ═══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup info."""
    log.info("─" * 50)
    log.info("AI-Medikelizar Backend starting")
    log.info(f"  Provider:      {config.PROVIDER}")
    log.info(f"  Model:         {_resolve_model_name(config.PROVIDER)}")
    log.info(f"  Confidence:    {config.DEFAULT_CONFIDENCE} (default)")
    log.info(f"  PubMed:        {'API key set' if config.PUBMED_API_KEY else 'no API key (3 req/s)'}")
    log.info(f"  CORS:          * (configure via CORS_ORIGINS env var for production)")
    log.info("─" * 50)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="AI-Medikelizar API",
    description="Clinical reference RAG pipeline — search PubMed + AI summarization",
    version="1.0.0",
    lifespan=lifespan,
)

# ═══ CORS (allow frontend dev servers & Vercel production) ═
# In production (e.g., Vercel), frontend and API are on the same
# origin, so CORS is mostly needed for local development.
# Restrict origins in production by setting the CORS_ORIGINS
# environment variable (comma-separated).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount frontend static files ──────────────────────
CSS_DIR = FRONTEND_DIR / "css"
JS_DIR = FRONTEND_DIR / "js"
if CSS_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(CSS_DIR)), name="css")
if JS_DIR.exists():
    app.mount("/js", StaticFiles(directory=str(JS_DIR)), name="js")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main index.html."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ═══ Endpoints ═════════════════════════════════════════

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    provider_name = config.PROVIDER
    model = _resolve_model_name(provider_name)
    return HealthResponse(
        status="ok",
        provider=provider_name,
        model=model,
        confidence_presets=config.CONFIDENCE_PRESETS,
        default_confidence=config.DEFAULT_CONFIDENCE,
    )


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Submit a clinical question.

    The backend will:
    1. Search PubMed for relevant articles
    2. Retrieve full metadata (title, authors, abstract, etc.)
    3. Call the configured AI provider to synthesise an answer
    4. Return the answer with inline citation markers and source cards
    """
    q = request.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(q) > 1000:
        raise HTTPException(status_code=400, detail="Query too long (max 1000 chars).")

    # Validate confidence level
    confidence = request.confidence or config.DEFAULT_CONFIDENCE
    if confidence not in config.CONFIDENCE_PRESETS:
        confidence = config.DEFAULT_CONFIDENCE
    preset = config.CONFIDENCE_PRESETS[confidence]

    log.info(f"Query: {q[:80]}{'...' if len(q) > 80 else ''}  [confidence={confidence}, max_sources={preset['max_sources']}]")

    try:
        result = await run_pipeline(q, confidence=confidence)
        log.info(f"  → {len(result.sources)} sources, confidence={result.confidence}")
        return result
    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══ Helpers ═══════════════════════════════════════════

def _resolve_model_name(provider_name: str) -> str:
    """Get the configured model for the active provider."""
    attr = f"{provider_name.upper()}_MODEL"
    return getattr(config, attr, "unknown")


# ═══ Entry point ══════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    print()
    print(f"  +------------------------------------------------+")
    print(f"  |        AI-Medikelizar -- Starting Up           |")
    print(f"  +------------------------------------------------+")
    print(f"  |  Open:  http://localhost:{port}                   |")
    print(f"  |  Provider: {config.PROVIDER:<25s}|")
    model_name = _resolve_model_name(config.PROVIDER)
    print(f"  |  Model:    {model_name:<25s}|")
    print(f"  |  Press Ctrl+C to stop                        |")
    print(f"  +------------------------------------------------+")
    print()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
