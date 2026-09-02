###############################################################################
# infra/gcp/variables.tf
#
# All inputs to the GCP Tier A stack. Follows the same discipline as
# infra/dev-tier/variables.tf:
#
#   * NO default values for secrets (silent pass-through would let an empty
#     string land in Secret Manager and the runtime would silently degrade).
#   * Secrets are tagged `sensitive = true` so they never appear in
#     `tofu plan` output or CI logs.
#   * The cross-cutting test
#     `tests/infra/gcp/test_cross_cutting.py::test_secrets_marked_sensitive`
#     enforces this for every variable whose name matches the secret-suffix
#     allowlist (`_api_key`, `_secret_key`, `_password`, `_url` for db URLs,
#     `_secret` for signing keys).
###############################################################################

# ── GCP project + region ────────────────────────────────────────────────────

variable "gcp_project_id" {
  type        = string
  description = "GCP project ID. Must already exist and have billing enabled (HUMAN_SETUP.md step 1)."
}

variable "gcp_region" {
  type        = string
  description = "Primary GCP region for Cloud Run, Secret Manager, Artifact Registry."
  default     = "us-central1"

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.gcp_region))
    error_message = "gcp_region must look like a GCP region (e.g. us-central1)."
  }
}

# ── Artifact Registry ────────────────────────────────────────────────────────

variable "artifact_registry_location" {
  type        = string
  description = "Location for the Artifact Registry repository. Must be a valid AR location (region or multi-region). Defaults to match gcp_region."
  default     = "us-central1"
}

variable "artifact_registry_repo_id" {
  type        = string
  description = "Repository ID for the backend Docker images."
  default     = "agent-backend"
}

# ── WorkOS public config ─────────────────────────────────────────────────────
#
# `workos_client_id` is a public-facing identifier (not a secret). It goes
# into a plain Cloud Run env var, not Secret Manager. Keeping it here (not
# hardcoded in foundations.tf) lets operators swap environments without
# touching resource code.

variable "workos_client_id" {
  type        = string
  description = "WorkOS client ID (client_…). Public-facing; used as a plain Cloud Run env var for JWT issuer validation."
  default     = ""
}

# ── Secret Manager seed values ───────────────────────────────────────────────
#
# Strategy: `tofu_creates_versions` — Tofu writes both the secret shell and
# its version. Values live in the gitignored `terraform.tfvars` locally or
# in `TF_VAR_*` env vars in CI. State lives in the GCS remote backend
# (encrypted, IAM-restricted) so secrets never touch developer laptops in
# plaintext.

variable "workos_api_key" {
  type        = string
  description = "WorkOS secret API key (sk_test_… / sk_live_…)."
  sensitive   = true
}

variable "openai_api_key" {
  type        = string
  description = "OpenAI API key for LiteLLM."
  sensitive   = true
}

variable "anthropic_api_key" {
  type        = string
  description = "Anthropic API key for LiteLLM."
  sensitive   = true
}

variable "deepseek_api_key" {
  type        = string
  description = "DeepSeek API key for LiteLLM (the deepseek/* profile set)."
  sensitive   = true
}

variable "model_profile_set" {
  type        = string
  description = "Which model registry the backend wires (services/llm_config.py build_model_registry): openai (default, prod-safe byte-identical Auto) | anthropic | deepseek | all (pin-only union for the A/B sweep)."
  default     = "openai"
}

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse Cloud public key (pk-lf-…). Stored in Secret Manager for parity with the secret-key sibling so rotation doesn't require an env-var change on Cloud Run."
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse Cloud secret key (sk-lf-…)."
  sensitive   = true
}

variable "mem0_api_key" {
  type        = string
  description = "Mem0 Cloud API key (m0-…)."
  sensitive   = true
}

variable "database_url" {
  type        = string
  description = <<-EOT
    Cloud SQL connection string for the checkpointer + frontend engine BFF.
    Prefer the plain scheme (Node pg + psycopg both accept it):
      postgresql://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE
    Historical `postgresql+asyncpg://…` values still work: deploy_gcp.sh and
    frontend/lib/adapters/db/node_pg_url.ts strip the +dialect marker for Node.
    Populated in Recipe 2 once the Cloud SQL instance is provisioned.
    Set to a placeholder value for Recipe 1 so the secret shell is created.
  EOT
  sensitive   = true
  default     = "placeholder-set-in-recipe-2"
}

variable "agent_facts_secret" {
  type        = string
  description = "HMAC signing key for AgentFacts trust records (trust/models.py). Min 32 chars. Rotate via `gcloud secrets versions add`."
  sensitive   = true
}

