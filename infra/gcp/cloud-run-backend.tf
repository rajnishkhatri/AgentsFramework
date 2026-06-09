###############################################################################
# infra/gcp/cloud-run-backend.tf
#
# GCP Tier A combined backend on Cloud Run (Recipe 4): single service hosting
# middleware auth/ACL + agent SSE runtime (Tier A Option A).
#
# Resources:
#   * google_cloud_run_v2_service.backend_combined — agent-backend-combined
#   * google_cloud_run_v2_service_iam_binding.public_invoker — allUsers invoker
#
# Wiring:
#   * Cloud SQL built-in connector via template.volumes.cloud_sql_instance
#   * Secret Manager injection for all runtime credentials
#   * Plain env vars for GCS bucket names + GCP_EXECUTION_ENV=cloudrun
#   * /healthz startup + liveness probes (pre-auth)
#
# Depends on: foundations.tf, secret-manager.tf, data.tf (Recipe 2)
###############################################################################

resource "google_cloud_run_v2_service" "backend_combined" {
  project  = var.gcp_project_id
  name     = "agent-backend-combined"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = var.backend_min_instances
      max_instance_count = var.backend_max_instances
    }

    timeout = "${var.backend_request_timeout_seconds}s"

    service_account       = google_service_account.backend_runtime.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.main.connection_name]
      }
    }

    containers {
      image = var.backend_image

      ports {
        container_port = 8080
        name           = "http1"
      }

      resources {
        limits = {
          cpu    = var.backend_cpu
          memory = var.backend_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      startup_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        initial_delay_seconds = 5
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 12
      }

      liveness_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }

      # ── Public / non-secret env vars ─────────────────────────────────────

      env {
        name  = "GCP_EXECUTION_ENV"
        value = "cloudrun"
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "v3"
      }

      env {
        name  = "AGENT_OFFLOAD_DIR"
        value = "/tmp/agent_offload"
      }

      # ── BlackBox→Langfuse relay (Tier A in-process mode) ─────────────────
      #
      # The relay runs as an asyncio task inside app_prod's lifespan. Its
      # storage dir MUST match where BlackBoxRecorder writes recordings under
      # AGENT_OFFLOAD_DIR, otherwise the relay tails an empty path.

      env {
        name  = "BLACKBOX_RELAY_MODE"
        value = "in_process"
      }

      env {
        name  = "BLACKBOX_STORAGE_DIR"
        value = "/tmp/agent_offload/black_box_recordings"
      }

      env {
        name  = "GCS_FACTS_BUCKET"
        value = google_storage_bucket.agent_facts.name
      }

      env {
        name  = "GCS_TRACES_BUCKET"
        value = google_storage_bucket.trust_traces.name
      }

      env {
        name  = "WORKSPACE_DIR"
        value = "/workspace"
      }

      # GoalJudge runtime posture (Change C — goaljudge_gcp_compatibility.plan.md)
      env {
        name  = "GOAL_JUDGE_ENABLED"
        value = "true"
      }

      env {
        name  = "GOAL_JUDGE_DOWNGRADE_ENABLED"
        value = "false"
      }

      env {
        name  = "WORKOS_CLIENT_ID"
        value = var.workos_client_id
      }

      env {
        name  = "LANGFUSE_HOST"
        value = "https://cloud.langfuse.com"
      }

      env {
        name  = "MEM0_BASE_URL"
        value = "https://api.mem0.ai"
      }

      # ── Secrets via Secret Manager ──────────────────────────────────────

      env {
        name = "WORKOS_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.workos_api_key.secret_id
            version = "latest"
          }
        }
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

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "LANGFUSE_PUBLIC_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langfuse_public_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "LANGFUSE_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.langfuse_secret_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "MEM0_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mem0_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "AGENT_FACTS_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.agent_facts_secret.secret_id
            version = "latest"
          }
        }
      }

      # ── Web search provider (SearXNG sidecar) ──────────────────────────────

      env {
        name  = "WEB_SEARCH_PROVIDER"
        value = "searxng"
      }

      env {
        name  = "SEARXNG_URL"
        value = "http://localhost:8888"
      }
    }

    # ── SearXNG sidecar container ──────────────────────────────────────────
    #
    # Private internal instance (no ingress port) on :8888 (backend uses :8080).
    # Shares the service's scale-to-zero and startup lifecycle.

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/${google_artifact_registry_repository.backend.repository_id}/searxng:latest"
      name  = "searxng"

      resources {
        limits = {
          cpu    = "0.5"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "SEARXNG_BASE_URL"
        value = "http://localhost:8888/"
      }

      env {
        name  = "GRANIAN_PORT"
        value = "8888"
      }

      startup_probe {
        http_get {
          path = "/healthz"
          port = 8888
        }
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 10
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_secret_manager_secret_iam_member.workos_api_key_accessor,
    google_secret_manager_secret_iam_member.openai_api_key_accessor,
    google_secret_manager_secret_iam_member.anthropic_api_key_accessor,
    google_secret_manager_secret_iam_member.langfuse_public_key_accessor,
    google_secret_manager_secret_iam_member.langfuse_secret_key_accessor,
    google_secret_manager_secret_iam_member.mem0_api_key_accessor,
    google_secret_manager_secret_iam_member.database_url_accessor,
    google_secret_manager_secret_iam_member.agent_facts_secret_accessor,
    google_project_iam_member.backend_runtime_cloudsql_client,
  ]
}

# ── Public invoker binding (Tier A dev) ──────────────────────────────────────
#
# Auth happens at the application layer (WorkOS JWT). Tier B recipe tightens
# this to a specific invoker SA behind an internal LB.

resource "google_cloud_run_v2_service_iam_binding" "backend_public_invoker" {
  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.backend_combined.location
  name     = google_cloud_run_v2_service.backend_combined.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}
