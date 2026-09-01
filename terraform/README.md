# Infrastructure — Terraform

Two-stage approach, deliberately: mock everything locally first with
zero cost and zero risk, then point the same config at real Fly.io
once the app itself is proven.

## Stage 1 — Mock AWS locally with LocalStack

```bash
# Install LocalStack (free, runs in Docker)
pip install localstack
localstack start -d

# Apply with the AWS side pointed at LocalStack (default: use_localstack = true)
cd terraform
terraform init
terraform apply -var="fly_org=your-org-slug"
```

This provisions the S3 backup bucket against LocalStack — nothing
touches real AWS, nothing can generate a bill. Good for proving the
Terraform config itself is correct before it matters.

## Stage 2 — Real Fly.io (always real, by design)

The `fly` provider block is never mocked — Fly's free tier is the
actual target, so there's no reason to fake it. `terraform apply`
above already creates the real Fly app + IPs. Postgres is created
separately via the CLI (see the note in `main.tf`) since the Fly
Terraform provider's Postgres support isn't reliable yet:

```bash
fly postgres create --name tax-lien-finder-db --region ord
fly secrets set DATABASE_URL="<connection string from above>" --app tax-lien-finder-api
```

## Stage 3 — Real AWS (only when you're ready to pay)

Flip the switch:

```bash
terraform apply -var="use_localstack=false" \
  -var="aws_access_key=..." -var="aws_secret_key=..." \
  -var="fly_org=your-org-slug"
```

Same config, same resources — just pointed at real AWS instead of
LocalStack. Nothing about the Terraform code changes between stages,
which is the point: you test the infrastructure logic for free, then
promote it unchanged.