variable "workos_cookie_password" {
  type        = string
  description = "iron-session encryption key for WorkOS AuthKit on the Next.js BFF (>= 32 chars). Frontend-only; injected via Secret Manager in Recipe 5."
  sensitive   = true
}

# ── Cloud SQL (Recipe 2) ─────────────────────────────────────────────────────

variable "cloud_sql_instance_name" {
  type        = string
  description = "Cloud SQL instance name. Must be unique within the project; reuse within 7 days of deletion is forbidden by GCP."
  default     = "agent-db"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.cloud_sql_instance_name))
    error_message = "cloud_sql_instance_name must be lowercase alphanumeric with hyphens (no leading/trailing hyphen)."
  }
}

variable "cloud_sql_tier" {
  type        = string
  description = "Cloud SQL machine tier. Tier A uses db-f1-micro (~$7.67/mo sustained). Tier B upgrades to db-custom-1-3840 or higher."
  default     = "db-f1-micro"
}

variable "cloud_sql_disk_size_gb" {
  type        = number
  description = "Cloud SQL disk size in GB. Tier A minimum is 10."
  default     = 10

  validation {
    condition     = var.cloud_sql_disk_size_gb >= 10
    error_message = "cloud_sql_disk_size_gb must be >= 10 (Cloud SQL minimum)."
  }
}

variable "cloud_sql_database_name" {
  type        = string
  description = "Name of the application database within the Cloud SQL instance."
  default     = "agent"
}

variable "cloud_sql_user" {
  type        = string
  description = "Database user for the backend runtime."
  default     = "agent_runtime"
}

variable "cloud_sql_password" {
  type        = string
  description = "Password for the Cloud SQL database user. Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
  sensitive   = true
}

# ── Cloud Run backend (Recipe 4) ─────────────────────────────────────────────

variable "backend_image" {
  type        = string
  description = "Container image URI for the combined backend Cloud Run service. Push to Artifact Registry before apply (Recipe 4 agent steps)."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
  # Bootstrap placeholder — overridden after `docker push` to Artifact Registry.
  # First apply with the placeholder will fail /healthz probes; that is intentional
  # and forces pushing the real image from Recipe 3 before promoting traffic.
}

variable "backend_min_instances" {
  type        = number
  description = "Cloud Run min instance count. Tier A requires 0 (scale-to-zero)."
  default     = 0

  validation {
    condition     = var.backend_min_instances == 0
    error_message = "Tier A cost constraint: backend_min_instances must be 0 (scale-to-zero)."
  }
}

variable "backend_max_instances" {
  type        = number
  description = "Cloud Run max instance count (cost cap for beta traffic)."
  default     = 10
}

variable "backend_cpu" {
  type        = string
  description = "Cloud Run vCPU allocation for the combined backend."
  default     = "1000m"

  validation {
    condition     = var.backend_cpu == "1000m" || var.backend_cpu == "1"
    error_message = "Tier A backend requires 1 vCPU (`1000m` or `1`)."
  }
}

variable "backend_memory" {
  type        = string
  description = "Cloud Run memory allocation for the combined backend."
  default     = "2Gi"

  validation {
    condition     = var.backend_memory == "2Gi" || var.backend_memory == "2048Mi"
    error_message = "Tier A backend requires 2Gi memory."
  }
}

variable "backend_request_timeout_seconds" {
  type        = number
  description = "Per-request timeout in seconds. Must be 3600 for SSE + long ReAct runs."
  default     = 3600

  validation {
    condition     = var.backend_request_timeout_seconds == 3600
    error_message = "Tier A SSE constraint: backend_request_timeout_seconds must be 3600."
  }
}

# ── Cloud Run frontend (Recipe 5) ────────────────────────────────────────────

variable "frontend_image" {
  type        = string
  description = "Container image URI for the Next.js frontend Cloud Run service. Push to Artifact Registry before apply (Recipe 5 agent steps)."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
  # Bootstrap placeholder — overridden after `docker push` to Artifact Registry.
}

variable "frontend_min_instances" {
  type        = number
  description = "Cloud Run min instance count for the frontend (exam route / BFF). R5 requires ≥ 1 so beginSection is not a scale-to-zero cold start."
  default     = 1

  validation {
    condition     = var.frontend_min_instances >= 1
    error_message = "R5 (exam-module): frontend_min_instances must be ≥ 1 (warm exam route)."
  }
}

variable "frontend_max_instances" {
  type        = number
  description = "Cloud Run max instance count for the frontend (cost cap for beta traffic)."
  default     = 10
}

