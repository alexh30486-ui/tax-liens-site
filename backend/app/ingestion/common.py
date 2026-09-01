"""
Shared HTTP fetch helper for ingestion scripts.

Previously this retry/backoff logic lived inline inside the NYC script,
which meant adding a second county (Allegheny, etc.) would mean copy-
pasting it. Pulled out here so every future county ingestion module
reuses the same tested retry behavior.
"""

import logging
import time
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)


def fetch_json_with_backoff(
    url: str,
    params: dict[str, Any],
    headers: Optional[dict[str, str]] = None,
    max_retries: int = 4,
    timeout: int = 30,
) -> list[dict]:
    """GET a JSON endpoint with exponential backoff on 429/5xx.

    Raises requests.HTTPError on other non-2xx statuses, or RuntimeError
    if retries are exhausted — both are meant to stop that county's
    ingestion run rather than silently returning nothing.
    """
    for attempt in range(max_retries + 1):
        resp = requests.get(url, params=params, headers=headers or {}, timeout=timeout)

        if resp.status_code == 429 or resp.status_code >= 500:
            backoff = (2**attempt) * 0.5
            log.warning("status %s from %s, retrying in %.1fs", resp.status_code, url, backoff)
            time.sleep(backoff)
            continue

        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(f"Exceeded max retries fetching {url}")
