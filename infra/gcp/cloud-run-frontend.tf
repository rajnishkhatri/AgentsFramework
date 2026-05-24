###############################################################################
# infra/gcp/cloud-run-frontend.tf
#
# GCP Tier A Next.js frontend on Cloud Run (Recipe 5): BFF + SSR UI that
# proxies authenticated requests to the combined backend via MIDDLEWARE_URL.
#
# Resources:
#   * google_cloud_run_v2_service.frontend — agent-frontend
#   * google_cloud_run_v2_service_iam_binding.frontend_public_invoker
#
# Wiring:
#   * MIDDLEWARE_URL → Recipe 4 backend Cloud Run URI
#   * NEXT_PUBLIC_WORKOS_REDIRECT_URI → this service URI + /api/auth/callback
#   * WorkOS BFF secrets via Secret Manager (WORKOS_API_KEY, WORKOS_COOKIE_PASSWORD)
#   * No backend credentials (DATABASE_URL, LLM keys, agent-facts secret)
#
# Depends on: foundations.tf, secret-manager.tf, cloud-run-backend.tf (Recipe 4)
###############################################################################

resource "google_cloud_run_v2_service" "frontend" {
  project  = var.gcp_project_id
  name     = "agent-frontend"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = var.frontend_min_instances
      max_instance_count = var.frontend_max_instances
    }

    timeout = "${var.frontend_request_timeout_seconds}s"

    service_account       = google_service_account.frontend_runtime.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    containers {
      image = var.frontend_image

      ports {
        container_port = 3000
        name           = "http1"
      }

      resources {
        limits = {
          cpu    = var.frontend_cpu
          memory = var.frontend_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        http_get {
          path = "/"
          port = 3000
        }
        initial_delay_seconds = 0
        timeout_seconds       = 5
        period_seconds        = 5
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/"
          port = 3000
        }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }

      # ── Public / non-secret env vars ─────────────────────────────────────

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "v3"
      }

      env {
        name  = "MIDDLEWARE_URL"
        value = google_cloud_run_v2_service.backend_combined.uri
      }

      env {
        name  = "WORKOS_CLIENT_ID"
        value = var.workos_client_id
      }

      env {
        name  = "NEXT_PUBLIC_WORKOS_REDIRECT_URI"
        value = "${google_cloud_run_v2_service.frontend.uri}/api/auth/callback"
      }

      # ── BFF-only secrets via Secret Manager ─────────────────────────────

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
        name = "WORKOS_COOKIE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.workos_cookie_password.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_cloud_run_v2_service.backend_combined,
    google_secret_manager_secret_iam_member.workos_api_key_frontend_accessor,
    google_secret_manager_secret_iam_member.workos_cookie_password_accessor,
  ]
}

# ── Public invoker binding (Tier A dev) ──────────────────────────────────────
#
# Auth happens at the application layer (WorkOS session cookie + JWT to backend).
# Tier B recipe tightens this behind Cloud Armor / IAP.

resource "google_cloud_run_v2_service_iam_binding" "frontend_public_invoker" {
  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.frontend.location
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}
