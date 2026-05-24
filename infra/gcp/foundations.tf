###############################################################################
# infra/gcp/foundations.tf
#
# GCP Tier A foundations (Recipe 1): required project APIs, Artifact Registry,
# and the runtime service account that Cloud Run containers will use.
#
# Resources:
#   * google_project_service — enables 9 APIs needed for Tier A
#   * google_artifact_registry_repository — Docker repo for backend images
#   * google_service_account.backend_runtime — least-privilege identity for
#     Cloud Run containers (secretAccessor + AR reader + log writer)
#   * google_artifact_registry_repository_iam_member — AR reader for runtime SA
#   * google_project_iam_member (logging + monitoring) — structured log writer
#     and metric writer for Cloud Run
#
# NOT provisioned here (Tofu chicken-and-egg):
#   * The tofu-deployer SA — created once by the human operator per
#     docs/recipes/gcp/HUMAN_SETUP.md §2.
#   * The GCS remote-state bucket — created once per HUMAN_SETUP.md §1.
#   * Cloud SQL, GCS data buckets — Recipe 2 (data.tf).
#   * Cloud Run services — Recipe 4/5.
###############################################################################

# ── Required APIs ────────────────────────────────────────────────────────────
#
# `disable_on_destroy = false` prevents Tofu destroy from turning off APIs
# that may be shared with other resources outside this stack (e.g. Cloud
# Console UI, other projects in the billing account). Disabling APIs is a
# highly disruptive, non-reversible-at-speed action.

locals {
  required_apis = toset([
    "cloudresourcemanager.googleapis.com", # required for Tofu to manage project services
    "iam.googleapis.com",                  # service accounts
    "artifactregistry.googleapis.com",     # Docker image registry
    "run.googleapis.com",                  # Cloud Run v2
    "sqladmin.googleapis.com",             # Cloud SQL (Recipe 2)
    "secretmanager.googleapis.com",        # Secret Manager
    "storage.googleapis.com",              # GCS (agent-facts + trust-traces buckets)
    "monitoring.googleapis.com",           # Cloud Monitoring (Recipe 7)
    "cloudbilling.googleapis.com",         # billing budget alerts (Recipe 7)
    "cloudscheduler.googleapis.com",       # Cloud Scheduler (Recipe 6 meta ring)
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_apis

  project            = var.gcp_project_id
  service            = each.key
  disable_on_destroy = false
}

# ── Artifact Registry ────────────────────────────────────────────────────────
#
# Single Docker repository for the combined backend image. The `us-central1`
# region keeps push/pull latency low for Cloud Run in the same region and
# avoids cross-region egress charges.

resource "google_artifact_registry_repository" "backend" {
  project       = var.gcp_project_id
  location      = var.artifact_registry_location
  repository_id = var.artifact_registry_repo_id
  format        = "DOCKER"
  description   = "AgentsFramework combined backend images (Cloud Run Tier A)."

  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
  }

  depends_on = [google_project_service.required]
}

# ── Runtime service account ──────────────────────────────────────────────────
#
# Cloud Run containers run as this SA. All IAM bindings in secret-manager.tf
# target this identity so no other principal can read runtime secrets.
#
# Naming convention: `agent-backend-runtime` identifies the product ring
# (backend) and role (runtime), matching the `agent-middleware-runtime` pattern
# from infra/dev-tier/cloud-run.tf for cross-stack legibility.

resource "google_service_account" "backend_runtime" {
  project      = var.gcp_project_id
  account_id   = "agent-backend-runtime"
  display_name = "Agent Backend (Cloud Run runtime)"
  description  = "Runtime identity for Cloud Run containers. Granted secretAccessor on individual secrets (secret-manager.tf), AR reader (foundations.tf), and log/metric writer."

  depends_on = [google_project_service.required]
}

# ── Artifact Registry — runtime SA can pull images ──────────────────────────

resource "google_artifact_registry_repository_iam_member" "backend_runtime_ar_reader" {
  project    = var.gcp_project_id
  location   = google_artifact_registry_repository.backend.location
  repository = google_artifact_registry_repository.backend.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.backend_runtime.email}"
}

# ── Cloud Logging — runtime SA can write structured logs ─────────────────────
#
# `roles/logging.logWriter` is the minimum role for structured log emission
# from Cloud Run. Without it, logs appear in the default Compute Engine log
# sink but without the structured JSON payload the observability stack expects.

resource "google_project_iam_member" "backend_runtime_log_writer" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.backend_runtime.email}"
}

# ── Cloud Monitoring — runtime SA can write custom metrics ───────────────────

resource "google_project_iam_member" "backend_runtime_metric_writer" {
  project = var.gcp_project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.backend_runtime.email}"
}

# ── Frontend runtime service account (Recipe 5) ─────────────────────────────
#
# Cloud Run containers for the Next.js BFF run as this SA. Granted
# secretAccessor on WorkOS secrets only (secret-manager.tf) — never backend
# credentials (DATABASE_URL, LLM keys, agent-facts signing key).

resource "google_service_account" "frontend_runtime" {
  project      = var.gcp_project_id
  account_id   = "agent-frontend-runtime"
  display_name = "Agent Frontend (Cloud Run runtime)"
  description  = "Runtime identity for the agent-frontend Cloud Run service. Granted secretAccessor on WorkOS BFF secrets only."

  depends_on = [google_project_service.required]
}

resource "google_artifact_registry_repository_iam_member" "frontend_runtime_ar_reader" {
  project    = var.gcp_project_id
  location   = google_artifact_registry_repository.backend.location
  repository = google_artifact_registry_repository.backend.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.frontend_runtime.email}"
}

resource "google_project_iam_member" "frontend_runtime_log_writer" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.frontend_runtime.email}"
}
