###############################################################################
# infra/dev-tier/cloudflare-pages.tf — Sprint 2 §S2.1.3 (Pages half)
#
# Provisions the Cloudflare Pages project that hosts the Next.js BFF.
#
# Why Pages and not Workers? Pages gives us:
#   * Native SSE pass-through (no `CachingDisabled` workaround needed —
#     this was the V1-vs-CloudFront pain point that motivated V3-Dev-Tier).
#   * Free, unlimited request bandwidth.
#   * Built-in preview deployments per PR.
#   * Edge runtime for the SSE forwarding Route Handler
#     (transport/edge_proxy.ts in Sprint 3).
#
# Build config:
#   * Build command + output dir are placeholders here; they're
#     overridden by the Sprint 3 Next.js scaffold via Pages' deployment
#     pipeline. Keeping them empty here means we don't fight the BFF
#     team's `wrangler` config.
###############################################################################

resource "cloudflare_pages_project" "frontend" {
  account_id        = var.cloudflare_account_id
  name              = var.cloudflare_pages_project_name
  production_branch = var.cloudflare_pages_production_branch

  # Build config — set to no-op here; the actual build runs through the
  # Pages CLI / GitHub integration that Sprint 3 wires up. Tofu owns the
  # *project* identity; the *build* is owned by CI to avoid drift.
  build_config {
    build_command   = ""
    destination_dir = ".vercel/output/static"
    root_dir        = "frontend"
  }

  # Production deployment env vars. Strictly NON-secret values only — the
  # cross-cutting DoD (FE-AP-18 AUTO-REJECT) forbids `NEXT_PUBLIC_*KEY*`
  # / `*SECRET*` / `*TOKEN*`. These are the public knobs the frontend
  # composition root reads at module load time.
  deployment_configs {
    production {
      environment_variables = {
        ARCHITECTURE_PROFILE = "v3"
        # MIDDLEWARE_URL is set after first Cloud Run apply via
        # `cloudflare_pages_project_environment_variable` (kept out of
        # this base config so a fresh Tofu apply doesn't 422 on missing
        # Cloud Run URL).
      }
      compatibility_flags = ["nodejs_compat"]
      # Compatibility date pinned per Cloudflare release notes; bump
      # quarterly per RUNBOOK.md.
      compatibility_date = "2026-04-01"
    }

    preview {
      environment_variables = {
        ARCHITECTURE_PROFILE = "v3"
      }
      compatibility_flags = ["nodejs_compat"]
      compatibility_date  = "2026-04-01"
    }
  }
}
