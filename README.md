# Tax Lien Finder

An AI-assisted tax lien investment screener. Pulls real county tax lien
records into Postgres, filters them by value-to-lien ratio, and uses
Gemini to generate a plain-language summary of each opportunity.

Free-tier stack — no paid services required to run this.

## Stack

| Layer      | Choice                                   | Why                          |
|------------|-------------------------------------------|-------------------------------|
| Database   | Postgres (Neon / Supabase free tier)      | Both have a free tier w/ no card required for Neon |
| Backend    | Python + FastAPI                          | You asked for Python; async, minimal boilerplate |
| Ingestion  | `ingest.py` — pulls NYC Open Data (Socrata)| Only county found with a real JSON API, no scraping fragility |
| AI         | Gemini API (`gemini-2.0-flash`, free tier)| Enrichment text only — never in the filtering path |
| Frontend   | React (build next, not included here yet)| Hits `/api/listings` and `/api/listings/{id}/enrich` |
| Deploy     | Fly.io free allowance                     | Hosts both API and Postgres |

## Why NYC first

County tax lien data is not standardized. Most counties publish PDFs or
raw HTML tables meant for a browser, not a script (Pima County AZ,
DeKalb County GA — both checked). NYC and Allegheny County, PA are the
two exceptions with real open-data APIs (Socrata / CKAN). Starting with
a real API means the pipeline gets built once, correctly, instead of
being rebuilt every time a scraper breaks. Once this works end-to-end,
adding Allegheny County (or others) means writing one more `normalize_record`
function — the schema and API don't change.

## How the pieces fit together

```
ingest.py  →  Postgres (properties, tax_liens tables)
                    │
                    ▼
         lien_opportunities VIEW
         (precomputes value_to_lien_ratio,
          silently excludes incomplete rows)
                    │
                    ▼
            main.py (FastAPI)
         GET  /api/listings?min_ratio=3
         POST /api/listings/{id}/enrich   → Gemini
                    │
                    ▼
              React frontend (next)
```

**Filtering is pure SQL — deterministic, fast, no AI dependency.**
Gemini only touches the `/enrich` endpoint, and if it fails the listing
still returns fine, just without the summary. This is deliberate: your
core product (accurate filtering) never depends on an external AI call
succeeding.

## Backend structure

```
backend/
  app/
    main.py           # FastAPI app + lifespan (startup/shutdown)
    config.py         # env var validation (pydantic-settings)
    db.py             # Postgres pool lifecycle
    schemas.py        # response models (validation + auto docs at /docs)
    routers/
      listings.py     # GET /api/listings, POST /api/listings/{id}/enrich
    services/
      gemini.py       # enrichment only — never in the filtering path
    ingestion/
      common.py       # shared retry/backoff fetch helper
      nyc.py           # NYC-specific normalization + upsert
  scripts/
    run_ingest.py     # CLI entrypoint for ingestion
  schema.sql
  requirements.txt
```

Adding a second county later means one new file in `app/ingestion/`
that reuses `common.py` — the API, schema, and CLI script don't change.

## Setup — run this now

1. **Get a free Postgres instance.**
   [Neon](https://neon.tech) is the fastest path — free tier, no card,
   gives you a `DATABASE_URL` connection string immediately.

2. **Apply the schema.**
   ```bash
   cd backend
   psql "$DATABASE_URL" -f schema.sql
   ```

3. **Copy env vars and fill them in.**
   ```bash
   cp ../.env.example .env
   # edit .env with your DATABASE_URL and GEMINI_API_KEY
   ```

4. **Install dependencies.**
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Run the ingestion script.**
   ```bash
   python scripts/run_ingest.py
   ```
   Check the log line at the end — `ingested=N skipped=N`. Some skips
   are expected (rows missing assessed value or lien amount); a skip
   rate over ~30% means the dataset's field names likely changed and
   `app/ingestion/nyc.py`'s `normalize_record()` needs updating.

6. **Run the API.**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

7. **Test it.**
   ```bash
   curl "http://localhost:8000/api/listings?min_ratio=3&limit=10"
   ```
   You should get back real NYC properties with their computed
   value-to-lien ratios. Visit `http://localhost:8000/docs` for the
   interactive API docs FastAPI generates automatically from
   `schemas.py`.

## What's deliberately not built yet

- **React frontend** — next step, once you confirm the API returns
  real data you're happy with.
- **Fly.io deploy config** — trivial to add once the API is confirmed
  working locally; no reason to deploy before that.
- **Auth / user accounts** — not needed for a listings screener; add
  only if you build saved-search or portfolio-tracking features.
- **More counties** — Allegheny County is the next candidate (also has
  a real API). Each new county is one normalize function, not a rewrite.

## Known limitations (by design, not oversight)

- The NYC dataset resource ID in `.env.example` should be double
  checked against the current NYC Open Data portal before your first
  real run — Socrata resource IDs occasionally change.
- `value_to_lien_ratio` is only computed for liens with `lien_status = 'active'`
  and both figures present — that's intentional, not a bug, so the
  filter never surfaces stale or incomplete data as if it were solid.
