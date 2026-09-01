"""
Gemini enrichment.

Fix from the previous version: a new httpx.AsyncClient was opened and
closed on every single request, which is wasteful and drops connection
reuse. This module keeps one client for the process lifetime, closed
explicitly on app shutdown.

Enrichment failures return None rather than raising — by design, a
listing should never fail to load just because the AI summary failed.
"""

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
Interest rate: {listing.get('interest_rate', 'unknown')}%"""

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )

    try:
        client = _get_client()
        resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
        if resp.status_code != 200:
            log.error("Gemini request failed: %s %s", resp.status_code, resp.text)
            return None
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        log.exception("Gemini call errored")
        return None
