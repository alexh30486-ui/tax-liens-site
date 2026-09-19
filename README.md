# Tax Lien Finder v2.1 — Production-ready revamp

Screen tax liens by **value-to-lien ratio** (Postgres SQL) + **Meilisearch** full-text search + optional Gemini summary.

Stack for real deployment:

| Layer | Choice |
|--------|--------|
| API | FastAPI + **Gunicorn** + **Uvicorn** workers |
| Proxy | **Nginx** (static frontend + `/api` reverse proxy + security headers) |
| Process | **systemd** unit (`tax-lien-api.service`) |
| DB | Postgres (Docker / Supabase / Neon) |
| Search | **Meilisearch** (Docker or systemd) |
| Secrets | **`.env` only** (never in code, nginx, or git) |

## What’s new in 2.1

- Security / observability headers on API + nginx config
- Gunicorn config + systemd service (hardened)
- Nginx site with CSP, frame deny, nosniff, rate-friendly proxy
- Meilisearch index + `/api/search` + dashboard search box
- JWT/Meili secrets rejected if still `CHANGE_ME…`
- `scripts/security_check.sh` smoke test
- `docs/SECURITY.md` checklist

## Local build (Docker Postgres + Meilisearch)

```bash
cd tax-lien-finder-v2

# 1) Data services
export MEILI_MASTER_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
docker compose up -d

# 2) Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python3 -c 'import secrets; print("JWT_SECRET="+secrets.token_hex(32))'
# Paste JWT_SECRET and the same MEILI_MASTER_KEY into .env
# MEILI_URL=http://127.0.0.1:7700

PYTHONPATH=src python scripts/seed_demo.py
PYTHONPATH=src python scripts/reindex_meili.py

# Dev API (or use gunicorn below)
uvicorn app.main:app --reload --port 8000 --app-dir src
```

```bash
# 3) Frontend
cd frontend
python3 -m http.server 8080
# http://localhost:8080 → signup → dashboard → search
```

### Gunicorn (closer to prod)

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=src gunicorn -c ../deploy/gunicorn/gunicorn.conf.py app.main:app
```

### Security smoke test

```bash
chmod +x scripts/security_check.sh
./scripts/security_check.sh http://127.0.0.1:8000
```

## CI/CD

The repository includes local pre-commit protection, GitHub secret/SAST/SCA/DAST
gates, and health-gated blue-green deployment with automatic rollback. See
[`docs/CICD.md`](docs/CICD.md) for setup and required GitHub/server configuration.

## Production: Nginx + systemd

See `deploy/systemd/README.md` and:

- `deploy/nginx/tax-lien-finder.conf`
- `deploy/gunicorn/gunicorn.conf.py`
- `deploy/systemd/tax-lien-api.service`

Point nginx `root` at your frontend copy; proxy `/api/` and `/health` to `127.0.0.1:8000`.

After TLS:

```env
ENABLE_HSTS=true
CORS_ORIGINS=https://your.domain
PUBLIC_ORIGIN=https://your.domain
APP_ENV=production
```

## Supabase / Neon

1. Run `backend/schema.sql` in the SQL editor.
2. Set `DATABASE_URL` in `.env` (pooler URI + `sslmode=require` as required).
3. Seed + reindex as above.
4. Auth remains FastAPI JWT (secrets only in `.env`).

## API

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | Includes Meilisearch status |
| POST | `/api/auth/signup` | 5/min |
| POST | `/api/auth/login` | 10/min |
| GET | `/api/auth/me` | Bearer |
| GET | `/api/listings` | SQL filters |
| GET | `/api/search?q=` | Meilisearch |
| POST | `/api/listings/{id}/enrich` | Gemini, 20/min |

## Secrets rule

Never put keys in HTML, nginx, or git. Only `backend/.env` (and systemd `EnvironmentFile`).
Generate:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # JWT
python3 -c "import secrets; print(secrets.token_hex(16))"  # Meili
```

## Docs

- `docs/SECURITY.md` — headers, auth, HTTPS
- `docs/INADEQUACIES.md` — gaps fixed from v1
- `deploy/systemd/README.md` — install path

## Disclaimer

Not investment advice. Verify county records before bidding.
