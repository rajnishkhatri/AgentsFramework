###############################################################################
# infra/gcp/versions.tf
#
# Provider pins for the GCP Tier A stack (Recipe 1).
#
# This stack is Google-only — no Cloudflare, Neon, or PostgreSQL providers
# (those belong to infra/dev-tier/, which remains unchanged). The google
# provider ~>6.0 is the same pin used in infra/dev-tier/ for consistency.
#
# OpenTofu >=1.6 is required. Do NOT use HashiCorp Terraform — versions.tf
# uses `required_version` scoped to OpenTofu semantics and future recipes
# may rely on OpenTofu-specific features (e.g. `removed {}` blocks).
#
# Provider block placement: all provider {} blocks live in this file so
# `tests/infra/gcp/test_cross_cutting.py::test_no_hardcoded_credentials_in_providers`
# can audit them in one place without chasing multiple files.
###############################################################################

terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# ── Provider block ───────────────────────────────────────────────────────────
#
# Credentials are sourced from the environment (GOOGLE_APPLICATION_CREDENTIALS
# or Application Default Credentials via `gcloud auth application-default
# login`). Never hardcode a credential here — the cross-cutting DoD test
# enforces this automatically.

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}
