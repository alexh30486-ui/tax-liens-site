"""
CLI entrypoint. Run from the backend/ directory: python scripts/run_ingest.py
"""

import logging
import os
import sys

# Ensure backend/ is on sys.path regardless of the cwd this is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings  # noqa: E402
from app.ingestion import nyc  # noqa: E402

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    settings = get_settings()
    nyc.run(
        database_url=settings.database_url,
        endpoint=settings.nyc_lien_endpoint,
        app_token=settings.socrata_app_token,
    )
