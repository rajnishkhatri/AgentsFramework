###############################################################################
# infra/dev-tier/outputs.tf
#
# Outputs that downstream tooling (CI scripts, Sprint 3 frontend
# composition, RUNBOOK smoke checks) needs after `tofu apply`.
#
# Cross-cutting DoD enforcement: NO secret value escapes via outputs.
# Every secret-bearing var.tf entry has `sensitive = true`; we additionally
# avoid emitting `secret_data` here. The `tests/infra/test_cross_cutting.py`
# test `test_no_secret_outputs` keeps this guarantee mechanical.
###############################################################################

# ── Cloud Run ──────────────────────────────────────────────────────────────

output "middleware_url" {
  description = "Public URL of the agent-middleware Cloud Run service. Sprint 3 BFF reads this as MIDDLEWARE_URL."
  value       = google_cloud_run_v2_service.middleware.uri
}

output "middleware_runtime_service_account_email" {
  description = "Email of the dedicated runtime SA. Useful for granting additional IAM (e.g. Artifact Registry pull) outside this stack."
  value       = google_service_account.middleware_runtime.email
}

# ── Cloudflare ─────────────────────────────────────────────────────────────

output "pages_subdomain" {
  description = "*.pages.dev subdomain of the Cloudflare Pages project. Sprint 3 uses this for CORS allowlists and OAuth callback config."
  value       = cloudflare_pages_project.frontend.subdomain
}

output "pages_project_name" {
  description = "Pages project name. Used by the deploy CLI (`wrangler pages deploy`)."
  value       = cloudflare_pages_project.frontend.name
}

output "cloudflare_zone_name" {
  description = "DNS zone name (e.g. agent.example.com) the WAF + cache rulesets are attached to. Sourced from `data.cloudflare_zone.agent` so a future `terraform plan` re-confirms the zone exists at apply-time."
  value       = data.cloudflare_zone.agent.name
}

# ── Neon ───────────────────────────────────────────────────────────────────
#
# We deliberately DO NOT output `neon_database_url` directly — it goes
# into Secret Manager only. Operators who need the URL pull it via
# `gcloud secrets versions access latest --secret=neon-database-url`.

output "neon_project_id" {
  description = "Neon project ID. Read by ops scripts to scope `neonctl` commands."
  value       = neon_project.agent.id
}

output "neon_database_name" {
  description = "Application database name (= var.neon_database_name)."
  value       = neon_database.app.name
}

# ── Secret Manager ─────────────────────────────────────────────────────────

output "secret_ids" {
  description = "Map of logical-name → Secret Manager secret_id, for ops ref."
  value = {
    workos_api_key      = google_secret_manager_secret.workos_api_key.secret_id
    openai_api_key      = google_secret_manager_secret.openai_api_key.secret_id
    anthropic_api_key   = google_secret_manager_secret.anthropic_api_key.secret_id
    langfuse_public_key = google_secret_manager_secret.langfuse_public_key.secret_id
    langfuse_secret_key = google_secret_manager_secret.langfuse_secret_key.secret_id
    mem0_api_key        = google_secret_manager_secret.mem0_api_key.secret_id
    neon_database_url   = google_secret_manager_secret.neon_database_url.secret_id
  }
}
