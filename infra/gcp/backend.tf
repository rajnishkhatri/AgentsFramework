###############################################################################
# infra/gcp/backend.tf
#
# GCS remote state for the GCP Tier A stack. The bucket is provisioned
# out-of-band (human one-time step, documented in docs/recipes/gcp/HUMAN_SETUP.md):
#
#   gsutil mb -p $PROJECT -l us-central1 gs://${PROJECT}-tofu-state
#   gsutil versioning set on gs://${PROJECT}-tofu-state
#
# `bucket` is left as a placeholder; callers MUST inject it:
#
#   tofu init -backend-config="bucket=${PROJECT}-tofu-state"
#
# Prefix `infra/gcp` keeps Tier A state isolated from the dev-tier prefix
# (`infra/dev-tier`) so both stacks can coexist in the same GCS bucket.
#
# Why GCS remote state matters: Tofu's `tofu_creates_versions` strategy
# (per Sprint 2 clarifications) stores secret_data in state. GCS versioning
# + IAM restriction ensures secret values never land on developer laptops in
# plaintext.
###############################################################################

terraform {
  backend "gcs" {
    # bucket = "${PROJECT}-tofu-state"  ← injected via -backend-config at init
    prefix = "infra/gcp"
  }
}
