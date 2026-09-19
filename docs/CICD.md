# CI/CD and production deployment

This repository uses three gates. A release cannot reach production unless the
secret scan, code/dependency checks, and live API scan all pass.

## 1. Install local commit protection

From the repository root on macOS:

```bash
brew install gitleaks python@3.12
python3 -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

The hooks reject private keys, likely credentials, malformed YAML, large files,
high-confidence Python security findings, and common formatting damage. Gitleaks
scans staged changes for API keys and tokens.

Never bypass a secret finding. Rotate a real leaked key immediately; removing it
in a later commit does not remove it from Git history.

## 2. GitHub Actions gates

`.github/workflows/security.yml` runs on every pull request and every push to
`main`:

- **Secret history scan:** Gitleaks scans the complete Git history.
- **SAST:** Bandit scans `backend/src/app` and Python byte-compilation catches
  syntax errors.
- **SCA:** `pip-audit --strict` blocks known vulnerable Python dependencies.
- **Frontend validation:** validates local links, duplicate IDs, CSS braces, and
  inline JavaScript. The frontend is static HTML/CSS/JS, so an npm audit would
  provide no coverage until a `package.json` actually exists.
- **DAST:** starts Postgres, Meilisearch, and FastAPI, runs the security-header
  smoke test, then runs the OWASP ZAP baseline against the live API.

For an organization-owned repository, add `GITLEAKS_LICENSE` as a repository
secret. Personal repositories do not require it.

In GitHub, create a branch ruleset for `main` and require these checks:

- `Secret history scan`
- `SAST, SCA, syntax, and frontend`
- `API smoke test and DAST`

Also require pull requests, block force pushes, and require the branch to be up
to date before merging.

## 3. One-time production server setup

The production layout is release-based:

```text
/opt/tax-lien-finder/
├── current -> releases/<active-release>
├── releases/
├── repo/                 # deployment checkout
└── shared/backend.env    # production secrets; never committed
```

Install the service and nginx files:

```bash
sudo useradd --system --home /opt/tax-lien-finder --shell /usr/sbin/nologin tlf
sudo install -d -m 0755 /opt/tax-lien-finder/{releases,shared}
sudo install -d -m 0755 /etc/nginx/snippets
sudo cp deploy/systemd/tax-lien-api@.service /etc/systemd/system/
sudo cp deploy/nginx/tlf-active-upstream.conf /etc/nginx/snippets/
sudo cp deploy/nginx/tax-lien-finder.conf /etc/nginx/sites-available/
sudo ln -sfn /etc/nginx/sites-available/tax-lien-finder.conf /etc/nginx/sites-enabled/tax-lien-finder.conf
sudo systemctl daemon-reload
sudo nginx -t
sudo systemctl reload nginx
```

Clone the deployment repository into `/opt/tax-lien-finder/repo`. Create
`/opt/tax-lien-finder/shared/backend.env`, owned by `root:tlf` with mode `0640`,
and provide production values for `DATABASE_URL`, `JWT_SECRET`, Meilisearch,
CORS, and other backend settings.

The SSH deployment user needs read/write access to the repository and releases,
plus narrowly scoped passwordless sudo access for the service slots, nginx
reload/config test, runtime environment files, the `current` symlink, and the
nginx upstream snippet. Do not grant unrestricted passwordless sudo.

## 4. Enable automated production deployment

Create a protected GitHub environment named `production`. Add:

- Repository variable: `PRODUCTION_DEPLOY_ENABLED=true`
- Environment secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, and
  `DEPLOY_KNOWN_HOSTS`

`DEPLOY_KNOWN_HOSTS` must contain the pinned host key collected out of band. Do
not use `StrictHostKeyChecking=no`.

The deploy job sends only the commit SHA. On the server, `scripts/deploy.sh`:

1. extracts that exact commit into a new immutable release;
2. creates an isolated virtual environment and validates Python syntax;
3. starts the inactive blue/green Gunicorn slot;
4. health-checks the inactive slot directly;
5. atomically switches the frontend symlink and nginx upstream;
6. gracefully reloads nginx and checks the public `/health` route; and
7. restores the former release and upstream automatically if the check fails.

Keep at least two releases so rollback remains available. Remove older release
directories only after confirming they are not the `current` target and are not
used by either running service slot.
