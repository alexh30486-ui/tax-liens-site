"""Meilisearch-backed search API."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas import SearchResponse
from app.services import meili

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_listings(
    q: str = Query("", max_length=200, description="Full-text query (address, city, parcel…)"),
    min_ratio: float = Query(0, ge=0),
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return meili.search(q, min_ratio=min_ratio, state=state, county=county, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        log.exception("Search failed")
        raise HTTPException(status_code=500, detail="Search failed. Is Meilisearch running?")
