# Systemd deployment

Assumes app installed at `/opt/tax-lien-finder` and a system user `tlf`.

```bash
# Create user + dirs
sudo useradd --system --home /opt/tax-lien-finder --shell /usr/sbin/nologin tlf
sudo mkdir -p /opt/tax-lien-finder /var/www/tax-lien-finder /var/lib/meilisearch/data
sudo cp -a . /opt/tax-lien-finder/
sudo cp -a frontend /var/www/tax-lien-finder/
sudo chown -R tlf:tlf /opt/tax-lien-finder /var/lib/meilisearch

# Python venv + deps
cd /opt/tax-lien-finder/backend
sudo -u tlf python3 -m venv .venv
sudo -u tlf .venv/bin/pip install -r requirements.txt
sudo -u tlf cp .env.example .env
# Edit .env: JWT_SECRET, MEILI_MASTER_KEY, DATABASE_URL, CORS_ORIGINS

# Units
sudo cp deploy/systemd/tax-lien-api.service /etc/systemd/system/
# Optional if not using Docker for Meili:
# sudo cp deploy/systemd/meilisearch.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now tax-lien-api
sudo systemctl status tax-lien-api

# Nginx
sudo cp deploy/nginx/tax-lien-finder.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/tax-lien-finder.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

After seed/ingest:

```bash
cd /opt/tax-lien-finder/backend
sudo -u tlf env $(grep -v '^#' .env | xargs) PYTHONPATH=src .venv/bin/python scripts/reindex_meili.py
```
