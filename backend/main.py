"""
Tax Lien API — FastAPI backend

Filtering is pure SQL (fast, deterministic, no AI dependency).
Gemini is used only for enrichment text — if it fails, listings
still return successfully with enrichment omitted.

Run: uvicorn main:app --reload --port 8000
"""

import os
import logging
from typing import Optional

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tax-lien-api")

DATABASE_URL = os.environ["DATABASE_URL"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"

app = FastAPI(title="Tax Lien API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before real production launch
    allow_methods=["*"],
    allow_headers=["*"],
)

pool: Optional[asyncpg.Pool] = None


@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()


class Listing(BaseModel):
    property_id: str
    parcel_id: str
    address: Optional[str]
    city: Optional[str]
    state: str
    county: str
    assessed_value: Optional[float]
    lien_id: str
    lien_amount: float
    interest_rate: Optional[float]
    lien_status: str
    value_to_lien_ratio: Optional[float]


@app.get("/api/listings")
async def get_listings(
    min_ratio: float = Query(0, ge=0),
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = Query(50, le=200),
):
    conditions = ["value_to_lien_ratio >= $1"]
    params = [min_ratio]

    if state:
        params.append(state)
        conditions.append(f"state = ${len(params)}")
    if county:
        params.append(county)
        conditions.append(f"county = ${len(params)}")

    params.append(limit)

    query = f"""
        SELECT * FROM lien_opportunities
        WHERE {' AND '.join(conditions)}
        ORDER BY value_to_lien_ratio DESC
        LIMIT ${len(params)}
    """

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        return {"count": len(rows), "listings": [dict(r) for r in rows]}
    except Exception:
        log.exception("Failed to fetch listings")
        raise HTTPException(status_code=500, detail="Failed to fetch listings. Please try again.")


@app.post("/api/listings/{lien_id}/enrich")
async def enrich_listing(lien_id: str):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM lien_opportunities WHERE lien_id = $1", lien_id
            )
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")

        listing = dict(row)
        summary = await generate_summary(listing)
        return {**listing, "ai_summary": summary}

    except HTTPException:
        raise
    except Exception:
        # Enrichment failures degrade gracefully — never a hard failure.
        log.exception("Enrichment failed, returning listing without it")
        return {"ai_summary": None, "error": "Enrichment unavailable"}


async def generate_summary(listing: dict) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None

    prompt = f"""Summarize this tax lien investment opportunity in 2-3 plain-language
sentences aimed at a first-time investor. Mention the value-to-lien ratio and note
any obvious risk. Do not invent numbers not given below.

Address: {listing.get('address')}, {listing.get('city')}, {listing.get('state')}
Assessed value: ${listing.get('assessed_value')}
Lien amount: ${listing.get('lien_amount')}
Value-to-lien ratio: {listing.get('value_to_lien_ratio')}
Interest rate: {listing.get('interest_rate', 'unknown')}%"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url, json={"contents": [{"parts": [{"text": prompt}]}]}
            )
        if resp.status_code != 200:
            log.error("Gemini request failed: %s %s", resp.status_code, resp.text)
            return None
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        log.exception("Gemini call errored")
        return None


@app.get("/health")
async def health():
    return {"status": "ok"}
