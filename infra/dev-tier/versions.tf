###############################################################################
# infra/dev-tier/versions.tf
#
# Provider pins for the V3-Dev-Tier stack (Sprint 2 § Epic 2.1).
#
# Pinning strategy: tilde-arrow (~>) on minor versions so we get patch bumps
# automatically but never breaking-change minor bumps. Each pin is reviewed
# during the Stage-A → Stage-B graduation per RUNBOOK.md.
#
# OpenTofu is required (>=1.6); we DO NOT support legacy Terraform here. The
# sprint board (§S2.1.1, §S2.1.3 acceptance criteria) names OpenTofu/`tofu`
# explicitly; using HashiCorp Terraform may diverge on provider behaviour
# (e.g. removed_block handling). See infra/dev-tier/README.md for the rationale.
###############################################################################

terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }

    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }

    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.6"
    }

    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.23"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# ── Provider blocks ─────────────────────────────────────────────────────────
#
# Note: provider configurations are kept in this file rather than colocated
# with their resources. Reason: the cross-cutting DoD test
# `tests/infra/test_cross_cutting.py::test_no_secrets_in_provider_blocks`
# walks `provider {}` blocks looking for hardcoded secrets — keeping them in
# one file makes that traversal trivially auditable.

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "neon" {
  api_key = var.neon_api_key
}

# The postgresql provider is used to manage extensions (pgvector) inside the
# Neon database after the Neon project is provisioned. Connection params are
# resolved from the `neon_project` resource outputs (see neon.tf). Keeping
# `superuser = false` lets this work on Neon's restricted role model.
provider "postgresql" {
  host      = local.neon_pg_host
  port      = 5432
  database  = local.neon_pg_database
  username  = local.neon_pg_user
  password  = local.neon_pg_password
  sslmode   = "require"
  superuser = false

  # Neon's pooled endpoint requires this to avoid prepared-statement issues.
  # Pinned to 17 to match the existing project's `pg_version` (we cannot
  # downgrade — `tofu plan` would fail with "version mismatch"). Bump in
  # lockstep when Neon defaults change AND we explicitly upgrade.
  expected_version = "17"
}
