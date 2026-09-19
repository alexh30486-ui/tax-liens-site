# Blue-green systemd deployment

Use `tax-lien-api@.service` with `scripts/deploy.sh`. The deploy script writes a
small runtime environment file for the `blue` or `green` instance and starts the
new instance on port 8001 or 8002. Nginx continues sending traffic to the old
instance until the new instance passes `/health`.

See `docs/CICD.md` for installation, GitHub secrets, branch protection, and the
rollback model. The older single-instance `tax-lien-api.service` is retained only
for existing installations; disable it before enabling blue-green deployment:

```bash
sudo systemctl disable --now tax-lien-api.service
```
