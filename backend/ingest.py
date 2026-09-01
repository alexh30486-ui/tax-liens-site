"""
NYC Tax Lien Sale List — Ingestion Script (Python)

Source: NYC Open Data (Socrata) — Tax Lien Sale Lists dataset
  https://data.cityofnewyork.us/dataset/tax-lien-sale-lists

Design goals:
  - Never crash on a malformed/missing field — log + skip that row, keep going.
  - Store the full raw record in raw_payload so schema drift never loses data.
  - Upsert on (county, state, parcel_id) so re-running is safe (idempotent).
  - Retry with backoff on rate limiting (Socrata 429s).

Run: python ingest.py
"""

import os
import time
import logging
import json

import requests
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ingest")

DATABASE_URL = os.environ["DATABASE_URL"]
SOCRATA_ENDPOINT = os.environ.get(
    "NYC_LIEN_ENDPOINT", "https://data.cityofnewyork.us/resource/9rz4-mjek.json"
)
APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN", "")

PAGE_LIMIT = 1000
MAX_RETRIES = 4


def fetch_page(offset: int) -> list:
    params = {"$limit": PAGE_LIMIT, "$offset": offset}
    headers = {"X-App-Token": APP_TOKEN} if APP_TOKEN else {}

    for attempt in range(MAX_RETRIES + 1):
        resp = requests.get(SOCRATA_ENDPOINT, params=params, headers=headers, timeout=30)

        if resp.status_code == 429 or resp.status_code >= 500:
            backoff = (2 ** attempt) * 0.5
            log.warning("status %s, retrying in %.1fs", resp.status_code, backoff)
            time.sleep(backoff)
            continue

        resp.raise_for_status()
        return resp.json()

    raise RuntimeError("Exceeded max retries fetching page")


def normalize_record(raw: dict):
    """Returns (property_dict, lien_dict) or None if the row can't be used."""
    try:
        parcel_id = raw.get("boro_block_lot") or raw.get("parcel_id") or raw.get("bbl")
        lien_amount_raw = raw.get("total_amount_due") or raw.get("lien_amount")
        lien_amount = float(lien_amount_raw) if lien_amount_raw not in (None, "") else None

        if not parcel_id or lien_amount is None:
            log.warning("skipping row — missing parcel id or lien amount: %s", raw)
            return None

        address = None
        if raw.get("house_number") and raw.get("street_name"):
            address = f"{raw['house_number']} {raw['street_name']}"
        else:
            address = raw.get("address")

        assessed_value = raw.get("assessed_value")
        assessed_value = float(assessed_value) if assessed_value not in (None, "") else None

        property_dict = {
            "parcel_id": str(parcel_id),
            "county": "New York",
            "state": "NY",
            "address": address,
            "city": raw.get("borough"),
            "zip": raw.get("zip_code"),
            "assessed_value": assessed_value,
            "property_type": raw.get("property_type") or raw.get("bldg_class"),
        }

        lien_dict = {
            "lien_amount": lien_amount,
            "interest_rate": float(raw["interest_rate"]) if raw.get("interest_rate") else None,
            "auction_date": raw.get("lien_sale_date"),
            "lien_status": "active",
            "source_county_url": "https://data.cityofnewyork.us/dataset/tax-lien-sale-lists",
            "raw_payload": json.dumps(raw),
        }

        return property_dict, lien_dict

    except Exception:
        log.exception("normalization error, skipping row: %s", raw)
        return None


def upsert_record(cur, property_dict: dict, lien_dict: dict):
    cur.execute(
        """
        INSERT INTO properties
            (parcel_id, county, state, address, city, zip, assessed_value, property_type)
        VALUES (%(parcel_id)s, %(county)s, %(state)s, %(address)s, %(city)s,
                %(zip)s, %(assessed_value)s, %(property_type)s)
        ON CONFLICT (county, state, parcel_id) DO UPDATE SET
            address = EXCLUDED.address,
            city = EXCLUDED.city,
            zip = EXCLUDED.zip,
            assessed_value = COALESCE(EXCLUDED.assessed_value, properties.assessed_value),
            property_type = EXCLUDED.property_type,
            updated_at = now()
        RETURNING id
        """,
        property_dict,
    )
    property_id = cur.fetchone()[0]

    lien_dict = {**lien_dict, "property_id": property_id}
    cur.execute(
        """
        INSERT INTO tax_liens
            (property_id, lien_amount, interest_rate, auction_date, lien_status,
             source_county_url, raw_payload)
        VALUES (%(property_id)s, %(lien_amount)s, %(interest_rate)s, %(auction_date)s,
                %(lien_status)s, %(source_county_url)s, %(raw_payload)s)
        """,
        lien_dict,
    )


def run():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False

    offset = 0
    total_ingested = 0
    total_skipped = 0

    try:
        while True:
            page = fetch_page(offset)
            if not page:
                break

            with conn.cursor() as cur:
                for raw in page:
                    normalized = normalize_record(raw)
                    if normalized is None:
                        total_skipped += 1
                        continue
                    try:
                        upsert_record(cur, *normalized)
                        total_ingested += 1
                    except Exception:
                        log.exception("upsert failed for row, skipping")
                        conn.rollback()
                        total_skipped += 1
                        continue
                conn.commit()

            offset += PAGE_LIMIT

    finally:
        conn.close()

    log.info("done. ingested=%d skipped=%d", total_ingested, total_skipped)


if __name__ == "__main__":
    run()
