"""Listings and AI-enrich endpoints. Filtering is pure SQL."""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.db import get_pool
from app.rate_limit import limiter
from app.schemas import EnrichedListing, ListingsResponse
from app.services import gemini

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/listings", tags=["listings"])


def _row_to_listing(row) -> dict:
    d = dict(row)
    # asyncpg returns UUID/Decimal — coerce for JSON
    for key in ("property_id", "lien_id"):
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    for key in ("assessed_value", "lien_amount", "interest_rate", "value_to_lien_ratio"):
        if key in d and d[key] is not None:
            d[key] = float(d[key])
    if d.get("redemption_period") is not None:
        d["redemption_period"] = str(d["redemption_period"])
    return d


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
        params.append(state.upper())
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
        listings = [_row_to_listing(r) for r in rows]
        return {"count": len(listings), "listings": listings}
    except Exception:
        log.exception("Failed to fetch listings")
        raise HTTPException(status_code=500, detail="Failed to fetch listings. Please try again.")


@router.get("/{lien_id}", response_model=EnrichedListing)
async def get_listing(lien_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM lien_opportunities WHERE lien_id = $1", lien_id
            )
    except Exception:
        log.exception("Failed to fetch listing")
        raise HTTPException(status_code=500, detail="Failed to fetch listing.")

    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing = _row_to_listing(row)
    listing["ai_summary"] = None
    return listing


@router.post("/{lien_id}/enrich", response_model=EnrichedListing)
@limiter.limit("20/minute")
async def enrich_listing(request: Request, lien_id: str, pool: asyncpg.Pool = Depends(get_pool)):
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

    listing = _row_to_listing(row)
    listing["ai_summary"] = await gemini.generate_summary(listing)
    return listing
