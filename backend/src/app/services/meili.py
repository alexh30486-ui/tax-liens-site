"""Meilisearch client: index sync + search."""

from __future__ import annotations

import logging
from typing import Any, Optional

import meilisearch
from meilisearch.errors import MeilisearchApiError

from app.config import get_settings

log = logging.getLogger(__name__)

_client: Optional[meilisearch.Client] = None


def get_client() -> Optional[meilisearch.Client]:
    global _client
    settings = get_settings()
    if not settings.meili_enabled:
        return None
    if _client is None:
        _client = meilisearch.Client(settings.meili_url, settings.meili_master_key)
    return _client


def ensure_index() -> bool:
    """Create index and settings if missing. Returns False if Meili disabled/unreachable."""
    client = get_client()
    if client is None:
        return False
    settings = get_settings()
    try:
        try:
            client.get_index(settings.meili_index)
        except MeilisearchApiError:
            client.create_index(settings.meili_index, {"primaryKey": "lien_id"})

        index = client.index(settings.meili_index)
        index.update_filterable_attributes(
            ["state", "county", "lien_status", "value_to_lien_ratio", "city"]
        )
        index.update_sortable_attributes(["value_to_lien_ratio", "lien_amount", "assessed_value"])
        index.update_searchable_attributes(
            ["address", "city", "county", "state", "parcel_id", "property_type"]
        )
        return True
    except Exception:
        log.exception("Meilisearch ensure_index failed")
        return False


def listing_to_doc(listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "lien_id": str(listing["lien_id"]),
        "property_id": str(listing.get("property_id", "")),
        "parcel_id": listing.get("parcel_id") or "",
        "address": listing.get("address") or "",
        "city": listing.get("city") or "",
        "state": listing.get("state") or "",
        "county": listing.get("county") or "",
        "zip": listing.get("zip") or "",
        "assessed_value": float(listing["assessed_value"]) if listing.get("assessed_value") is not None else None,
        "lien_amount": float(listing["lien_amount"]) if listing.get("lien_amount") is not None else None,
        "value_to_lien_ratio": float(listing["value_to_lien_ratio"])
        if listing.get("value_to_lien_ratio") is not None
        else None,
        "interest_rate": float(listing["interest_rate"]) if listing.get("interest_rate") is not None else None,
        "lien_status": listing.get("lien_status") or "active",
        "property_type": listing.get("property_type") or "",
        "source_county_url": listing.get("source_county_url") or "",
    }


def index_documents(docs: list[dict[str, Any]]) -> Optional[str]:
    client = get_client()
    if client is None or not docs:
        return None
    settings = get_settings()
    ensure_index()
    task = client.index(settings.meili_index).add_documents(docs)
    return str(task.task_uid) if hasattr(task, "task_uid") else str(task)


def search(
    query: str,
    *,
    min_ratio: float = 0,
    state: Optional[str] = None,
    county: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Full-text search with optional filters.
    Raises RuntimeError if Meili is not configured.
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Meilisearch is not configured (set MEILI_URL and MEILI_MASTER_KEY)")

    settings = get_settings()
    filters: list[str] = []
    if min_ratio > 0:
        filters.append(f"value_to_lien_ratio >= {min_ratio}")
    if state:
        filters.append(f'state = "{state.upper()}"')
    if county:
        filters.append(f'county = "{county}"')

    opts: dict[str, Any] = {
        "limit": min(limit, 200),
        "sort": ["value_to_lien_ratio:desc"],
    }
    if filters:
        opts["filter"] = " AND ".join(filters)

    result = client.index(settings.meili_index).search(query or "", opts)
    hits = result.get("hits") or []
    return {
        "query": query,
        "count": len(hits),
        "estimated_total": result.get("estimatedTotalHits", len(hits)),
        "listings": hits,
    }


def health() -> dict[str, Any]:
    client = get_client()
    if client is None:
        return {"enabled": False, "ok": False, "detail": "not configured"}
    try:
        info = client.health()
        return {"enabled": True, "ok": info.get("status") == "available", "detail": info}
    except Exception as exc:
        return {"enabled": True, "ok": False, "detail": str(exc)}
