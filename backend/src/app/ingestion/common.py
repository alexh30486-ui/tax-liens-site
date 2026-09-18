"""Shared HTTP helpers for county open-data pulls."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

PAGE_LIMIT = 1000
MAX_RETRIES = 5


def fetch_json_with_backoff(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
) -> list[dict[str, Any]]:
    """GET JSON with exponential backoff on 429/5xx."""
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, headers=headers or {}, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("HTTP %s from %s — retry in %.1fs", resp.status_code, url, delay)
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return []
        except requests.RequestException as exc:
            log.warning("Request failed (%s) — retry in %.1fs", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 30)
    log.error("Gave up after %s retries: %s", MAX_RETRIES, url)
    return []
