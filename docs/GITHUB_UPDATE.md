# Update GitHub repo with v2.1 + SAST/SCA

Repo: https://github.com/alexh30486-ui/tax-liens-site

Do this on **your machine** (or any terminal where you are logged into GitHub).

## Step 0 — Prerequisites

```bash
# GitHub CLI login (once)
gh auth login

# Or use HTTPS + personal access token when git asks for a password
```

Confirm:

```bash
git --version
gh auth status
```

## Step 1 — Clone your existing GitHub repo

```bash
cd ~
# or wherever you keep projects
git clone https://github.com/alexh30486-ui/tax-liens-site.git
cd tax-liens-site
git status
git branch   # should show main (or master)
```

## Step 2 — Bring in the new version (v2.1 zip)

If you have `tax-lien-finder-v2.zip`:

```bash
# From parent of tax-liens-site
cd ..
unzip -o tax-lien-finder-v2.zip

# Copy new tree OVER the clone (keeps .git)
rsync -a --delete \
  --exclude '.git' \
  tax-lien-finder-v2/ \
  tax-liens-site/
```

Or manually:

```bash
cd tax-liens-site
# remove old app files you are replacing, then:
cp -R ../tax-lien-finder-v2/* .
cp -R ../tax-lien-finder-v2/.github .
cp ../tax-lien-finder-v2/.gitignore .
```

**Do not** copy a real `.env` with secrets. Only `.env.example`.

## Step 3 — Verify nothing secret is staged

```bash
cd ~/tax-liens-site   # adjust path
git status
# Must NOT list .env or real keys
grep -R "CHANGE_ME\|sk-\|BEGIN RSA" --include='*.py' --include='*.yml' . || true
```

## Step 4 — Commit and push to GitHub

```bash
git add -A
git status
git commit -m "v2.1: dashboard, Meilisearch, nginx/gunicorn/systemd, SAST+SCA CI"
git push origin main
# if branch is master: git push origin master
```

If GitHub rejects (history diverged):

```bash
git pull origin main --rebase
git push origin main
```

## Step 5 — Turn on GitHub security features (UI)

1. Open https://github.com/alexh30486-ui/tax-liens-site/settings/security_analysis
2. Enable:
   - **Dependency graph**
   - **Dependabot alerts**
   - **Dependabot security updates**
   - **Secret scanning**
   - **Push protection** (blocks commits that contain secrets)
3. Open the repository rulesets page and protect `main` with required pull
   requests, blocked force pushes, and the three required checks listed below.

## Step 6 — Confirm CI ran

1. https://github.com/alexh30486-ui/tax-liens-site/actions
2. Open the **CI / Security / Deploy** workflow
3. Expect:
   - **Secret history scan** = Gitleaks across the complete Git history
   - **SAST, SCA, syntax, and frontend** = Bandit, pip-audit, and validation
   - **API smoke test and DAST** = live FastAPI checks plus OWASP ZAP

## What each CI piece does

| Step in pipeline | Type | Catches |
|------------------|------|---------|
| Bandit | SAST | Risky Python (assert, hardcoded binds, bad crypto usage patterns) |
| pip-audit | SCA | Known vulnerable versions of fastapi, passlib, pyjwt, … |
| OWASP ZAP | DAST | Security issues visible against the running API |
| Dependabot | SCA (ongoing) | Opens PRs when a dependency advisory appears |
| Gitleaks | Secrets | Keys in current files or Git history |

## Local dry-run (optional, before push)

```bash
python3 -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Do not do

- Force-push secrets that were ever committed (rotate those keys instead)
- Commit `.env`
- Disable the workflow to “make the badge green” without fixing findings
