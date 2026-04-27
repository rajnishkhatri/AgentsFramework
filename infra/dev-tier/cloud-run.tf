###############################################################################
# infra/dev-tier/cloud-run.tf — Sprint 2 §S2.1.1
#
# Provisions the `agent-middleware` Cloud Run v2 service on the GCP free
# tier. Acceptance criteria from the sprint board:
#
#   * Service name: agent-middleware
#   * min_instance_count = 0   (free-tier scale-to-zero)
#   * max_instance_count = 10  (cost cap, sized for beta traffic)
#   * 1 vCPU / 2 GB RAM
#   * timeout = 3600s (long ReAct runs)
#   * startup_cpu_boost = true (cold start <200ms)
#   * /healthz returns 200 (probe target — middleware/server.py exposes it pre-auth)
#
# Cross-cutting DoD touched here:
#   * Sprint 2 §S2.1.4 — dedicated SA `middleware_runtime` (NOT default
#     Compute Engine SA) so Secret Manager IAM bindings are scoped least-
#     privilege. The SA is granted secretAccessor on each individual secret
#     in secret-manager.tf, never project-wide.
#   * Frontend cross-cutting (FD3.SEC1, FE-AP-18 AUTO-REJECT): no
#     `NEXT_PUBLIC_*` env vars are set on this service. Public env vars
#     belong on Cloudflare Pages, not on the middleware that holds secrets.
###############################################################################

# ── Runtime service account ─────────────────────────────────────────────────
#
# Per Sprint 2 §S2.1.4 DoD: 'Cloud Run accesses [Secret Manager] via IAM
# role'. A dedicated SA scoped to roles/secretmanager.secretAccessor on
# specific secrets is the least-privilege wiring.

resource "google_service_account" "middleware_runtime" {
  account_id   = "agent-middleware-runtime"
  display_name = "Agent Middleware (Cloud Run runtime)"
  description  = "Runtime identity for the agent-middleware Cloud Run service. Granted secretAccessor on individual middleware secrets only — see infra/dev-tier/secret-manager.tf."
}

# ── The Cloud Run service ──────────────────────────────────────────────────
#
# Resource type is `google_cloud_run_v2_service` (NOT v1). v2 is GA,
# supports startup_cpu_boost natively, and matches the FRONTEND_PLAN
# expectation that we use the modern execution environment.

resource "google_cloud_run_v2_service" "middleware" {
  name     = "agent-middleware"
  location = var.gcp_region

  # ingress: INGRESS_TRAFFIC_ALL is the dev-tier choice because the BFF on
  # Cloudflare Pages calls this service over the public internet. Stage B
  # (V2-Frontier) flips this to INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER and
  # adds an HTTPS LB — see RUNBOOK.md §Stage A→B.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    # ── scaling ────────────────────────────────────────────────────────
    # min=0 is the hard acceptance criterion (Sprint 2 §S2.1.1 + the
    # `middleware_min_instances` Tofu validator block).
    scaling {
      min_instance_count = var.middleware_min_instances
      max_instance_count = var.middleware_max_instances
    }

    # ── per-request timeout ────────────────────────────────────────────
    # 3600s = 1 hour. ReAct loops with deep tool fanout (file_io +
    # web_search composed) regularly run >10 min when reasoning over
    # large repos. Anything below 1 hr risks truncating valid runs.
    timeout = "${var.middleware_request_timeout_seconds}s"

    # ── runtime identity ───────────────────────────────────────────────
    service_account = google_service_account.middleware_runtime.email

    # Cloud Run v2 free tier requires `execution_environment = EXECUTION_ENVIRONMENT_GEN2`
    # for full CPU access (gen1 throttles); gen2 is also the default but
    # we set it explicitly to survive provider default flips.
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    containers {
      image = var.middleware_image

      ports {
        container_port = 8080
        name           = "http1"
      }

      resources {
        limits = {
          cpu    = var.middleware_cpu
          memory = var.middleware_memory
        }
        # cpu_idle = true is REQUIRED for free-tier billing on min=0 services
        # (lets Cloud Run scale CPU to 0 between requests). Without it,
        # idle CPU minutes count against the free tier.
        cpu_idle          = true
        startup_cpu_boost = true
      }

      # ── startup probe ──────────────────────────────────────────────
      # Sprint 2 §S2.1.1 DoD: /healthz returns 200. middleware/server.py
      # exposes /healthz pre-auth precisely so this probe doesn't need a
      # bearer token.
      startup_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        initial_delay_seconds = 0
        timeout_seconds       = 5
        period_seconds        = 5
        failure_threshold     = 3
      }

      # ── liveness probe ─────────────────────────────────────────────
      # Same /healthz endpoint. Liveness ticks slower than startup; a
      # failure restarts the container.
      liveness_probe {
        http_get {
          path = "/healthz"
          port = 8080
        }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }

      # Public, non-secret env vars only. Secrets land via
      # `value_source.secret_key_ref` — see secret-manager.tf for the
      # bindings that materialise as `env { value_source { ... } }`
      # blocks added below by the secret-manager.tf merger pattern.
      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "v3"
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

      # ── Secrets injected by Secret Manager ────────────────────────
      # The secret_key_ref blocks below mirror the
      # google_secret_manager_secret resources in secret-manager.tf.
      # Keeping them inline (rather than dynamic) makes the Cloud Run
      # service definition fully self-describing for code review.

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
            secret  = google_secret_manager_secret.neon_database_url.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  # Bind traffic to the latest deployed revision so the team's
  # `gcloud run deploy` flow doesn't need to re-route after a Tofu apply.
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  # The secret_manager IAM bindings must exist before Cloud Run pulls the
  # secret values at boot — explicit dependency keeps `tofu apply` ordering
  # deterministic without relying on implicit reference graphs alone.
  depends_on = [
    google_secret_manager_secret_iam_member.workos_api_key_accessor,
    google_secret_manager_secret_iam_member.openai_api_key_accessor,
    google_secret_manager_secret_iam_member.anthropic_api_key_accessor,
    google_secret_manager_secret_iam_member.langfuse_public_key_accessor,
    google_secret_manager_secret_iam_member.langfuse_secret_key_accessor,
    google_secret_manager_secret_iam_member.mem0_api_key_accessor,
    google_secret_manager_secret_iam_member.neon_database_url_accessor,
  ]
}

# ── Public invoker binding ──────────────────────────────────────────────────
#
# Sprint 2 dev-tier accepts allUsers invoker (the BFF authenticates via
# WorkOS at the application layer, not via Cloud Run IAM). Stage B
# tightens this to a specific Cloud Run invoker SA bound from the LB.
#
# This is a *binding* not a *member* so we own the full member set on the
# service (replacing whatever stale `roles/run.invoker` grants existed).

resource "google_cloud_run_v2_service_iam_binding" "public_invoker" {
  location = google_cloud_run_v2_service.middleware.location
  name     = google_cloud_run_v2_service.middleware.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}
