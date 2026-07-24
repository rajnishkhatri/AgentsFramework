###############################################################################
# infra/gcp/secret-manager.tf
#
# All credentials the combined backend reads at runtime. Strategy mirrors
# infra/dev-tier/secret-manager.tf (`tofu_creates_versions`): Tofu creates
# both the secret shell and its first version. Values come from sensitive
# Tofu variables — never hardcoded.
#
# Cross-cutting DoD:
#   * `roles/secretmanager.secretAccessor` granted ONLY to the dedicated
#     `backend_runtime` SA (foundations.tf). Never allUsers / personal accounts.
#   * `secret_data` always references `var.<name>` — tested by
#     `tests/infra/gcp/test_secret_manager.py::test_no_plaintext_secret_data`.
#   * `deletion_policy = "ABANDON"` — operators rotate via
#     `gcloud secrets versions add`; Tofu tracks the shell, not every version.
#
# Secrets provisioned here (9 total):
#   1. workos-api-key      — WorkOS auth (backend + frontend BFF)
#   2. openai-api-key      — LiteLLM primary model
#   3. anthropic-api-key   — LiteLLM fallback model
#   4. langfuse-public-key — Observability (eval capture)
#   5. langfuse-secret-key — Observability (eval capture)
#   6. mem0-api-key        — Long-term memory service
#   7. database-url        — Cloud SQL connection (placeholder; real value in Recipe 2)
#   8. agent-facts-secret      — HMAC signing key for AgentFacts trust records
#   9. workos-cookie-password  — iron-session encryption for frontend BFF (Recipe 5)
###############################################################################

# ── Locals ───────────────────────────────────────────────────────────────────

locals {
  backend_runtime_member  = "serviceAccount:${google_service_account.backend_runtime.email}"
  frontend_runtime_member = "serviceAccount:${google_service_account.frontend_runtime.email}"
}

# ── 1. workos-api-key ────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "workos_api_key" {
  project   = var.gcp_project_id
  secret_id = "workos-api-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "workos"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "workos_api_key" {
  secret          = google_secret_manager_secret.workos_api_key.id
  secret_data     = var.workos_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "workos_api_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.workos_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

resource "google_secret_manager_secret_iam_member" "workos_api_key_frontend_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.workos_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.frontend_runtime_member
}

# ── 2. openai-api-key ────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "openai_api_key" {
  project   = var.gcp_project_id
  secret_id = "openai-api-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "openai"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret          = google_secret_manager_secret.openai_api_key.id
  secret_data     = var.openai_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "openai_api_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.openai_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 3. anthropic-api-key ─────────────────────────────────────────────────────

resource "google_secret_manager_secret" "anthropic_api_key" {
  project   = var.gcp_project_id
  secret_id = "anthropic-api-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "anthropic"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret          = google_secret_manager_secret.anthropic_api_key.id
  secret_data     = var.anthropic_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "anthropic_api_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.anthropic_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 3b. deepseek-api-key ──────────────────────────────────────────────────────
# Same dispatch-by-prefix as anthropic: LiteLLM reads DEEPSEEK_API_KEY from the
# container env for the deepseek/* profile set. Mirrors the anthropic resources.
resource "google_secret_manager_secret" "deepseek_api_key" {
  project   = var.gcp_project_id
  secret_id = "deepseek-api-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "deepseek"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "deepseek_api_key" {
  secret          = google_secret_manager_secret.deepseek_api_key.id
  secret_data     = var.deepseek_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "deepseek_api_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.deepseek_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 4. langfuse-public-key ───────────────────────────────────────────────────
# Stored in Secret Manager for parity with the secret-key sibling so rotation
# is a single `gcloud secrets versions add` with no Cloud Run env-var change.

resource "google_secret_manager_secret" "langfuse_public_key" {
  project   = var.gcp_project_id
  secret_id = "langfuse-public-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "langfuse"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "langfuse_public_key" {
  secret          = google_secret_manager_secret.langfuse_public_key.id
  secret_data     = var.langfuse_public_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "langfuse_public_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.langfuse_public_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 5. langfuse-secret-key ───────────────────────────────────────────────────

resource "google_secret_manager_secret" "langfuse_secret_key" {
  project   = var.gcp_project_id
  secret_id = "langfuse-secret-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "langfuse"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "langfuse_secret_key" {
  secret          = google_secret_manager_secret.langfuse_secret_key.id
  secret_data     = var.langfuse_secret_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "langfuse_secret_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.langfuse_secret_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 6. mem0-api-key ──────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "mem0_api_key" {
  project   = var.gcp_project_id
  secret_id = "mem0-api-key"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "mem0"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "mem0_api_key" {
  secret          = google_secret_manager_secret.mem0_api_key.id
  secret_data     = var.mem0_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "mem0_api_key_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.mem0_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 7. database-url ──────────────────────────────────────────────────────────
# Cloud SQL connection string for AsyncPostgresSaver. The default placeholder
# value is overwritten in Recipe 2 once the Cloud SQL instance is provisioned.
# Operators update via: gcloud secrets versions add database-url --data-file=-

resource "google_secret_manager_secret" "database_url" {
  project   = var.gcp_project_id
  secret_id = "database-url"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "backend"
    provider  = "cloud-sql"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret          = google_secret_manager_secret.database_url.id
  secret_data     = var.database_url
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "database_url_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# Frontend BFF also needs DATABASE_URL (coach-v3 durable engine FR-F1/F3):
# threads + coach-marker + EngineDb all flip to Pg when the env is set.
# Accessor is SEPARATE from the backend member so least-privilege stays clear.
resource "google_secret_manager_secret_iam_member" "database_url_frontend_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.frontend_runtime_member
}

# ── 8. agent-facts-secret ────────────────────────────────────────────────────
# HMAC signing key consumed by trust/models.py AgentFacts.sign(). Belongs in
# trust/ by AGENTS.md §Trust Kernel Rules (shared, stable, dependency-free),
# but its *value* is an operational secret managed here.

resource "google_secret_manager_secret" "agent_facts_secret" {
  project   = var.gcp_project_id
  secret_id = "agent-facts-secret"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "1-foundations"
    component = "trust-kernel"
    provider  = "internal"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "agent_facts_secret" {
  secret          = google_secret_manager_secret.agent_facts_secret.id
  secret_data     = var.agent_facts_secret
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "agent_facts_secret_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.agent_facts_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_runtime_member
}

# ── 9. workos-cookie-password ────────────────────────────────────────────────
# iron-session encryption key for WorkOS AuthKit on the Next.js BFF.
# Frontend-only — backend middleware validates JWTs and does not set cookies.

resource "google_secret_manager_secret" "workos_cookie_password" {
  project   = var.gcp_project_id
  secret_id = "workos-cookie-password"
  replication {
    auto {}
  }
  labels = {
    tier      = "a"
    recipe    = "5-frontend"
    component = "frontend"
    provider  = "workos"
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "workos_cookie_password" {
  secret          = google_secret_manager_secret.workos_cookie_password.id
  secret_data     = var.workos_cookie_password
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "workos_cookie_password_accessor" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.workos_cookie_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.frontend_runtime_member
}
