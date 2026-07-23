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
    POST /api/subscriptions/create-checkout    — Create Paymob checkout session
    POST /api/subscriptions/create-portal-session — Subscription management portal
    POST /api/subscriptions/webhook       — Paymob webhook
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
from .models import QueryRequest, QueryResponse, HealthResponse, HumanizeRequest
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
    # ── Validate environment variables (fail fast if critical keys missing) ──
    # This mirrors the requireEnv() pattern from the reference architecture:
    #   The server crashes immediately at startup if a required env var is missing.
    #   No silent failures, no running in a broken state.
    env_statuses = config.validate_startup_env()

    # ── Print environment table (mirrors reference's markdown table) ──
    print()
    print("  +------------------------------------------------------------------+")
    print("  |              AI-Medikelizar — Environment Check                  |")
    print("  +------------------------------------------------------------------+")
    print()
    print(f"  {'Variable':30s} {'Status':12s} {'Purpose'}")
    print(f"  {'-' * 30} {'-' * 12} {'-' * 36}")
    for s in env_statuses:
        print(f"  {s['name']:30s} {s['status']:12s} {s['purpose']}")
    print()

    # Initialize database tables
    try:
        init_db()
        log.info("Database tables created/verified")
    except Exception as e:
        log.error(f"Database initialization failed: {e}")

    # ── Startup banner ──
    log.info("-" * 50)
    log.info("AI-Medikelizar Backend starting")
    _provider = config.PROVIDER
    _key_attr = f"{_provider.upper()}_API_KEY"
    _key_set = bool(getattr(config, _key_attr, ""))
    log.info(f"  Provider:      {_provider}")
    log.info(f"  Model:         {_resolve_model_name(_provider)}")
    log.info(f"  API key:       {'set' if _key_set else 'NOT SET — will fail if not a local provider'}")
    log.info(f"  Confidence:    {config.DEFAULT_CONFIDENCE} (default)")
    log.info(f"  PubMed:        {'API key set' if config.PUBMED_API_KEY else 'no API key (3 req/s)'}")
    log.info(f"  Rate limit:    {'enabled' if config.RATE_LIMIT_ENABLED else 'disabled'}")
    log.info(f"  Admin emails:  {', '.join(config.ADMIN_EMAILS)}")
    log.info(f"  Payments:      {'Paymob configured' if config.PAYMOB_API_KEY else 'not configured'}")
    log.info("-" * 50)

    # ── Security flow diagram (mirrors reference architecture) ──
    log.info("  Security layers active:")
    log.info("    Layer 1  Clerk auth middleware  →  /api/auth/me, Bearer token")
    log.info("    Layer 2  Admin email whitelist  →  require_admin() dependency")
    log.info("    Layer 3  Client-side admin hide →  shield button shown only for admins")
    log.info("  -" * 17)

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
# Since FastAPI serves both frontend AND API from the same origin
# (same domain & port), same-origin requests don't need CORS at all.
# But for deployment flexibility (e.g. separate frontend domain),
# we allow explicit origins with credentials support.
_CORS_ORIGINS_RAW = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
)
_CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
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


# ═══ Auth Middleware (Layer 1: Clerk — protects /api/admin/*) ═══
from .auth import clerk_auth_middleware
app.middleware("http")(clerk_auth_middleware)


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
                detail=f"Daily query limit reached. Upgrade your subscription or purchase credit packs.",
            )

        # ── Diagnostic log: show incoming context for follow-up queries ──
        if body.context:
            log.info(f"CONTEXT RECEIVED: previousQuery='{body.context.get('previousQuery','')[:60]}' | "
                     f"previousAnswer_len={len(body.context.get('previousAnswer',''))} ")
        else:
            log.info(f"NO CONTEXT: initial query")

        log.info(f"Query: {q[:80]}{'...' if len(q) > 80 else ''}  "
                 f"[tier={tier}, confidence={confidence}, max_sources={preset['max_sources']}, lang={body.language}]")

        result = await run_pipeline(q, confidence=confidence, context=body.context, language=body.language)

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

        # Deduct from purchased credits if daily limit is exhausted
        from .subscriptions import get_user_daily_limit, get_queries_used_today, get_purchased_credits, deduct_purchased_credit
        daily_limit = get_user_daily_limit(user, db)
        used = get_queries_used_today(user, db)
        if used > daily_limit:
            deduct_purchased_credit(user, db)
        # Get final credit state
        used = get_queries_used_today(user, db)
        purchased = get_purchased_credits(user, db)
        credits = {
            "used": used,
            "limit": daily_limit,
            "remaining": max(0, daily_limit - used),
            "purchased_credits": purchased,
        }

        # Add credits info to the response
        result_dict = result.model_dump()
        result_dict["credits"] = credits
        return result_dict
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


@app.get("/api/auth/me")
async def get_current_user_info(request: Request):
    """Return current user info including admin status."""
    from .auth import get_current_user
    from .database import get_db
    from pydantic import BaseModel
    from typing import Optional

    class UserInfo(BaseModel):
        id: int
        email: str
        name: str
        is_admin: bool

    db = next(get_db())
    try:
        user = await get_current_user(request, db)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            is_admin=user.is_admin
        )
    finally:
        db.close()