variable "frontend_cpu" {
  type        = string
  description = "Cloud Run vCPU allocation for the Next.js frontend."
  default     = "1000m"

  validation {
    condition     = var.frontend_cpu == "1000m" || var.frontend_cpu == "1"
    error_message = "Tier A frontend requires 1 vCPU (`1000m` or `1`)."
  }
}

variable "frontend_memory" {
  type        = string
  description = "Cloud Run memory allocation for the Next.js frontend."
  default     = "512Mi"

  validation {
    condition     = var.frontend_memory == "512Mi"
    error_message = "Tier A frontend requires 512Mi memory."
  }
}

variable "frontend_request_timeout_seconds" {
  type        = number
  description = "Per-request timeout in seconds for the frontend BFF. Must be 3600 so SSE proxy routes can stream long agent runs."
  default     = 3600

  validation {
    condition     = var.frontend_request_timeout_seconds == 3600
    error_message = "Tier A SSE constraint: frontend_request_timeout_seconds must be 3600."
  }
}

variable "frontend_workos_redirect_uri" {
  type        = string
  description = "WorkOS OAuth callback URL for NEXT_PUBLIC_WORKOS_REDIRECT_URI. Set before apply using the project-scoped *.a.run.app hash from any Cloud Run URL in this project (replace the service segment with agent-frontend). After apply, verify with tofu output -raw frontend_workos_redirect_uri."
  default     = ""
}

variable "enable_durable_engine" {
  type        = bool
  description = "Coach-v3 durable engine (FR-A4/§6). Build-time intent for NEXT_PUBLIC_FF_DURABLE_ENGINE — deploy_gcp.sh maps this into a Docker --build-arg when building Dockerfile.frontend. Default false (shadow→canary / InMemoryEngineDb). Flipping true requires rebuilding + pinning a new frontend_image digest; Cloud Run runtime env cannot change an already-inlined NEXT_PUBLIC_* bundle."
  default     = false
}

# ── Meta ring (Recipe 6, optional) ───────────────────────────────────────────

variable "enable_meta_ring" {
  type        = bool
  description = "Recipe 6 (optional): enable Cloud Scheduler + Cloud Run Job for nightly meta/run_eval.py. Default false for Tier A cost."
  default     = false
}

variable "meta_cron_schedule" {
  type        = string
  description = "Cron schedule (UTC) for the meta eval Cloud Run Job. Default: 06:00 daily."
  default     = "0 6 * * *"
}

variable "meta_golden_set_gcs_uri" {
  type        = string
  description = "GCS URI to the golden-set JSONL for meta/run_eval.py. Defaults to gs://<trust-traces-bucket>/golden/eval.jsonl when empty."
  default     = ""
}

variable "meta_report_output_prefix" {
  type        = string
  description = "Object prefix inside the trust-traces bucket for eval report output."
  default     = "reports/meta-eval"
}

variable "meta_job_timeout_seconds" {
  type        = number
  description = "Cloud Run Job task timeout in seconds for the meta eval pipeline."
  default     = 3600
}

variable "meta_job_cpu" {
  type        = string
  description = "Cloud Run Job vCPU allocation for meta/run_eval.py."
  default     = "1000m"
}

variable "meta_job_memory" {
  type        = string
  description = "Cloud Run Job memory allocation for meta/run_eval.py."
  default     = "2Gi"
}

# ── Observability (Recipe 7) ─────────────────────────────────────────────────

variable "billing_account_id" {
  type        = string
  description = "GCP billing account ID (XXXXXX-XXXXXX-XXXXXX). Required for Recipe 7 budget alerts. Find via: gcloud billing accounts list"
  default     = ""
}

variable "monthly_budget_usd" {
  type        = number
  description = "Tier A billing budget alert threshold in USD."
  default     = 50

  validation {
    condition     = var.monthly_budget_usd >= 10 && var.monthly_budget_usd <= 1000
    error_message = "monthly_budget_usd must be between 10 and 1000 for Tier A dev."
  }
}

variable "alert_notification_email" {
  type        = string
  description = "Email address for Cloud Monitoring alert notifications. Empty skips the notification channel (alerts still appear in Cloud Console)."
  default     = ""
}

variable "cloud_run_5xx_rate_threshold" {
  type        = number
  description = "Alert when backend 5xx rate exceeds this ratio (0.05 = 5%) over 5 minutes."
  default     = 0.05
}

variable "cloud_run_latency_p95_ms_threshold" {
  type        = number
  description = "Alert when backend p95 request latency exceeds this value in milliseconds."
  default     = 5000
}

variable "cloud_sql_connections_threshold" {
  type        = number
  description = "Alert when Cloud SQL active connections exceed this count."
  default     = 50
}
