###############################################################################
# infra/dev-tier/secret-manager.tf — Sprint 2 §S2.1.4
#
# All credentials the middleware reads at runtime live as
# `google_secret_manager_secret` resources here; their values come from
# `var.<...>` references (Sprint 2 §S2.1.4 DoD: NO credentials hardcoded).
#
# Secret strategy: `tofu_creates_versions` (per Sprint 2 user clarification).
#   * Tofu creates BOTH the secret 'shell' AND its version.
#   * Version `secret_data` is sourced from a sensitive Tofu variable
#     populated locally via `terraform.tfvars` (gitignored) or in CI via
#     `TF_VAR_<name>` env vars.
#   * State lives in the GCS remote backend (versioned, IAM-restricted),
#     so the secret value never lands on a developer laptop.
#
# Cross-cutting DoD:
#   * `roles/secretmanager.secretAccessor` granted ONLY to the dedicated
#     `google_service_account.middleware_runtime` SA (cloud-run.tf).
#   * No `allUsers` / `allAuthenticatedUsers` / personal-account bindings.
#   * No `NEXT_PUBLIC_*` named variables hold any of these values
#     (variables.tf naming policy enforced by
#     `tests/infra/test_secret_manager.py::test_no_secret_var_is_named_next_public`).
###############################################################################

# ── Locals ──────────────────────────────────────────────────────────────────
#
# `secret_definitions` is the single source of truth for the per-secret
# wiring. Adding a new secret means adding ONE row here; the Cloud Run env
# block (cloud-run.tf) lists the same names explicitly so a code reviewer
# can see the binding without chasing a `for_each`.
#
# Rationale for `local` over a true `for_each`: the `secret_key_ref`
# blocks in cloud-run.tf must name resources by their static address
# (e.g. `google_secret_manager_secret.workos_api_key.secret_id`). A
# for_each here would make Cloud Run's env binding less self-evident.

locals {
  middleware_runtime_member = "serviceAccount:${google_service_account.middleware_runtime.email}"
}

# ── workos_api_key ─────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "workos_api_key" {
  secret_id = "workos-api-key"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "workos"
  }
}

resource "google_secret_manager_secret_version" "workos_api_key" {
  secret      = google_secret_manager_secret.workos_api_key.id
  secret_data = var.workos_api_key

  # Don't disable old versions automatically — operators may rotate via
  # `gcloud secrets versions add` and we don't want Tofu fighting them.
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "workos_api_key_accessor" {
  secret_id = google_secret_manager_secret.workos_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}

# ── openai_api_key ─────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "openai"
  }
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret          = google_secret_manager_secret.openai_api_key.id
  secret_data     = var.openai_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "openai_api_key_accessor" {
  secret_id = google_secret_manager_secret.openai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}

# ── anthropic_api_key ──────────────────────────────────────────────────────

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "anthropic-api-key"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "anthropic"
  }
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret          = google_secret_manager_secret.anthropic_api_key.id
  secret_data     = var.anthropic_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "anthropic_api_key_accessor" {
  secret_id = google_secret_manager_secret.anthropic_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}

# ── langfuse_public_key ────────────────────────────────────────────────────
# Public-keyish but kept in Secret Manager for parity with the secret-key
# sibling (and so rotating it doesn't require touching env vars on the
# Cloud Run service — Tofu just bumps the version).

resource "google_secret_manager_secret" "langfuse_public_key" {
  secret_id = "langfuse-public-key"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "langfuse"
  }
}

resource "google_secret_manager_secret_version" "langfuse_public_key" {
  secret          = google_secret_manager_secret.langfuse_public_key.id
  secret_data     = var.langfuse_public_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "langfuse_public_key_accessor" {
  secret_id = google_secret_manager_secret.langfuse_public_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}

# ── langfuse_secret_key ────────────────────────────────────────────────────

resource "google_secret_manager_secret" "langfuse_secret_key" {
  secret_id = "langfuse-secret-key"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "langfuse"
  }
}

resource "google_secret_manager_secret_version" "langfuse_secret_key" {
  secret          = google_secret_manager_secret.langfuse_secret_key.id
  secret_data     = var.langfuse_secret_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "langfuse_secret_key_accessor" {
  secret_id = google_secret_manager_secret.langfuse_secret_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}

# ── mem0_api_key ───────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "mem0_api_key" {
  secret_id = "mem0-api-key"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "mem0"
  }
}

resource "google_secret_manager_secret_version" "mem0_api_key" {
  secret          = google_secret_manager_secret.mem0_api_key.id
  secret_data     = var.mem0_api_key
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "mem0_api_key_accessor" {
  secret_id = google_secret_manager_secret.mem0_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}

# ── neon_database_url ──────────────────────────────────────────────────────
# Connection string for the Neon Free Postgres cluster (Sprint 2 §S2.1.2).
# The value is NOT a literal — it is computed from the `neon_project`
# resource outputs in neon.tf and passed into Secret Manager via the
# `local.neon_database_url` local, so a single Tofu apply provisions
# both substrate and credential atomically.

resource "google_secret_manager_secret" "neon_database_url" {
  secret_id = "neon-database-url"
  replication {
    auto {}
  }
  labels = {
    sprint    = "s2-1-4"
    component = "middleware"
    provider  = "neon"
  }
}

resource "google_secret_manager_secret_version" "neon_database_url" {
  secret          = google_secret_manager_secret.neon_database_url.id
  secret_data     = local.neon_database_url
  deletion_policy = "ABANDON"
}

resource "google_secret_manager_secret_iam_member" "neon_database_url_accessor" {
  secret_id = google_secret_manager_secret.neon_database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.middleware_runtime_member
}
