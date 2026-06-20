# GCP deployment runbooks — bundle index

OKF sub-bundle. Each entry is a typed Concept. See the convention in [CONVENTIONS_OKF.md](../../CONVENTIONS_OKF.md).

- [Recipe 0 — GCP Runtime Adapters](00_adapters.md) — Build the five Python runtime adapters that let the framework run on GCP.
- [Recipe 1 — GCP Account Foundations](01_foundations.md) — Bootstrap the infra/gcp OpenTofu stack: APIs, Artifact Registry, foundations.
- [Recipe 2 — Data Tier (Cloud SQL + GCS Buckets)](02_data.md) — Provision the Tier A data tier: Cloud SQL PostgreSQL + GCS buckets.
- [Recipe 3 — Containerize Backend + Frontend](03_containerize.md) — Build production Docker images for the combined backend and Next.js frontend.
- [Recipe 4 — Deploy Combined Backend on Cloud Run](04_backend_cloudrun.md) — Deploy the combined Python backend as a Cloud Run service.
- [Recipe 5 — Deploy Frontend on Cloud Run](05_frontend_cloudrun.md) — Deploy the Next.js frontend as a second Cloud Run service.
- [Recipe 6 — Meta Ring (Optional)](06_meta_ring.md) — Optionally schedule nightly offline evaluation via Cloud Scheduler + Cloud Run Job.
- [Recipe 7 — Observability + Smoke Tests + Budget](07_observability.md) — Add Tier A observability: health, alerts, smoke tests, and budget.
- [Recipe 8 — Cleanup + Teardown Order](08_cleanup.md) — Safe teardown order for the GCP Tier A stack (partial or full).
- [Recipe 9 — Change Detection + Deploy Identity](09_change_detection.md) — Branch-vs-main change detection plus a hybrid CalVer+SHA deploy identity.
- [Recipe 10 — Real Web Search (SearXNG sidecar) + No-Progress Detection](10_web_search_searxng.md) — Replace the web_search stub with a SearXNG sidecar + no-progress detection.
- [GCP Tier A — Human Setup Runbook](HUMAN_SETUP.md) — One-time human setup steps for the GCP Tier A stack.
- [GCP Tier A — Live Deployment Operator Runbook](LIVE_DEPLOYMENT.md) — Operator runbook for a live GCP Tier A deployment.
- [GCP Log Pipeline Guide — End-to-End Flow Analysis](LOG_PIPELINE_GUIDE.md) — End-to-end analysis of the GCP log pipeline flow.
- [Skill Deploy Guide — From Runbook to Autopilot](SKILL_DEPLOY_GUIDE.md) — Drive GCP deploys via the deploy-gcp skill and its orchestrator.
- [Tier B Future Recipes — Decoupled GCP Production Topology](TIER_B_FUTURE.md) — When and how to graduate from Tier A dev to a Tier B production topology.
