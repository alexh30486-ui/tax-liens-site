# Security checklist — Tax Lien Finder

## Secrets (env only)

| Variable | Purpose | Never |
|----------|---------|--------|
| `JWT_SECRET` | Signs access tokens | Commit, logs, client JS |
| `MEILI_MASTER_KEY` | Meilisearch admin | Commit, browser |
| `DATABASE_URL` | Postgres credentials | Commit, client |
| `GEMINI_API_KEY` | Optional AI | Commit, client |

- `.env` is gitignored.
- Systemd loads secrets via `EnvironmentFile=.../backend/.env`.
- Gunicorn/nginx configs contain **no** secrets.
- Startup **fails** if `JWT_SECRET` is missing or still `CHANGE_ME…`.

## Headers

**API** (`SecurityHeadersMiddleware`):

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` (camera/mic/geo/payment off)
- Strict CSP for JSON API (`default-src 'none'`)
- `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`
- `Strict-Transport-Security` only when `ENABLE_HSTS=true` (use behind HTTPS nginx)

**Nginx** (HTML + proxy): same baseline + frontend CSP allowing Google Fonts and API `connect-src`.

## Auth & abuse

- Passwords: bcrypt via passlib
- JWT: HS256 only (alg confusion blocked)
- Rate limits: signup 5/min, login 10/min, enrich 20/min (per IP)
- CORS: explicit origin list (no `*` in production)
- Login errors do not reveal whether an email exists

## Common mistakes fixed

1. Placeholder secrets rejected at boot
2. CORS methods limited to GET/POST/OPTIONS
3. Meilisearch key required for search (503 if down)
4. Server version not leaked via nginx `server_tokens off`
5. Body size limited (`client_max_body_size 1m`)

## Quick header test

```bash
curl -sI http://127.0.0.1:8000/health | grep -iE 'x-content|x-frame|referrer|permissions|strict-transport|content-security'
```

## HTTPS

Terminate TLS at nginx (or a load balancer). Then:

```env
ENABLE_HSTS=true
CORS_ORIGINS=https://your.domain
PUBLIC_ORIGIN=https://your.domain
```

Uncomment the HSTS `add_header` and HTTP→HTTPS redirect in `deploy/nginx/tax-lien-finder.conf`.
