###############################################################################
# infra/gcp/meta.tf
#
# GCP Tier A meta ring (Recipe 6, optional): Cloud Scheduler triggers a
# Cloud Run Job that runs `python -m meta.run_eval` against a golden-set
# JSONL stored in the trust-traces GCS bucket.
#
# Resources (created only when var.enable_meta_ring = true):
#   * google_service_account.meta_runtime — read traces, write reports
#   * google_service_account.meta_scheduler — invokes the Cloud Run Job
#   * google_cloud_run_v2_job.meta_eval — nightly eval pipeline
#   * google_cloud_scheduler_job.meta_eval — cron trigger (default 06:00 UTC)
#   * google_storage_bucket_iam_member — meta SA read/write on trust-traces
#   * google_secret_manager_secret_iam_member — OPENAI_API_KEY for judge only
#
# Default: disabled for Tier A (~$0/mo). Enable with enable_meta_ring = true
# in terraform.tfvars once a golden set is uploaded to GCS.
#
# Depends on: foundations.tf, secret-manager.tf, data.tf, cloud-run-backend.tf
###############################################################################

locals {
  meta_enabled = var.enable_meta_ring

  meta_golden_set_uri = var.meta_golden_set_gcs_uri != "" ? var.meta_golden_set_gcs_uri : (
    "gs://${google_storage_bucket.trust_traces.name}/golden/eval.jsonl"
  )

  meta_report_uri = "gs://${google_storage_bucket.trust_traces.name}/${var.meta_report_output_prefix}/latest.json"
}

# ── Meta runtime service account ─────────────────────────────────────────────

resource "google_service_account" "meta_runtime" {
  count = local.meta_enabled ? 1 : 0

  project      = var.gcp_project_id
  account_id   = "agent-meta-runtime"
  display_name = "Agent Meta Ring (Cloud Run Job runtime)"
  description  = "Runtime identity for the agent-meta-eval Cloud Run Job. Read-only on trust-traces plus report writes; OPENAI_API_KEY for judge only."

  depends_on = [google_project_service.required]
}

resource "google_artifact_registry_repository_iam_member" "meta_runtime_ar_reader" {
  count = local.meta_enabled ? 1 : 0

  project    = var.gcp_project_id
  location   = google_artifact_registry_repository.backend.location
  repository = google_artifact_registry_repository.backend.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.meta_runtime[0].email}"
}

resource "google_project_iam_member" "meta_runtime_log_writer" {
  count = local.meta_enabled ? 1 : 0

  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.meta_runtime[0].email}"
}

# ── Scheduler invoker service account ────────────────────────────────────────

resource "google_service_account" "meta_scheduler" {
  count = local.meta_enabled ? 1 : 0

  project      = var.gcp_project_id
  account_id   = "agent-meta-scheduler"
  display_name = "Agent Meta Ring (Cloud Scheduler invoker)"
  description  = "Invokes the agent-meta-eval Cloud Run Job on the nightly cron schedule."

  depends_on = [google_project_service.required]
}

# ── GCS IAM — read golden set / traces, write eval reports ───────────────────

resource "google_storage_bucket_iam_member" "meta_trust_traces_reader" {
  count = local.meta_enabled ? 1 : 0

  bucket = google_storage_bucket.trust_traces.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.meta_runtime[0].email}"
}

resource "google_storage_bucket_iam_member" "meta_trust_traces_writer" {
  count = local.meta_enabled ? 1 : 0

  bucket = google_storage_bucket.trust_traces.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.meta_runtime[0].email}"
}

# ── Secret Manager — judge LLM key only ──────────────────────────────────────

resource "google_secret_manager_secret_iam_member" "openai_api_key_meta_accessor" {
  count = local.meta_enabled ? 1 : 0

  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.openai_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.meta_runtime[0].email}"
}

# ── Cloud Run Job ────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "meta_eval" {
  count = local.meta_enabled ? 1 : 0

  project  = var.gcp_project_id
  name     = "agent-meta-eval"
  location = var.gcp_region

  template {
    template {
      service_account = google_service_account.meta_runtime[0].email
      timeout         = "${var.meta_job_timeout_seconds}s"

      containers {
        image   = var.backend_image
        command = ["python", "-m", "meta.run_eval"]
        args = [
          "--golden-set", local.meta_golden_set_uri,
          "--output", local.meta_report_uri,
          "--report-id", "nightly-meta-eval",
        ]

        resources {
          limits = {
            cpu    = var.meta_job_cpu
            memory = var.meta_job_memory
          }
        }

        env {
          name  = "GCP_EXECUTION_ENV"
          value = "cloudrun"
        }

        env {
          name  = "GCS_TRACES_BUCKET"
          value = google_storage_bucket.trust_traces.name
        }

        env {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.openai_api_key.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.openai_api_key_meta_accessor,
    google_artifact_registry_repository_iam_member.meta_runtime_ar_reader,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "meta_scheduler_invoker" {
  count = local.meta_enabled ? 1 : 0

  project  = var.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_job.meta_eval[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.meta_scheduler[0].email}"
}

# ── Cloud Scheduler ──────────────────────────────────────────────────────────

resource "google_cloud_scheduler_job" "meta_eval" {
  count = local.meta_enabled ? 1 : 0

  project   = var.gcp_project_id
  name      = "agent-meta-eval-nightly"
  region    = var.gcp_region
  schedule  = var.meta_cron_schedule
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.gcp_region}-run.googleapis.com/v2/projects/${var.gcp_project_id}/locations/${var.gcp_region}/jobs/${google_cloud_run_v2_job.meta_eval[0].name}:run"

    oauth_token {
      service_account_email = google_service_account.meta_scheduler[0].email
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.meta_scheduler_invoker,
    google_project_service.required,
  ]
}
