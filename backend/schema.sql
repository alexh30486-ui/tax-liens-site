-- ============================================================
-- Tax Lien Investment App — Core Schema
-- Target: PostgreSQL 14+
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------
-- properties: one row per physical property
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS properties (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_id       TEXT NOT NULL,          -- county-assigned parcel/BBL number
    county          TEXT NOT NULL,
    state           TEXT NOT NULL,
    address         TEXT,
    city            TEXT,
    zip             TEXT,
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION,
    assessed_value  NUMERIC(14,2),          -- nullable: some counties omit this
    property_type   TEXT,                   -- residential / commercial / vacant / etc
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (county, state, parcel_id)
);

-- ------------------------------------------------------------
-- tax_liens: one row per lien event on a property
-- (a property can have multiple liens over time; keep history)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tax_liens (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id        UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    lien_amount        NUMERIC(14,2) NOT NULL,
    interest_rate      NUMERIC(5,2),         -- percent, e.g. 16.00
    redemption_period  INTERVAL,             -- e.g. '3 years'
    auction_date       DATE,
    lien_status        TEXT NOT NULL DEFAULT 'active'
                        CHECK (lien_status IN ('active','redeemed','sold','expired','unknown')),
    source_county_url  TEXT,                 -- link back to original record for auditing
    raw_payload        JSONB,                -- full original record, for when the source schema drifts
    ingested_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tax_liens_property_id ON tax_liens(property_id);
CREATE INDEX IF NOT EXISTS idx_tax_liens_status ON tax_liens(lien_status);
CREATE INDEX IF NOT EXISTS idx_properties_county_state ON properties(county, state);

-- ------------------------------------------------------------
-- View: precomputes the value-to-lien ratio (your core filter)
-- Excludes rows missing either figure instead of erroring.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW lien_opportunities AS
SELECT
    p.id                AS property_id,
    p.parcel_id,
    p.address,
    p.city,
    p.state,
    p.county,
    p.assessed_value,
    t.id                AS lien_id,
    t.lien_amount,
    t.interest_rate,
    t.redemption_period,
    t.lien_status,
    ROUND(p.assessed_value / NULLIF(t.lien_amount, 0), 2) AS value_to_lien_ratio
FROM properties p
JOIN tax_liens t ON t.property_id = p.id
WHERE p.assessed_value IS NOT NULL
  AND t.lien_amount IS NOT NULL
  AND t.lien_amount > 0
  AND t.lien_status = 'active';

-- Example query for your stated criteria (ratio >= 3, i.e. lien is
-- worth 3x+ less than the property — a conservative safety margin):
--
-- SELECT * FROM lien_opportunities
-- WHERE value_to_lien_ratio >= 3
-- ORDER BY value_to_lien_ratio DESC;
