#!/usr/bin/env python3
"""
Ingest NYC tax lien records into Postgres.

Usage (from backend/):
  PYTHONPATH=src python scripts/run_ingest.py
"""

from __future__ import annotations

import logging
import os
import sys

# Allow running without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.config import get_settings
from app.ingestion.nyc import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    settings = get_settings()
    run(
        database_url=settings.database_url,
        endpoint=settings.nyc_lien_endpoint,
        app_token=settings.socrata_app_token,
    )


if __name__ == "__main__":
    main()
