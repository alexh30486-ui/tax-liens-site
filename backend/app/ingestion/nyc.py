"""
NYC Tax Lien Sale List ingestion.

Source: NYC Open Data (Socrata) — Tax Lien Sale Lists dataset
  https://data.cityofnewyork.us/dataset/tax-lien-sale-lists

Kept synchronous (psycopg2) deliberately — this runs as a standalone
batch job (cron/manual), not inside the async web server, so there's
no benefit to asyncio here and it stays simpler to read and debug.
"""

import json
import logging
from typing import Optional

import psycopg2

from app.ingestion.common import fetch_json_with_backoff

log = logging.getLogger(__name__)

PAGE_LIMIT = 1000
SOURCE_URL = "https://data.cityofnewyork.us/dataset/tax-lien-sale-lists"


def normalize_record(raw: dict) -> Optional[tuple[dict, dict]]:
    """Returns (property_dict, lien_dict), or None if the row can't be used.
    Never raises — a malformed row is logged and skipped, not fatal."""
    try:
        parcel_id = raw.get("boro_block_lot") or raw.get("parcel_id") or raw.get("bbl")
        lien_amount_raw = raw.get("total_amount_due") or raw.get("lien_amount")
        lien_amount = float(lien_amount_raw) if lien_amount_raw not in (None, "") else None

        if not parcel_id or lien_amount is None:
            log.warning("skipping row — missing parcel id or lien amount: %s", raw)
            return None

        if raw.get("house_number") and raw.get("street_name"):
            address = f"{raw['house_number']} {raw['street_name']}"
        else:
            address = raw.get("address")

        assessed_value_raw = raw.get("assessed_value")
        assessed_value = (
            float(assessed_value_raw) if assessed_value_raw not in (None, "") else None
        )

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
            "source_county_url": SOURCE_URL,
            "raw_payload": json.dumps(raw),
        }

        return property_dict, lien_dict

    except Exception:
        log.exception("normalization error, skipping row: %s", raw)
        return None


def upsert_record(cur, property_dict: dict, lien_dict: dict) -> None:
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

    cur.execute(
        """
        INSERT INTO tax_liens
            (property_id, lien_amount, interest_rate, auction_date, lien_status,
             source_county_url, raw_payload)
        VALUES (%(property_id)s, %(lien_amount)s, %(interest_rate)s, %(auction_date)s,
                %(lien_status)s, %(source_county_url)s, %(raw_payload)s)
        """,
        {**lien_dict, "property_id": property_id},
    )


def run(database_url: str, endpoint: str, app_token: str = "") -> None:
    conn = psycopg2.connect(database_url)
    conn.autocommit = False

    offset = 0
    total_ingested = 0
    total_skipped = 0
    headers = {"X-App-Token": app_token} if app_token else {}

    try:
        while True:
            page = fetch_json_with_backoff(
                endpoint, params={"$limit": PAGE_LIMIT, "$offset": offset}, headers=headers
            )
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
