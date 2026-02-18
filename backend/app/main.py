"""
SecureFlow AI — FastAPI Application Entry Point.
Configures CORS, rate limiting, routes, and startup events.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.db import init_db
from app.routers import health, sanitize, restore, sanitize_file

# ── Logging ───────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("secureflow")


# ── Lifespan (startup / shutdown) ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on startup and shutdown."""
    settings = get_settings()
    logger.info("🚀 SecureFlow AI backend starting…")
    logger.info(f"   spaCy model  : {settings.spacy_model}")
    logger.info(f"   BERT model   : {settings.bert_model_path}")
    logger.info(f"   Database     : {settings.database_url}")
    logger.info(f"   Token TTL    : {settings.token_map_ttl_minutes} min")

    # Initialize database
    await init_db()
    logger.info("   Database initialized ✓")

    yield

    logger.info("SecureFlow AI backend shutting down.")


# ── App ───────────────────────────────────────────────────────────

app = FastAPI(
    title="SecureFlow AI",
    description="Privacy-preserving proxy for LLM interactions",
    version="1.0.0",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────

settings = get_settings()
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins and origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Optional API Key Auth ─────────────────────────────────────────

async def verify_api_key(request: Request):
    """Verify the X-API-Key header if API_KEY is configured."""
    api_key = settings.api_key
    if not api_key:
        return  # No auth configured

    provided = request.headers.get("X-API-Key", "")
    if provided != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── Routes ────────────────────────────────────────────────────────

app.include_router(
    health.router,
    prefix="/api/v1",
)

app.include_router(
    sanitize.router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
)

app.include_router(
    restore.router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
)

app.include_router(
    sanitize_file.router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)],
)


# ── Global Exception Handler ─────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Root redirect ────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "SecureFlow AI API — visit /docs for Swagger UI"}
