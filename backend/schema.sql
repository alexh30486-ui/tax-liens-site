-- ============================================================
-- Tax Lien Finder v2 — Full schema
-- Compatible with: Neon, Supabase, local Postgres 14+
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------
-- users
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- properties
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS properties (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parcel_id       TEXT NOT NULL,
    county          TEXT NOT NULL,
    state           TEXT NOT NULL,
    address         TEXT,
    city            TEXT,
    zip             TEXT,
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION,
    assessed_value  NUMERIC(14,2),
    property_type   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (county, state, parcel_id)
);

-- ------------------------------------------------------------
-- tax_liens
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tax_liens (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id        UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    lien_amount        NUMERIC(14,2) NOT NULL,
    interest_rate      NUMERIC(5,2),
    redemption_period  INTERVAL,
    auction_date       DATE,
    lien_status        TEXT NOT NULL DEFAULT 'active'
                        CHECK (lien_status IN ('active','redeemed','sold','expired','unknown')),
    source_county_url  TEXT,
    raw_payload        JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tax_liens_property_id ON tax_liens(property_id);
CREATE INDEX IF NOT EXISTS idx_tax_liens_status ON tax_liens(lien_status);
CREATE INDEX IF NOT EXISTS idx_properties_county_state ON properties(county, state);

-- ------------------------------------------------------------
-- Core product view: value-to-lien ratio (pure SQL, no AI)
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW lien_opportunities AS
SELECT
    p.id                AS property_id,
    p.parcel_id,
    p.address,
    p.city,
    p.state,
    p.county,
    p.zip,
    p.assessed_value,
    p.property_type,
    t.id                AS lien_id,
    t.lien_amount,
    t.interest_rate,
    t.redemption_period,
    t.auction_date,
    t.lien_status,
    t.source_county_url,
    ROUND(p.assessed_value / NULLIF(t.lien_amount, 0), 2) AS value_to_lien_ratio
FROM properties p
JOIN tax_liens t ON t.property_id = p.id
WHERE p.assessed_value IS NOT NULL
  AND t.lien_amount IS NOT NULL
  AND t.lien_amount > 0
  AND t.lien_status = 'active';
