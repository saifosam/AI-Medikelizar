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

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .models import QueryRequest, QueryResponse, HealthResponse
from .rag_pipeline import run_pipeline

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
    log.info(f"  Provider:  {config.PROVIDER}")
    log.info(f"  PubMed:    {'API key set' if config.PUBMED_API_KEY else 'no API key (3 req/s)'}")
    log.info(f"  CORS:      http://localhost:5500, http://127.0.0.1:5500")
    log.info("─" * 50)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="AI-Medikelizar API",
    description="Clinical reference RAG pipeline — search PubMed + AI summarization",
    version="1.0.0",
    lifespan=lifespan,
)

# ═══ CORS (allow frontend dev servers) ════════════════
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://saifosam.github.io",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    log.info(f"Query: {q[:80]}{'...' if len(q) > 80 else ''}")

    try:
        result = await run_pipeline(q)
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
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
