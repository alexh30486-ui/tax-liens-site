"""
Tax Lien Finder API — entrypoint.

Dev:
  uvicorn app.main:app --reload --port 8000 --app-dir src

Prod (Gunicorn + Uvicorn workers):
  cd backend && PYTHONPATH=src gunicorn -c ../deploy/gunicorn/gunicorn.conf.py app.main:app
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db import close_pool, init_pool
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.rate_limit import limiter
from app.routers import auth, listings, search
from app.services import gemini, meili

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_pool(settings.database_url)
    if settings.meili_enabled:
        ok = meili.ensure_index()
        log.info("Meilisearch index ready=%s", ok)
    else:
        log.warning("Meilisearch disabled — set MEILI_URL and MEILI_MASTER_KEY to enable search")
    yield
    await gemini.close_client()
    await close_pool()


app = FastAPI(
    title="Tax Lien Finder API",
    version="2.1.0",
    description="Screen tax liens by value-to-lien ratio. SQL filters + Meilisearch + optional Gemini.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    expose_headers=["X-Request-Id", "X-App-Env"],
)

app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(search.router)


@app.get("/health")
async def health():
    settings = get_settings()
    meili_status = meili.health()
    return {
        "status": "ok",
        "version": "2.1.0",
        "env": settings.app_env,
        "meilisearch": meili_status,
    }
