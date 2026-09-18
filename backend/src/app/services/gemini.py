"""Gemini enrichment — optional; failures never block a listing."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def generate_summary(listing: dict) -> Optional[str]:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None

    prompt = f"""Summarize this tax lien investment opportunity in 2-3 plain-language
sentences aimed at a first-time investor. Mention the value-to-lien ratio and note
any obvious risk. Do not invent numbers not given below.

Address: {listing.get('address')}, {listing.get('city')}, {listing.get('state')}
Assessed value: ${listing.get('assessed_value')}
Lien amount: ${listing.get('lien_amount')}
Value-to-lien ratio: {listing.get('value_to_lien_ratio')}
Interest rate: {listing.get('interest_rate')}
County: {listing.get('county')}
"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
        f"?key={settings.gemini_api_key}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        client = _get_client()
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        log.exception("Gemini summary failed")
        return None
