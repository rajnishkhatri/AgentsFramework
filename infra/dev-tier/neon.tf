###############################################################################
# infra/dev-tier/neon.tf — Sprint 2 §S2.1.2 (import-existing variant)
#
# Provisions:
#   * Adopts the existing Neon Free project that was auto-created on
#     account signup (Neon Free quota: 1 project / account, so we cannot
#     create a second). The project was renamed in the Neon dashboard to
#     `agent-prod-dev`. Tofu adopts it via `import {}` blocks (Tofu 1.5+).
#   * Adopts the existing `neondb` database owned by `neondb_owner`.
#   * Adds the pgvector extension via the `cyrilgdn/postgresql` provider.
#
# Why import instead of create?
#   * Neon Free = 1 project / account. The user's account already has
#     `still-credit-23413998` (renamed to `agent-prod-dev`). A second
#     `tofu apply` that tries to create another project hits HTTP 402
#     ("plan limit exceeded").
#   * Per the Sprint 2 user clarification ("import_existing"): keep the
#     existing project, use the existing `neondb` database (which Neon
#     auto-creates on signup), only add pgvector + secret wiring.
#
# Import IDs (kislerdm/neon provider):
#   * neon_project.agent           → "still-credit-23413998"
#   * neon_database.app            → "still-credit-23413998/<branch_id>/neondb"
#
# Cross-stack handoff:
#   * Locals at the bottom (`neon_pg_*` and `neon_database_url`) are the
#     single bridge between this file and the postgresql provider /
#     Secret Manager. The pytest test
#     `test_neon_connection_locals_defined` enforces presence.
###############################################################################

# ── Adopt the existing project ─────────────────────────────────────────────
#
# The `import {}` block runs once during the next `tofu apply` to adopt
# the live project into Tofu state, then this resource block becomes the
# source of truth. Subsequent `tofu plan` runs see no diff.
#
# IMPORTANT: the resource attributes below MUST match the existing
# project's live values, or `tofu apply` will try to update the project
# (which on Neon Free can fail or be no-op silently). Captured from the
# Neon API on 2026-04-23:
#   pg_version: 17           (Neon's current default; cannot be downgraded)
#   region_id:  aws-us-east-2
#   name:       agent-prod-dev
#   history_retention_seconds: 21600  (6h — Free tier default)

import {
  to = neon_project.agent
  id = "still-credit-23413998"
}

resource "neon_project" "agent" {
  name                      = "agent-prod-dev"
  region_id                 = var.neon_region_id
  pg_version                = 17
  history_retention_seconds = 21600
  store_password            = "yes"
}

# ── Adopt the existing `neondb` database ───────────────────────────────────
#
# The default branch `br-square-salad-ae026um3` (named "production") was
# auto-created with the project. Its `neondb` database is owned by
# `neondb_owner` — the auto-generated default role. We adopt both so
# Tofu owns the lifecycle going forward, but no fields change on apply.
#
# Branch ID is referenced via the project's `default_branch_id`
# attribute (computed by the provider after import).

import {
  to = neon_database.app
  id = "still-credit-23413998/br-square-salad-ae026um3/neondb"
}

resource "neon_database" "app" {
  project_id = neon_project.agent.id
  branch_id  = "br-square-salad-ae026um3"
  name       = var.neon_database_name # = "neondb"
  owner_name = "neondb_owner"
}

# ── pgvector extension ─────────────────────────────────────────────────────
#
# `postgresql_extension` runs `CREATE EXTENSION IF NOT EXISTS vector;` on
# the database. This IS net-new — the existing `neondb` doesn't ship with
# pgvector enabled by default. Provider must be configured with the
# connection details of `neon_database.app` — see the `local.neon_pg_*`
# block below and the `provider "postgresql" {}` configuration in
# versions.tf.
#
# `if_not_exists = true` makes the resource idempotent across re-applies.

resource "postgresql_extension" "pgvector" {
  name         = "vector"
  database     = neon_database.app.name
  schema       = "public"
  drop_cascade = false

  depends_on = [
    neon_database.app,
  ]
}

# ── Locals: cross-file wiring ──────────────────────────────────────────────
#
# These locals translate the `neon_project` resource outputs into the shape
# the `postgresql` provider and Secret Manager need. Keeping them in this
# file (rather than versions.tf) means a future Neon swap (e.g. Stage B
# graduation to a self-managed Postgres) only edits ONE file.
#
# We use `database_host_pooler` (PgBouncer-fronted) rather than the direct
# host because serverless workloads on Cloud Run benefit from connection
# pooling, especially given Neon's 5-minute auto-suspend.

locals {
  neon_pg_host     = neon_project.agent.database_host_pooler
  neon_pg_user     = "neondb_owner"
  neon_pg_password = neon_project.agent.database_password
  neon_pg_database = neon_database.app.name

  # Connection string in standard libpq URI form, sslmode=require because
  # Neon's edge requires TLS.
  neon_database_url = format(
    "postgresql://%s:%s@%s/%s?sslmode=require",
    local.neon_pg_user,
    local.neon_pg_password,
    local.neon_pg_host,
    local.neon_pg_database,
  )
}
