"""
NYC Open Data (Socrata) tax lien sale list ingestion.

Dataset: https://data.cityofnewyork.us/resource/9rz4-mjek.json
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import psycopg2
from psycopg2.extras import Json

from app.ingestion.common import PAGE_LIMIT, fetch_json_with_backoff

log = logging.getLogger(__name__)


def _num(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def normalize_record(raw: dict) -> Optional[tuple[dict, dict]]:
    """
    Map one Socrata row → (property_dict, lien_dict).
    Returns None if the row cannot produce a usable lien amount.
    """
    # Field names vary slightly across dataset versions; be defensive.
    parcel = (
        raw.get("borough_block_lot")
        or raw.get("bbl")
        or raw.get("parcel_id")
        or raw.get("tax_block")
    )
    if not parcel:
        return None

    lien_amount = _num(
        raw.get("total_debt")
        or raw.get("lien_amount")
        or raw.get("amount")
        or raw.get("current_balance")
    )
    if lien_amount is None or lien_amount <= 0:
        return None

    assessed = _num(
        raw.get("assessed_value")
        or raw.get("market_value")
        or raw.get("assessed_total")
    )

    address = raw.get("property_address") or raw.get("address") or raw.get("street_address")
    borough = raw.get("borough") or raw.get("boro") or "NYC"
    city = raw.get("city") or borough
    zip_code = raw.get("zip") or raw.get("zip_code") or raw.get("postcode")

    interest = _num(raw.get("interest_rate") or raw.get("rate"))

    property_dict = {
        "parcel_id": str(parcel).strip(),
        "county": "New York City",
        "state": "NY",
        "address": address,
        "city": city,
        "zip": str(zip_code) if zip_code else None,
        "assessed_value": assessed,
        "property_type": raw.get("building_class") or raw.get("property_type"),
    }

    lien_dict = {
        "lien_amount": lien_amount,
        "interest_rate": interest,
        "auction_date": raw.get("auction_date") or raw.get("sale_date"),
        "lien_status": "active",
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
        "raw_payload": Json(raw) if raw else None,
    }
    return property_dict, lien_dict


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
            log.info("offset=%s ingested=%s skipped=%s", offset, total_ingested, total_skipped)

    finally:
        conn.close()

    log.info("done. ingested=%d skipped=%d", total_ingested, total_skipped)
