#!/usr/bin/env python3
"""
Seed demo listings so the app works before (or without) live NYC ingest.

Usage (from backend/):
  PYTHONPATH=src python scripts/seed_demo.py
"""

from __future__ import annotations

import os
import sys

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.config import get_settings

DEMO = [
    {
        "parcel_id": "DEMO-412-GLENWOOD",
        "county": "Queens",
        "state": "NY",
        "address": "412 Glenwood Ave",
        "city": "Queens",
        "zip": "11385",
        "assessed_value": 187000,
        "property_type": "residential",
        "lien_amount": 55000,
        "interest_rate": 18.0,
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
    },
    {
        "parcel_id": "DEMO-88-BEDFORD",
        "county": "Brooklyn",
        "state": "NY",
        "address": "88 Bedford Ave",
        "city": "Brooklyn",
        "zip": "11249",
        "assessed_value": 420000,
        "property_type": "residential",
        "lien_amount": 62000,
        "interest_rate": 16.0,
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
    },
    {
        "parcel_id": "DEMO-2100-3RD",
        "county": "Manhattan",
        "state": "NY",
        "address": "2100 3rd Ave",
        "city": "New York",
        "zip": "10029",
        "assessed_value": 910000,
        "property_type": "mixed",
        "lien_amount": 145000,
        "interest_rate": 18.0,
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
    },
    {
        "parcel_id": "DEMO-15-MAPLE",
        "county": "Bronx",
        "state": "NY",
        "address": "15 Maple St",
        "city": "Bronx",
        "zip": "10451",
        "assessed_value": 98000,
        "property_type": "residential",
        "lien_amount": 41000,
        "interest_rate": 18.0,
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
    },
    {
        "parcel_id": "DEMO-77-OCEAN",
        "county": "Staten Island",
        "state": "NY",
        "address": "77 Ocean Terrace",
        "city": "Staten Island",
        "zip": "10301",
        "assessed_value": 265000,
        "property_type": "residential",
        "lien_amount": 38000,
        "interest_rate": 16.0,
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
    },
    {
        "parcel_id": "DEMO-501-LIBERTY",
        "county": "Brooklyn",
        "state": "NY",
        "address": "501 Liberty Ave",
        "city": "Brooklyn",
        "zip": "11207",
        "assessed_value": 156000,
        "property_type": "commercial",
        "lien_amount": 89000,
        "interest_rate": 18.0,
        "source_county_url": "https://data.cityofnewyork.us/City-Government/Lien-Sale-List/9rz4-mjek",
    },
]


def main() -> None:
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    try:
        with conn.cursor() as cur:
            for row in DEMO:
                cur.execute(
                    """
                    INSERT INTO properties
                        (parcel_id, county, state, address, city, zip, assessed_value, property_type)
                    VALUES (%(parcel_id)s, %(county)s, %(state)s, %(address)s, %(city)s,
                            %(zip)s, %(assessed_value)s, %(property_type)s)
                    ON CONFLICT (county, state, parcel_id) DO UPDATE SET
                        assessed_value = EXCLUDED.assessed_value,
                        updated_at = now()
                    RETURNING id
                    """,
                    row,
                )
                property_id = cur.fetchone()[0]
                # Avoid duplicate liens on re-seed: only insert if none exist for this property
                cur.execute(
                    "SELECT 1 FROM tax_liens WHERE property_id = %s AND lien_status = 'active' LIMIT 1",
                    (property_id,),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    """
                    INSERT INTO tax_liens
                        (property_id, lien_amount, interest_rate, lien_status, source_county_url)
                    VALUES (%s, %s, %s, 'active', %s)
                    """,
                    (property_id, row["lien_amount"], row["interest_rate"], row["source_county_url"]),
                )
        conn.commit()
        print(f"Seeded {len(DEMO)} demo properties.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
