"""
App entrypoint. Run: uvicorn app.main:app --reload --port 8000 (from backend/)

Fix from the previous version: replaced @app.on_event("startup"/"shutdown"),
which is deprecated in current FastAPI, with the lifespan context manager.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool, init_pool
from app.routers import listings
from app.services import gemini

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_pool(settings.database_url)
    yield
    await gemini.close_client()
    await close_pool()


app = FastAPI(title="Tax Lien API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your real frontend origin before production launch
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(listings.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