@app.get("/api/currency/rates")
@limiter.limit("30/minute")
async def get_currency_rates(request: Request):
    """
    Fetch live exchange rates from open.er-api.com (free, no API key needed).
    Returns rates with EGP as base currency.
    Cached server-side for 1 hour to avoid rate limits.
    """
    import time
    import aiohttp
    import asyncio

    # Simple in-memory cache
    cache_key = "egp_rates"
    cache = getattr(get_currency_rates, "_cache", {})
    now = time.time()

    if cache_key in cache and now - cache[cache_key]["ts"] < 3600:
        return cache[cache_key]["data"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://open.er-api.com/v6/latest/EGP",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Cache result
                    cache[cache_key] = {"data": data, "ts": now}
                    get_currency_rates._cache = cache
                    return data
                else:
                    # Return stale cache if available
                    if cache_key in cache:
                        return cache[cache_key]["data"]
                    return {"result": "error", "base_code": "EGP", "rates": {"EGP": 1}}
    except Exception as e:
        log.warning(f"Failed to fetch exchange rates: {e}")
        if cache_key in cache:
            return cache[cache_key]["data"]
        return {"result": "error", "base_code": "EGP", "rates": {"EGP": 1}}


@app.post("/api/humanize")
@limiter.limit("20/minute")
async def humanize_answer(request: Request, body: HumanizeRequest):
    """
    Rewrite a clinical answer in warm, plain language.

    Takes the original synthesis HTML, strips it to plain text (preserving
    citation markers), sends it to the AI provider for a tone-only rewrite,
    and returns the humanized version with the same citations preserved.
    """
    from .ai_providers import get_provider, AIProviderError

    if not body.answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")

    # Strip HTML to plain text, but preserve citation markers like [1], [1][2]
    import re
    plain_text = re.sub(r'<[^>]+>', '', body.answer)
    # Normalise whitespace
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()

    # Map language codes to full names for the AI
    LANG_MAP = {
        "en": "English",
        "ar": "Arabic",
    }
    target_lang = LANG_MAP.get(body.language, "English")

    # Build source list for context
    sources_text = ""
    for i, src in enumerate(body.sources or [], start=1):
        sources_text += f"[{i}] {src.title} — {src.authors} ({src.journal}, {src.date})\n"

    humanize_prompt = (
        f"## Original Clinical Synthesis\n{plain_text}\n\n"
        + (f"## Sources Referenced\n{sources_text}\n\n" if sources_text else "")
        + "## Instructions\n"
        "Rewrite the synthesis above in a warmer, plain-language tone.\n\n"
        "IMPORTANT RULES:\n"
        "1. PRESERVE ALL citation markers EXACTLY — every [1], [2], etc. must stay exactly as written.\n"
        "2. Do NOT add, remove, or soften ANY medical claim or fact.\n"
        "3. Do NOT change confidence/certainty language — keep 'may indicate', 'suggests', 'is associated with' exactly as written.\n"
        "4. Do NOT introduce new information or examples not in the original.\n"
        "5. Make the tone warmer and more conversational:\n"
        "   - Explain medical terms in simple words or short parentheticals\n"
        "   - Use direct 'you' language where appropriate (e.g. 'your blood pressure' not 'the patient's blood pressure')\n"
        "   - Use contractions (it's, don't, can't)\n"
        "   - Break long sentences into shorter, clearer ones\n"
        "   - Keep the same paragraph structure and headings\n"
        "6. Output ONLY the rewritten text — no prefixes, no explanations.\n"
        f"7. You MUST write your entire answer in {target_lang}. The original text may be in a different language; translate it to {target_lang} while keeping all the medical facts exactly the same.\n"
    )

    try:
        provider = get_provider()
        humanized = await provider.complete(
            humanize_prompt,
            f"You are a medical writer who rewrites clinical content in warm, plain {target_lang} without changing any facts. "
            "Preserve all citations, all claims, all certainty language — only change the tone."
        )
        humanized = humanized.strip().strip('"').strip("'")

        if not humanized:
            log.warning("Humanizer returned empty response, falling back to original")
            return {"humanized": body.answer}

        log.info(f"Humanizer: rewrote {len(plain_text)} chars -> {len(humanized)} chars")
        return {"humanized": humanized}

    except AIProviderError as e:
        log.warning(f"Humanizer AI error: {e}, falling back to original")
        return {"humanized": body.answer}
    except Exception as e:
        log.warning(f"Humanizer unexpected error: {e}, falling back to original")
        return {"humanized": body.answer}


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
    print(f"  |  Payments: {'Paymob' if config.PAYMOB_API_KEY else 'not configured':<21s}|")
    print(f"  |  Admins:   {', '.join(config.ADMIN_EMAILS):<26s}|")
    print(f"  |  Press Ctrl+C to stop                        |")
    print(f"  +------------------------------------------------+")
    print()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
