#!/usr/bin/env python3
"""
Push all lien_opportunities rows into Meilisearch.

Usage (from backend/):
  PYTHONPATH=src python scripts/reindex_meili.py
"""

from __future__ import annotations

import logging
import os
import sys

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.config import get_settings
from app.services import meili

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("reindex")


def main() -> None:
    settings = get_settings()
    if not settings.meili_enabled:
        log.error("Meilisearch not configured. Set MEILI_URL and MEILI_MASTER_KEY in .env")
        sys.exit(1)

    if not meili.ensure_index():
        log.error("Could not reach Meilisearch at %s", settings.meili_url)
        sys.exit(1)

    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM lien_opportunities")
            rows = cur.fetchall()
        docs = [meili.listing_to_doc(dict(r)) for r in rows]
        task = meili.index_documents(docs)
        log.info("Indexed %s documents (task=%s)", len(docs), task)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
