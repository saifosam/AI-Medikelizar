"""
AI-Medikelizar — FastAPI Backend
=================================
RAG pipeline API server with auth, subscriptions, and admin.

Endpoints:
    GET  /                  — Serve frontend
    GET  /api/health        — Health check
    POST /api/query         — Submit a clinical question
    POST /api/auth/webhook  — Clerk webhook (sync users)
    GET  /api/subscriptions/pricing       — Tier definitions
    GET  /api/subscriptions/status        — User's subscription status
    POST /api/subscriptions/create-checkout    — Create Stripe Checkout
    POST /api/subscriptions/create-portal-session — Customer portal
    POST /api/subscriptions/webhook       — Stripe webhook
    GET  /api/admin/dashboard — Admin dashboard stats
    GET  /api/admin/users    — List all users

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from . import config
from .models import QueryRequest, QueryResponse, HealthResponse
from .rag_pipeline import run_pipeline
from .database import init_db

# ── Project root for serving frontend ────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent

# ═══ Logging ═══════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("ai-medikelizar")


# ═══ Rate Limiter ══════════════════════════════════════
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, enabled=config.RATE_LIMIT_ENABLED)


# ═══ App ═══════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and log startup info."""
    # Initialize database tables
    try:
        init_db()
        log.info("Database tables created/verified")
    except Exception as e:
        log.error(f"Database initialization failed: {e}")

    log.info("─" * 50)
    log.info("AI-Medikelizar Backend starting")
    log.info(f"  Provider:      {config.PROVIDER}")
    log.info(f"  Model:         {_resolve_model_name(config.PROVIDER)}")
    log.info(f"  Confidence:    {config.DEFAULT_CONFIDENCE} (default)")
    log.info(f"  PubMed:        {'API key set' if config.PUBMED_API_KEY else 'no API key (3 req/s)'}")
    log.info(f"  Rate limit:    {'enabled' if config.RATE_LIMIT_ENABLED else 'disabled'}")
    log.info(f"  Admin emails:  {', '.join(config.ADMIN_EMAILS)}")
    log.info(f"  Stripe:        {'configured' if config.STRIPE_SECRET_KEY else 'not configured'}")
    log.info("─" * 50)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="AI-Medikelizar API",
    description="Clinical reference RAG pipeline — search PubMed + AI summarization",
    version="2.0.0",
    lifespan=lifespan,
)

# ═══ Rate limit handler ═══════════════════════════════
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ═══ Page View Tracking Middleware ════════════════════
@app.middleware("http")
async def track_page_views(request: Request, call_next):
    """Log page views for basic analytics."""
    path = request.url.path

    # Only track frontend page views, skip static files and API calls
    if path.startswith("/css/") or path.startswith("/js/") or path.startswith("/api/"):
        return await call_next(request)

    response = await call_next(request)

    # Track the page view after response is sent (fire-and-forget)
    try:
        from .database import SessionLocal
        from .models import PageViewModel
        from .auth import get_current_user

        db = SessionLocal()
        try:
            user = await get_current_user(request, db)
            page_view = PageViewModel(
                user_id=user.id if user else None,
                path=path,
                ip_address=request.client.host if request.client else "",
            )
            db.add(page_view)
            db.commit()
            log.debug(f"Page view tracked: {path}")
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        log.debug(f"Page view tracking failed: {e}")

    return response


# ═══ CORS ═════════════════════════════════════════════
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


# ═══ Import and include routers ═══════════════════════
from .auth import handle_clerk_webhook
from .subscriptions import router as subscriptions_router
from .admin import router as admin_router

app.include_router(subscriptions_router)
app.include_router(admin_router)


# ═══ Endpoints ═════════════════════════════════════════

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main index.html."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


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


@app.post("/api/query")
@limiter.limit("30/minute")
async def query(request: Request, body: QueryRequest):
    """
    Submit a clinical question.

    Rate-limited to 30 requests per minute per IP.
    Tier query limits enforced server-side.
    """
    from .auth import get_current_user
    from .database import get_db
    from .subscriptions import check_query_limit, get_user_tier, get_tier_limits
    from .models import QueryLogModel
    from datetime import datetime

    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(q) > 1000:
        raise HTTPException(status_code=400, detail="Query too long (max 1000 chars).")

    # Validate confidence level
    confidence = body.confidence or config.DEFAULT_CONFIDENCE
    if confidence not in config.CONFIDENCE_PRESETS:
        confidence = config.DEFAULT_CONFIDENCE
    preset = config.CONFIDENCE_PRESETS[confidence]

    # Check user tier and query limit
    db = next(get_db())
    try:
        user = await get_current_user(request, db)
        tier = get_user_tier(user, db)
        limits = get_tier_limits(tier)

        if not check_query_limit(user, db):
            raise HTTPException(
                status_code=429,
                detail=f"Daily query limit reached ({limits['queries_per_day']}/day). "
                       f"Upgrade your subscription for higher limits.",
            )

        # ── Diagnostic log: show incoming context for follow-up queries ──
        if body.context:
            log.info(f"CONTEXT RECEIVED: previousQuery='{body.context.get('previousQuery','')[:60]}' | "
                     f"previousAnswer_len={len(body.context.get('previousAnswer',''))} ")
        else:
            log.info(f"NO CONTEXT: initial query")

        log.info(f"Query: {q[:80]}{'...' if len(q) > 80 else ''}  "
                 f"[tier={tier}, confidence={confidence}, max_sources={preset['max_sources']}]")

        result = await run_pipeline(q, confidence=confidence, context=body.context)

        # Log the query for usage tracking
        query_log = QueryLogModel(
            user_id=user.id if user else None,
            query=q[:500],
            sources_count=len(result.sources),
            confidence=confidence,
            created_at=datetime.utcnow(),
        )
        db.add(query_log)
        db.commit()

        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/auth/webhook")
@limiter.limit("10/minute")
async def clerk_webhook(request: Request):
    """Receive Clerk webhook events to sync users."""
    from .database import get_db
    db = next(get_db())
    try:
        return await handle_clerk_webhook(request, db)
    finally:
        db.close()


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
    print(f"  |  Stripe:   {'configured' if config.STRIPE_SECRET_KEY else 'not configured':<21s}|")
    print(f"  |  Admins:   {', '.join(config.ADMIN_EMAILS):<26s}|")
    print(f"  |  Press Ctrl+C to stop                        |")
    print(f"  +------------------------------------------------+")
    print()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
