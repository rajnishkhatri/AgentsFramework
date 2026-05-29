# Deploy GCP Reference

This file provides deep context for the `deploy-gcp` skill.

## Phase To Recipe Map

- `preflight`
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-0 §0.1-0.5)
  - [docs/recipes/gcp/HUMAN_SETUP.md](../../../docs/recipes/gcp/HUMAN_SETUP.md)
  - Script: [scripts/bootstrap_gcp_env.sh](../../../scripts/bootstrap_gcp_env.sh)
- `foundations`
  - [docs/recipes/gcp/01_foundations.md](../../../docs/recipes/gcp/01_foundations.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.3)
- `data`
  - [docs/recipes/gcp/02_data.md](../../../docs/recipes/gcp/02_data.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.4)
- `secrets`
  - [docs/recipes/gcp/01_foundations.md](../../../docs/recipes/gcp/01_foundations.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.5)
- `images`
  - [docs/recipes/gcp/03_containerize.md](../../../docs/recipes/gcp/03_containerize.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.6)
- `backend`
  - [docs/recipes/gcp/04_backend_cloudrun.md](../../../docs/recipes/gcp/04_backend_cloudrun.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.7)
- `frontend`
  - [docs/recipes/gcp/05_frontend_cloudrun.md](../../../docs/recipes/gcp/05_frontend_cloudrun.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.8)
- `workos`
  - [docs/recipes/gcp/HUMAN_SETUP.md](../../../docs/recipes/gcp/HUMAN_SETUP.md) (Step 6)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.9)
- `observability`
  - [docs/recipes/gcp/07_observability.md](../../../docs/recipes/gcp/07_observability.md)
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-1 §1.10)
- `smoke`
  - [scripts/smoke_gcp.sh](../../../scripts/smoke_gcp.sh)
  - [docs/recipes/gcp/LOG_PIPELINE_GUIDE.md](../../../docs/recipes/gcp/LOG_PIPELINE_GUIDE.md)
- `preview`
  - [docs/recipes/gcp/09_change_detection.md](../../../docs/recipes/gcp/09_change_detection.md)
  - Advisory only; prints changed files, affected phases, and deploy identity. Not included in `all`.

## Human Gate Catalog

- Billing-enabled project and deployer credentials are operator-owned setup work:
  - [docs/recipes/gcp/HUMAN_SETUP.md](../../../docs/recipes/gcp/HUMAN_SETUP.md)
- Database migration gate after `data`:
  - Update `database-url` secret to Cloud SQL connector format
  - Run `AsyncPostgresSaver.setup()` against Cloud SQL before backend traffic
- WorkOS redirect gate after `frontend`:
  - Add `frontend_workos_redirect_uri` output value to WorkOS redirects
- Budget permissions gate before `observability` when using billing budgets:
  - Ensure billing-account-level IAM grant for deployer service account

## `deploy_gcp.sh` Environment Contract

- `DRY_RUN=1`
  - Prints commands, skips applies and other mutating actions.
- `AUTO_APPROVE=1`
  - Skips the interactive confirmation before `tofu apply`.
- `VERSION=v1`
  - Tag used for backend and frontend image build/push in `images`.
- `WRITE_TFVARS=1`
  - Updates `backend_image` and `frontend_image` in `infra/gcp/terraform.tfvars`.
  - Creates a backup at `infra/gcp/terraform.tfvars.bak`.
- `BASE_REF=origin/main`
  - Base ref for the three-dot merge-base diff in `preview`.
  - If unresolvable, `detect_changes()` fetches once then fails safe to all-phases-affected.
- `DEPLOY_VERSION=`
  - CalVer version (default: `YYYY.0M.0` from current date).
  - Used in image tags (`:DEPLOY_VERSION`) and as part of `DEPLOY_ID`.
  - If `VERSION` is unset, `VERSION` is derived from `DEPLOY_VERSION` for backward compat.
- `ENV=prod`
  - Environment name embedded in `DEPLOY_ID` (`tierA-${ENV}-${DEPLOY_VERSION}-${SHORT_SHA}`).

## Troubleshooting

- Use the runbook matrix first:
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Reference §3.1)
- For auth and SSE pipeline debugging:
  - [docs/recipes/gcp/LOG_PIPELINE_GUIDE.md](../../../docs/recipes/gcp/LOG_PIPELINE_GUIDE.md)

## Out Of Scope For This Skill

- Day-2 operations (rollbacks, scaling tuning, long-term maintenance):
  - [docs/recipes/gcp/LIVE_DEPLOYMENT.md](../../../docs/recipes/gcp/LIVE_DEPLOYMENT.md) (Day-2 section)
- Teardown workflows:
  - [scripts/teardown_gcp.sh](../../../scripts/teardown_gcp.sh)
  - [docs/recipes/gcp/08_cleanup.md](../../../docs/recipes/gcp/08_cleanup.md)
