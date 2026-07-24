###############################################################################
# infra/gcp/outputs.tf
#
# Outputs exposed after `tofu apply`. Downstream tooling (CI scripts, Recipe 3
# Docker push, Recipe 4 Cloud Run deploy, RUNBOOK smoke checks) reads these via
# `tofu output -raw <name>`.
#
# Cross-cutting DoD: NO secret value escapes via outputs. Every sensitive
# var.tf entry has `sensitive = true`; we additionally never emit `secret_data`
# here. The cross-cutting test
# `tests/infra/gcp/test_cross_cutting.py::test_no_secret_outputs` enforces
# this mechanically.
###############################################################################

# ── Artifact Registry ────────────────────────────────────────────────────────

output "artifact_registry_url" {
  description = "Docker push/pull base URL for the backend repository. Used by `docker push` and Cloud Run image references in Recipe 3/4."
  value       = "${var.artifact_registry_location}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.backend.repository_id}"
}

output "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID. Used by Recipe 4 Tofu to construct the full image URI."
  value       = google_artifact_registry_repository.backend.repository_id
}

# ── Service accounts ─────────────────────────────────────────────────────────

output "backend_runtime_service_account_email" {
  description = "Email of the backend runtime SA. Used to grant additional IAM (e.g. Cloud SQL client in Recipe 2) without modifying this stack."
  value       = google_service_account.backend_runtime.email
}

# ── Secret Manager ───────────────────────────────────────────────────────────
#
# Outputs the *secret_id* (name), not the value. Operators who need the value
# pull it via:
#   gcloud secrets versions access latest --secret=<secret_id>

output "secret_ids" {
  description = "Map of logical-name → Secret Manager secret_id. Used by Recipe 4 Tofu to wire Cloud Run value_source.secret_key_ref blocks."
  value = {
    workos_api_key         = google_secret_manager_secret.workos_api_key.secret_id
    openai_api_key         = google_secret_manager_secret.openai_api_key.secret_id
    anthropic_api_key      = google_secret_manager_secret.anthropic_api_key.secret_id
    deepseek_api_key       = google_secret_manager_secret.deepseek_api_key.secret_id
    langfuse_public_key    = google_secret_manager_secret.langfuse_public_key.secret_id
    langfuse_secret_key    = google_secret_manager_secret.langfuse_secret_key.secret_id
    mem0_api_key           = google_secret_manager_secret.mem0_api_key.secret_id
    database_url           = google_secret_manager_secret.database_url.secret_id
    agent_facts_secret     = google_secret_manager_secret.agent_facts_secret.secret_id
    workos_cookie_password = google_secret_manager_secret.workos_cookie_password.secret_id
  }
}

# ── Project info ─────────────────────────────────────────────────────────────

output "gcp_project_id" {
  description = "GCP project ID, for reference by downstream recipes and scripts."
  value       = var.gcp_project_id
}

output "gcp_region" {
  description = "Primary GCP region, for reference by downstream recipes."
  value       = var.gcp_region
}

# ── Cloud SQL (Recipe 2) ─────────────────────────────────────────────────────

output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name. Used by Recipe 4 to wire the Cloud Run cloud_sql_instances annotation."
  value       = google_sql_database_instance.main.name
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name (PROJECT:REGION:INSTANCE). Used by the Cloud Run built-in connector and local Cloud SQL Auth Proxy."
  value       = google_sql_database_instance.main.connection_name
}

output "cloud_sql_ip" {
  description = "Cloud SQL instance public IP address. Used by local Cloud SQL Auth Proxy for development."
  value       = google_sql_database_instance.main.public_ip_address
}

# ── GCS buckets (Recipe 2) ───────────────────────────────────────────────────

output "agent_facts_bucket" {
  description = "GCS bucket name for agent-facts JSON documents. Used by services/governance/agent_facts_gcs_registry.py via GCS_FACTS_BUCKET env var."
  value       = google_storage_bucket.agent_facts.name
}

output "trust_traces_bucket" {
  description = "GCS bucket name for trust-trace JSONL. Used by services/trace_sinks/gcs_sink.py via GCS_TRACES_BUCKET env var."
  value       = google_storage_bucket.trust_traces.name
}

# ── Cloud Run backend (Recipe 4) ─────────────────────────────────────────────

output "backend_url" {
  description = "HTTPS URL of the combined backend Cloud Run service. Used by Recipe 5 MIDDLEWARE_URL and smoke tests."
  value       = google_cloud_run_v2_service.backend_combined.uri
}

output "backend_service_name" {
  description = "Cloud Run service name for the combined backend (agent-backend-combined)."
  value       = google_cloud_run_v2_service.backend_combined.name
}

# ── Cloud Run frontend (Recipe 5) ────────────────────────────────────────────

output "frontend_url" {
  description = "HTTPS URL of the Next.js frontend Cloud Run service. Add to WorkOS redirect allowlist (HUMAN_SETUP.md §6)."
  value       = google_cloud_run_v2_service.frontend.uri
}

output "frontend_service_name" {
  description = "Cloud Run service name for the frontend (agent-frontend)."
  value       = google_cloud_run_v2_service.frontend.name
}

output "frontend_workos_redirect_uri" {
  description = "WorkOS OAuth callback URL for the deployed frontend. Copy into WorkOS Dashboard → Authentication → Redirects."
  value       = "${google_cloud_run_v2_service.frontend.uri}/api/auth/callback"
}

output "enable_durable_engine" {
  description = "Build-time durable-engine intent (T R.5). True only takes effect after rebuilding frontend_image with --build-arg NEXT_PUBLIC_FF_DURABLE_ENGINE=1; runtime env cannot flip an inlined NEXT_PUBLIC_* bundle."
  value       = var.enable_durable_engine
}

output "frontend_runtime_service_account_email" {
  description = "Email of the frontend runtime SA. Used to audit least-privilege secretAccessor grants."
  value       = google_service_account.frontend_runtime.email
}

# ── Meta ring (Recipe 6, optional) ───────────────────────────────────────────

output "meta_ring_enabled" {
  description = "Whether Recipe 6 meta ring resources were provisioned (enable_meta_ring in terraform.tfvars)."
  value       = var.enable_meta_ring
}

output "meta_job_name" {
  description = "Cloud Run Job name for the meta eval pipeline. Empty when enable_meta_ring=false."
  value       = var.enable_meta_ring ? google_cloud_run_v2_job.meta_eval[0].name : ""
}

output "meta_golden_set_uri" {
  description = "GCS URI to the golden-set JSONL the meta job reads. Empty when enable_meta_ring=false."
  value       = var.enable_meta_ring ? local.meta_golden_set_uri : ""
}

output "meta_report_uri" {
  description = "GCS URI where the meta job writes the latest eval report. Empty when enable_meta_ring=false."
  value       = var.enable_meta_ring ? local.meta_report_uri : ""
}

# ── Observability (Recipe 7) ─────────────────────────────────────────────────

output "monitoring_dashboard_name" {
  description = "Cloud Monitoring dashboard resource ID. Open in Console → Monitoring → Dashboards."
  value       = google_monitoring_dashboard.agent_tier_a.id
}

output "billing_budget_enabled" {
  description = "Whether a billing budget alert was provisioned (billing_account_id set in terraform.tfvars)."
  value       = var.billing_account_id != ""
}
