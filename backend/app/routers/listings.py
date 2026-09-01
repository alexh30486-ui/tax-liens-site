"""
Listings endpoints.

Bug fixed from the previous version: enrich_listing() used to wrap the
*entire* handler — including the database lookup — in one broad
try/except that returned HTTP 200 with {"ai_summary": null, "error": ...}
on ANY failure. That silently turned real database errors into what
looked like a successful response. Now only the Gemini call is allowed
to fail softly; a DB failure or missing listing still returns the
correct error status (500 / 404).
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_pool
from app.schemas import EnrichedListing, ListingsResponse
from app.services import gemini

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("", response_model=ListingsResponse)
async def get_listings(
    min_ratio: float = Query(0, ge=0, description="Minimum value-to-lien ratio"),
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    pool: asyncpg.Pool = Depends(get_pool),
):
    conditions = ["value_to_lien_ratio >= $1"]
    params: list = [min_ratio]

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


@router.post("/{lien_id}/enrich", response_model=EnrichedListing)
async def enrich_listing(lien_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM lien_opportunities WHERE lien_id = $1", lien_id
            )
    except Exception:
        log.exception("Database lookup failed during enrichment")
        raise HTTPException(status_code=500, detail="Failed to fetch listing. Please try again.")

    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing = dict(row)
    # Only this call is allowed to fail softly — a broken AI call should
    # never hide a real listing behind an error.
    listing["ai_summary"] = await gemini.generate_summary(listing)
    return listing
