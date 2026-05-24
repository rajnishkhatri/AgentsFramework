###############################################################################
# infra/gcp/data.tf
#
# GCP Tier A data tier (Recipe 2): Cloud SQL PostgreSQL 15, GCS buckets for
# agent-facts and trust-traces, and IAM bindings for the backend runtime SA.
#
# Resources:
#   * google_sql_database_instance — shared-core Postgres 15, single-AZ,
#     10 GB SSD, deletion_protection=false (dev-only; Tier B enables HA+DP).
#   * google_sql_database — the application database within the instance.
#   * google_sql_user — database user for the backend runtime.
#   * google_storage_bucket.agent_facts — versioned, uniform access, public
#     access prevention. Stores signed AgentFacts JSON documents.
#   * google_storage_bucket.trust_traces — 90-day lifecycle to Nearline,
#     uniform access, public access prevention. Stores trust trace JSONL.
#   * google_project_iam_member — Cloud SQL client role for the runtime SA.
#   * google_storage_bucket_iam_member — objectViewer on facts, objectCreator
#     on traces for the runtime SA.
#
# NOT provisioned at Tier A:
#   * Pub/Sub topic (Tier B recipe B2)
#   * HA Cloud SQL (Tier B recipe B3)
#   * Filestore / NFS (Tier B recipe B4)
#
# Depends on: foundations.tf (runtime SA, project services)
###############################################################################

# ── Cloud SQL PostgreSQL 15 ──────────────────────────────────────────────────
#
# `db-f1-micro` is the smallest shared-core tier (~$7.67/mo sustained).
# `deletion_protection = false` is intentional for Tier A dev — Tier B
# upgrades to `true` + multi-AZ HA.
#
# The Cloud Run built-in connector format for DATABASE_URL is:
#   postgresql+asyncpg://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE

resource "google_sql_database_instance" "main" {
  project             = var.gcp_project_id
  name                = var.cloud_sql_instance_name
  region              = var.gcp_region
  database_version    = "POSTGRES_15"
  deletion_protection = false

  settings {
    tier              = var.cloud_sql_tier
    disk_size         = var.cloud_sql_disk_size_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = false
    availability_type = "ZONAL"
    edition           = "ENTERPRISE"

    ip_configuration {
      ipv4_enabled = true
    }

    backup_configuration {
      enabled = true
    }

    database_flags {
      name  = "max_connections"
      value = "50"
    }

    user_labels = {
      tier      = "a"
      recipe    = "2-data"
      component = "backend"
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "agent" {
  project  = var.gcp_project_id
  instance = google_sql_database_instance.main.name
  name     = var.cloud_sql_database_name
}

resource "google_sql_user" "agent" {
  project  = var.gcp_project_id
  instance = google_sql_database_instance.main.name
  name     = var.cloud_sql_user
  password = var.cloud_sql_password
}

# ── GCS bucket: agent-facts ──────────────────────────────────────────────────
#
# Stores signed AgentFacts JSON documents read by
# services/governance/agent_facts_gcs_registry.py. Versioning enabled so
# identity rollback is a metadata operation, not a re-sign+redeploy.
#
# `public_access_prevention = "enforced"` prevents accidental allUsers grants.

resource "google_storage_bucket" "agent_facts" {
  project                     = var.gcp_project_id
  name                        = "${var.gcp_project_id}-agent-facts"
  location                    = var.gcp_region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  versioning {
    enabled = true
  }

  labels = {
    tier      = "a"
    recipe    = "2-data"
    component = "trust-kernel"
  }

  depends_on = [google_project_service.required]
}

# ── GCS bucket: trust-traces ────────────────────────────────────────────────
#
# Stores trust trace JSONL written by services/trace_sinks/gcs_sink.py.
# 90-day lifecycle to Nearline class — cheap at Tier A volume (<1 GB/mo)
# and matches the Tier B pattern so no migration is needed at graduation.
#
# `force_destroy = true` is dev-only; Recipe 8 documents cleanup concerns.

resource "google_storage_bucket" "trust_traces" {
  project                     = var.gcp_project_id
  name                        = "${var.gcp_project_id}-trust-traces"
  location                    = var.gcp_region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    tier      = "a"
    recipe    = "2-data"
    component = "governance"
  }

  depends_on = [google_project_service.required]
}

# ── IAM: runtime SA → Cloud SQL client ───────────────────────────────────────
#
# `roles/cloudsql.client` is required for Cloud Run's built-in Cloud SQL
# connector (`cloud_sql_instances` annotation in Recipe 4). Without this
# the connector fails to establish the Unix domain socket to the proxy.

resource "google_project_iam_member" "backend_runtime_cloudsql_client" {
  project = var.gcp_project_id
  role    = "roles/cloudsql.client"
  member  = local.backend_runtime_member
}

# ── IAM: runtime SA → GCS agent-facts (read) ────────────────────────────────
#
# `roles/storage.objectViewer` — read-only. The runtime reads signed facts
# but never writes them (facts are published by the governance pipeline or
# a human operator).

resource "google_storage_bucket_iam_member" "agent_facts_reader" {
  bucket = google_storage_bucket.agent_facts.name
  role   = "roles/storage.objectViewer"
  member = local.backend_runtime_member
}

# ── IAM: runtime SA → GCS trust-traces (write) ──────────────────────────────
#
# `roles/storage.objectCreator` — write-only. The runtime appends trace
# JSONL but never reads or deletes. This is the narrowest role that allows
# `storage.objects.create` without granting `get`, `delete`, or `list`.

resource "google_storage_bucket_iam_member" "trust_traces_writer" {
  bucket = google_storage_bucket.trust_traces.name
  role   = "roles/storage.objectCreator"
  member = local.backend_runtime_member
}
