terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    fly = {
      source  = "fly-apps/fly"
      version = "~> 0.0.23"
    }
  }
}

# ------------------------------------------------------------
# AWS provider — points at LocalStack, not real AWS.
# This lets you provision/test S3 (raw data backups) for $0
# and with zero risk of a surprise AWS bill while iterating.
# Switch to real AWS only when you're ready to pay for it —
# see variables.tf: use_localstack.
# ------------------------------------------------------------
provider "aws" {
  region                      = "us-east-1"
  access_key                  = var.use_localstack ? "test" : var.aws_access_key
  secret_key                  = var.use_localstack ? "test" : var.aws_secret_key
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      s3 = "http://localhost:4566"
    }
  }
}

# ------------------------------------------------------------
# Fly.io provider — this one is always real. Fly's free
# allowance covers a small Postgres + app instance, which is
# all this project needs at this stage.
# ------------------------------------------------------------
provider "fly" {
  useinternaltunnel   = true
  internaltunnelorg   = var.fly_org
}
