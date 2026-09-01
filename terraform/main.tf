# ------------------------------------------------------------
# AWS (LocalStack-backed while use_localstack = true)
# ------------------------------------------------------------
# Raw ingestion payload backups — a safety net independent of
# Postgres. If a bad migration ever wipes raw_payload data, this
# is the recovery source. Costs nothing until you flip to real AWS.
resource "aws_s3_bucket" "raw_lien_backups" {
  bucket = "tax-lien-finder-raw-backups"
}

resource "aws_s3_bucket_versioning" "raw_lien_backups" {
  bucket = aws_s3_bucket.raw_lien_backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ------------------------------------------------------------
# Fly.io — the real deploy target
# ------------------------------------------------------------
resource "fly_app" "api" {
  name = var.fly_app_name
  org  = var.fly_org
}

resource "fly_ip" "api_ipv4" {
  app  = fly_app.api.name
  type = "v4"
}

resource "fly_ip" "api_ipv6" {
  app  = fly_app.api.name
  type = "v6"
}

# Note: Fly Postgres clusters are best created via `fly postgres create`
# (the CLI wizard) rather than Terraform today — the provider's Postgres
# resource support is limited. Run that once, then reference the
# resulting DATABASE_URL as a Fly secret:
#   fly secrets set DATABASE_URL="..." --app tax-lien-finder-api
