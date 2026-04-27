###############################################################################
# infra/dev-tier/backend.tf
#
# Remote state in a GCS bucket. The bucket itself is provisioned out-of-band
# (per the README account-setup checklist):
#
#   gsutil mb -p $PROJECT -l us-central1 gs://$PROJECT-tofu-state
#   gsutil versioning set on gs://$PROJECT-tofu-state
#
# Reasoning:
#   - GCS versioning protects against accidental state corruption.
#   - The bucket lives in the same project Tofu manages, so its IAM is
#     governed by the same `tofu-deployer` service account.
#   - Local state would leak `secret_data` from
#     google_secret_manager_secret_version onto developer laptops; that is
#     why the user picked `tofu_creates_versions` *together with* GCS state
#     in Sprint 2 clarifications.
#
# `bucket` is intentionally a placeholder that MUST be overridden via
# `tofu init -backend-config="bucket=<actual>" -backend-config="prefix=…"`.
# Tests do not exercise the backend; they run with `tofu init -backend=false`.
###############################################################################

terraform {
  backend "gcs" {
    # bucket = "agent-prod-gcp-dev-tofu-state"   ← injected via -backend-config
    prefix = "infra/dev-tier"
  }
}
