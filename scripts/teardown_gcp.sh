#!/usr/bin/env bash
# scripts/teardown_gcp.sh — Recipe 8 phased or full teardown for GCP Tier A.
#
# Modes:
#   partial (default) — remove compute, observability, and data; keep Artifact
#                       Registry, Secret Manager shells, and service accounts
#                       (~$0.60/mo retained) for fast re-deploy.
#   full              — `tofu destroy` on the entire infra/gcp stack (except the
#                       remote state bucket, which lives outside this stack).
#
# Usage:
#   CONFIRM=1 MODE=partial ./scripts/teardown_gcp.sh       # partial (default), skip prompt
#   CONFIRM=1 MODE=full ./scripts/teardown_gcp.sh          # full stack destroy
#   CONFIRM=1 ./scripts/teardown_gcp.sh                    # partial, interactive confirm
#   DRY_RUN=1 ./scripts/teardown_gcp.sh                   # print commands only
#
# Prerequisites:
#   * GOOGLE_APPLICATION_CREDENTIALS set (tofu-deployer SA)
#   * `tofu init` already run in infra/gcp with backend config
#   * Run from repo root (or any cwd — script resolves paths)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra/gcp"
MODE="${MODE:-partial}"
CONFIRM="${CONFIRM:-}"
DRY_RUN="${DRY_RUN:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}INFO${NC}: $*"; }
warn() { echo -e "${YELLOW}WARN${NC}: $*"; }
fail() { echo -e "${RED}FAIL${NC}: $*"; exit 1; }

run() {
  echo "+ $*"
  if [[ -z "${DRY_RUN}" ]]; then
    "$@"
  fi
}

if ! command -v tofu >/dev/null 2>&1; then
  fail "OpenTofu (tofu) not found — install via brew install opentofu"
fi

if [[ ! -d "${INFRA_DIR}" ]]; then
  fail "Expected infra dir at ${INFRA_DIR}"
fi

if [[ "${MODE}" != "partial" && "${MODE}" != "full" ]]; then
  fail "MODE must be 'partial' or 'full', got: ${MODE}"
fi

echo "=== GCP Tier A teardown (Recipe 8) ==="
echo "Mode:     ${MODE}"
echo "Infra:    ${INFRA_DIR}"
[[ -n "${DRY_RUN}" ]] && warn "DRY_RUN enabled — commands will not execute"
echo

if [[ -z "${CONFIRM}" ]]; then
  if [[ "${MODE}" == "partial" ]]; then
    warn "Partial destroy removes Cloud Run, observability, and data tier."
    warn "Retains: Artifact Registry, Secret Manager, service accounts, APIs."
  else
    warn "Full destroy removes ALL resources managed by infra/gcp/."
    warn "Does NOT delete the remote state bucket (${PROJECT:-<project>}-tofu-state)."
  fi
  read -r -p "Type 'destroy' to continue: " answer
  [[ "${answer}" == "destroy" ]] || fail "Aborted — set CONFIRM=1 to skip prompt"
fi

cd "${INFRA_DIR}"

# ── Partial: targeted destroy in safe order ──────────────────────────────────

partial_destroy() {
  info "Phase 1 — Meta ring (no-op when enable_meta_ring=false)"
  run tofu destroy -auto-approve \
    -target=google_cloud_scheduler_job.meta_eval \
    -target=google_cloud_run_v2_job_iam_member.meta_scheduler_invoker \
    -target=google_cloud_run_v2_job.meta_eval \
    -target=google_secret_manager_secret_iam_member.openai_api_key_meta_accessor \
    -target=google_storage_bucket_iam_member.meta_trust_traces_writer \
    -target=google_storage_bucket_iam_member.meta_trust_traces_reader \
    -target=google_project_iam_member.meta_runtime_log_writer \
    -target=google_artifact_registry_repository_iam_member.meta_runtime_ar_reader \
    -target=google_service_account.meta_scheduler \
    -target=google_service_account.meta_runtime \
    || true

  info "Phase 2 — Observability (Recipe 7)"
  run tofu destroy -auto-approve \
    -target=google_billing_budget.tier_a \
    -target=google_monitoring_alert_policy.cloud_sql_connections \
    -target=google_monitoring_alert_policy.backend_latency_p95 \
    -target=google_monitoring_alert_policy.backend_5xx_rate \
    -target=google_monitoring_dashboard.agent_tier_a \
    -target=google_monitoring_notification_channel.email

  info "Phase 3 — Frontend Cloud Run (Recipe 5)"
  run tofu destroy -auto-approve \
    -target=google_cloud_run_v2_service_iam_binding.frontend_public_invoker \
    -target=google_cloud_run_v2_service.frontend

  info "Phase 4 — Backend Cloud Run (Recipe 4)"
  run tofu destroy -auto-approve \
    -target=google_cloud_run_v2_service_iam_binding.backend_public_invoker \
    -target=google_cloud_run_v2_service.backend_combined

  info "Phase 5 — Data tier (Recipe 2)"
  run tofu destroy -auto-approve \
    -target=google_storage_bucket_iam_member.trust_traces_writer \
    -target=google_storage_bucket_iam_member.agent_facts_reader \
    -target=google_project_iam_member.backend_runtime_cloudsql_client \
    -target=google_storage_bucket.trust_traces \
    -target=google_storage_bucket.agent_facts \
    -target=google_sql_user.agent \
    -target=google_sql_database.agent \
    -target=google_sql_database_instance.main

  echo
  info "Partial teardown complete."
  info "Retained: Artifact Registry, Secret Manager, runtime SAs, enabled APIs."
  info "Re-deploy: Recipes 2–7 (data → images → Cloud Run → observability)."
}

full_destroy() {
  info "Full stack destroy — all infra/gcp resources"
  run tofu destroy -auto-approve
  echo
  info "Full teardown complete."
  warn "Remote state bucket and tofu-deployer SA key are operator-managed — not deleted by this script."
}

case "${MODE}" in
  partial) partial_destroy ;;
  full)    full_destroy ;;
esac

echo
echo "Teardown finished (mode=${MODE})."
