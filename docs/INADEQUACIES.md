# Inadequacies of the original Tax Lien Finder (v1)

This document lists every material gap found in the unfinished project
that v2 is designed to close.

## Product / UX

1. **No real app after signup** — Signup redirected to the marketing page.
   There was no listings browser, filters, or detail view.
2. **Missing `login.html`** — Linked from signup but the file did not exist.
3. **Static marketing only** — Polished landing + form; zero product surface.
4. **API base hardcoded to `localhost:8000`** — Broke as soon as the API
   moved off the developer machine.
5. **Token stored in `localStorage`** — XSS-readable; acceptable only for
   a throwaway beta, never documented as temporary in the UI flow.

## Frontend architecture

6. **No shared API client** — Fetch logic lived only inside `signup.html`.
7. **No auth gate** — Nothing prevented unauthenticated use of a future
   dashboard because no dashboard existed.
8. **Demo file was a one-off** — `demo.html` duplicated CSS and JS instead
   of sharing modules with the real pages.
9. **No listing card wired to live data** — Sample card was hard-coded HTML.

## Backend / data

10. **No demo seed** — Without a successful NYC ingest, the API returned
    empty lists and the product looked broken.
11. **Ingest script only** — No scheduled job, no one-command local seed.
12. **UUID/Decimal serialization gaps** — Listings could fail JSON encoding
    depending on asyncpg type handling (fixed explicitly in v2).
13. **No `GET /api/listings/{id}`** — Only list + enrich; no single-listing fetch.

## Ops / setup

14. **No Docker Compose** — Local Postgres required manual install and
    schema application.
15. **Supabase mentioned but not operationalized** — README said
    “Neon / Supabase” but gave no concrete steps to apply schema or
    connection strings.
16. **Terraform was LocalStack-only** — Not a usable deploy path.
17. **No versioned health payload** — Harder to confirm which build is live.

## Security / completeness (already partially fixed in v1)

18. Rate limits and CORS were improved late; v2 keeps them and documents them.
19. Email enumeration on signup remains an accepted UX trade-off (documented).
20. No automated tests in either version (called out; still deferred).

## What v2 delivers instead

- Real **dashboard** (`app.html`) with ratio filter, state filter, cards, detail + enrich
- Working **login** and **signup** pages sharing one API client
- **Docker Compose** Postgres with schema auto-applied
- **Demo seed** so the UI has data without waiting on NYC Open Data
- **NYC ingest** still available for real records
- Explicit **Supabase / Neon** setup in README
- Coerced JSON types, single-listing GET, health version
- One zip with all dependencies listed in `requirements.txt`
