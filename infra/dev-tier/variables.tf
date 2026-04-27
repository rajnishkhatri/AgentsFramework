###############################################################################
# infra/dev-tier/variables.tf
#
# All inputs to the V3-Dev-Tier stack. NO default values are provided for
# secrets (those would silently fall through to apply); plain config gets
# sensible defaults that match the sprint-board acceptance criteria verbatim.
#
# Cross-cutting DoD (FE-AP-18, FD3.SEC1): secrets are tagged `sensitive = true`
# so they never appear in `tofu plan` output or CI logs. The
# `tests/infra/test_cross_cutting.py::test_secrets_marked_sensitive` test
# enforces this for every variable whose name matches the secret-suffix
# allowlist (`_api_key`, `_secret_key`, `_password`, `_url` for db URLs).
###############################################################################

# ── GCP ─────────────────────────────────────────────────────────────────────

variable "gcp_project_id" {
  type        = string
  description = "GCP project ID (per Sprint 0 §S0.1.2: agent-prod-gcp-dev or your suffix)."
}

variable "gcp_region" {
  type        = string
  description = "GCP region for Cloud Run + Secret Manager."
  default     = "us-central1"

  validation {
    # us-central1 is what the sprint board names; anything else triggers a
    # cost/cold-start review (some regions have higher egress).
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.gcp_region))
    error_message = "gcp_region must look like a GCP region (e.g. us-central1)."
  }
}

# ── Cloud Run sizing (S2.1.1) ───────────────────────────────────────────────

variable "middleware_image" {
  type        = string
  description = "Container image URI for the agent-middleware Cloud Run service."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
  # ^^ Bootstrap placeholder — overridden during the first real deploy by CI.
  # Kept as a real public image so `tofu apply` works end-to-end before the
  # team has pushed their own image to Artifact Registry. Per S2.1.1 DoD the
  # /healthz endpoint must return 200; the `cloudrun/container/hello` image
  # responds 200 on `/`, but we override probes to use `/healthz` so the
  # first apply WILL fail liveness — that is intentional and forces the team
  # to push a real image before promoting.
}

variable "middleware_min_instances" {
  type        = number
  description = "Cloud Run min instance count. Sprint 2 §S2.1.1: must be 0 for free tier."
  default     = 0

  validation {
    condition     = var.middleware_min_instances == 0
    error_message = "Sprint 2 §S2.1.1 acceptance criterion requires min=0 (Cloud Run free-tier scale-to-zero)."
  }
}

variable "middleware_max_instances" {
  type        = number
  description = "Cloud Run max instance count (cap to keep cost predictable)."
  default     = 10
}

variable "middleware_cpu" {
  type        = string
  description = "Cloud Run vCPU allocation. Sprint 2 §S2.1.1: 1 vCPU."
  default     = "1000m"

  validation {
    condition     = var.middleware_cpu == "1000m" || var.middleware_cpu == "1"
    error_message = "Sprint 2 §S2.1.1 requires 1 vCPU (`1000m` or `1`)."
  }
}

variable "middleware_memory" {
  type        = string
  description = "Cloud Run memory allocation. Sprint 2 §S2.1.1: 2 GB."
  default     = "2Gi"

  validation {
    condition     = var.middleware_memory == "2Gi" || var.middleware_memory == "2048Mi"
    error_message = "Sprint 2 §S2.1.1 requires 2 GB memory (`2Gi`)."
  }
}

variable "middleware_request_timeout_seconds" {
  type        = number
  description = "Cloud Run per-request timeout. Sprint 2 §S2.1.1: 3600s for long ReAct runs."
  default     = 3600

  validation {
    condition     = var.middleware_request_timeout_seconds == 3600
    error_message = "Sprint 2 §S2.1.1 requires timeout=3600s (long ReAct runs)."
  }
}

# ── Neon (S2.1.2) ───────────────────────────────────────────────────────────

variable "neon_api_key" {
  type        = string
  description = "Neon API key (https://console.neon.tech → API Keys)."
  sensitive   = true
}

variable "neon_region_id" {
  type        = string
  description = "Neon region ID. Free tier supports AWS regions only."
  default     = "aws-us-east-2"
}

variable "neon_database_name" {
  type        = string
  description = <<-EOT
    Application database name. The sprint board (S2.1.2) names `agent_app`,
    but the project chose to adopt Neon's auto-created `neondb` database
    instead (saves one moving part on the Free tier's per-project DB
    quota and avoids confusion with the unused default DB). The Drizzle
    config in Sprint 3 will pin to whatever value lives here.
  EOT
  default     = "neondb"
}

# ── Cloudflare (S2.1.3) ─────────────────────────────────────────────────────

variable "cloudflare_api_token" {
  type        = string
  description = "Cloudflare scoped API token (NOT the global API key)."
  sensitive   = true
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare account ID (dashboard sidebar)."
}

variable "cloudflare_zone_id" {
  type        = string
  description = "Cloudflare zone ID for the agent domain."
}

variable "cloudflare_pages_project_name" {
  type        = string
  description = "Pages project name (becomes <name>.pages.dev)."
  default     = "agent-frontend-dev"
}

variable "cloudflare_pages_production_branch" {
  type        = string
  description = "Git branch deployed to production."
  default     = "main"
}

# ── WorkOS public config (S2.1.4) ────────────────────────────────────────────

variable "workos_client_id" {
  type        = string
  description = "WorkOS client ID (client_…). Public-facing; not a secret, but required by the middleware for JWT issuer validation."
  default     = ""
}

# ── Secret Manager seed values (S2.1.4) ─────────────────────────────────────
#
# These hold the *values* that will land in `google_secret_manager_secret_version`
# resources. The user picked the `tofu_creates_versions` strategy in Sprint 2
# clarifications: Tofu writes the version, secret data lives in the GCS
# remote state bucket (encrypted, IAM-restricted). The dev terraform.tfvars
# file holds these locally and IS gitignored. CI passes them via
# `TF_VAR_*` env vars from the deploy runner's secret store.

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

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse Cloud Hobby public key (pk-lf-…). Public-keyish but we keep it in Secret Manager for parity with the secret-key sibling."
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse Cloud Hobby secret key (sk-lf-…)."
  sensitive   = true
}

variable "mem0_api_key" {
  type        = string
  description = "Mem0 Cloud Hobby API key (m0-…)."
  sensitive   = true
}
