#!/usr/bin/env bash
# scripts/bootstrap_gcp_env.sh — Day-0 preflight for GCP Tier A live deploy.
#
# Validates local toolchain, gcloud auth, billing, required APIs, and (when
# present) OpenTofu outputs. Source once per shell before Day-1 apply steps:
#
#   source ./scripts/bootstrap_gcp_env.sh
#
# Or run directly for a pass/fail gate (exits 1 on hard failures):
#
#   ./scripts/bootstrap_gcp_env.sh
#
# See docs/recipes/gcp/LIVE_DEPLOYMENT.md §0.5.

set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TFVARS="${REPO_ROOT}/infra/gcp/terraform.tfvars"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}PASS${NC}: $*"; }
fail() { echo -e "  ${RED}FAIL${NC}: $*"; HARD_FAIL=1; }
warn() { echo -e "  ${YELLOW}WARN${NC}: $*"; }

HARD_FAIL=0

_tfvars_value() {
  local key="$1"
  local default="${2:-}"
  if [[ ! -f "${TFVARS}" ]]; then
    echo "${default}"
    return
  fi
  grep -E "^[[:space:]]*${key}[[:space:]]*=" "${TFVARS}" 2>/dev/null \
    | head -1 \
    | sed -E 's/^[^=]*=[[:space:]]*"([^"]*)".*/\1/' \
    || echo "${default}"
}

_bootstrap_gcp_env() {
  echo "=== GCP Tier A environment bootstrap ==="
  echo "Repo: ${REPO_ROOT}"
  echo

  # ── Tool checks (hard fail) ────────────────────────────────────────────────

  for cmd in gcloud tofu docker python3 pytest conftest terraform-compliance; do
    if command -v "${cmd}" >/dev/null 2>&1; then
      pass "${cmd} on PATH"
    else
      fail "${cmd} not found — install dev toolchain (pip install -e \".[dev]\")"
    fi
  done

  if command -v tofu >/dev/null 2>&1; then
    tofu_ver="$(tofu version 2>/dev/null | head -1 | sed -E 's/.* v//')"
    tofu_major="${tofu_ver%%.*}"
    tofu_minor="${tofu_ver#*.}"; tofu_minor="${tofu_minor%%.*}"
    if [[ "${tofu_major}" -lt 1 ]] || { [[ "${tofu_major}" -eq 1 ]] && [[ "${tofu_minor}" -lt 6 ]]; }; then
      fail "tofu ${tofu_ver} — need >= 1.6 (brew install opentofu)"
    else
      pass "tofu version ${tofu_ver} (>= 1.6)"
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      pass "python3 $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') (>= 3.10)"
    else
      fail "python3 < 3.10 — upgrade Python"
    fi
  fi

  # ── terraform.tfvars + exports ─────────────────────────────────────────────

  if [[ ! -f "${TFVARS}" ]]; then
    fail "infra/gcp/terraform.tfvars missing — cp terraform.tfvars.example and fill (HUMAN_SETUP.md §4)"
  else
    pass "terraform.tfvars exists"
    export PROJECT="$(_tfvars_value gcp_project_id)"
    export REGION="$(_tfvars_value gcp_region us-central1)"
    if [[ -z "${PROJECT}" ]]; then
      fail "gcp_project_id not set in terraform.tfvars"
    else
      pass "PROJECT=${PROJECT}"
      pass "REGION=${REGION}"
    fi
  fi

  # ── Account state (hard fail) ──────────────────────────────────────────────

  if gcloud auth list --format='value(account)' 2>/dev/null | grep -q '@'; then
    pass "gcloud user account logged in"
  else
    fail "no gcloud user account — run: gcloud auth login"
  fi

  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    pass "Application Default Credentials (ADC) valid"
  else
    fail "ADC missing — run: gcloud auth application-default login"
  fi

  if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
    if [[ -r "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
      pass "GOOGLE_APPLICATION_CREDENTIALS readable (${GOOGLE_APPLICATION_CREDENTIALS})"
    else
      warn "GOOGLE_APPLICATION_CREDENTIALS set but file not readable — tofu may still work via ADC"
    fi
  else
    warn "GOOGLE_APPLICATION_CREDENTIALS unset — using ADC from gcloud auth application-default login"
  fi

  if [[ -n "${PROJECT:-}" ]]; then
    active_project="$(gcloud config get-value project 2>/dev/null || true)"
    if [[ "${active_project}" != "${PROJECT}" ]]; then
      warn "gcloud active project '${active_project}' != PROJECT '${PROJECT}' — setting"
      gcloud config set project "${PROJECT}" >/dev/null 2>&1 || fail "cannot set gcloud project to ${PROJECT}"
    else
      pass "gcloud active project matches PROJECT"
    fi
  fi

  # ── Billing + APIs (hard fail) ─────────────────────────────────────────────

  if [[ -n "${PROJECT:-}" ]]; then
    billing_enabled="$(gcloud billing projects describe "${PROJECT}" --format='value(billingEnabled)' 2>/dev/null || echo "False")"
    if [[ "${billing_enabled}" == "True" ]]; then
      pass "billing enabled on ${PROJECT}"
    else
      fail "billing not enabled — link billing (HUMAN_SETUP.md §1): gcloud billing projects link ${PROJECT} --billing-account=ACCOUNT_ID"
    fi

    required_apis=(
      cloudresourcemanager.googleapis.com
      iam.googleapis.com
      artifactregistry.googleapis.com
      run.googleapis.com
      sqladmin.googleapis.com
      secretmanager.googleapis.com
      storage.googleapis.com
      monitoring.googleapis.com
      cloudbilling.googleapis.com
      cloudscheduler.googleapis.com
      serviceusage.googleapis.com
    )

    for api in "${required_apis[@]}"; do
      if gcloud services list --enabled --project="${PROJECT}" --filter="config.name=${api}" --format='value(config.name)' 2>/dev/null | grep -q "${api}"; then
        pass "API enabled: ${api}"
      else
        warn "API not enabled: ${api} — enabling"
        if gcloud services enable "${api}" --project="${PROJECT}" >/dev/null 2>&1; then
          pass "API enabled: ${api}"
        else
          fail "could not enable ${api} — check IAM (roles/serviceusage.serviceUsageAdmin)"
        fi
      fi
    done
  fi

  # ── Quota check (warn-only) ────────────────────────────────────────────────

  if [[ -n "${PROJECT:-}" ]]; then
    echo
    echo "Quota snapshot (warn-only):"
    gcloud compute project-info describe --project="${PROJECT}" \
      --format='table(quotas.metric, quotas.limit, quotas.usage)' 2>/dev/null \
      | grep -E 'CLOUD_SQL|CPUS_ALL_REGIONS' \
      || warn "could not read CLOUD_SQL / CPUS_ALL_REGIONS quotas"
    warn "Cloud Run → Cloud SQL: max 100 connections per Cloud Run instance (plan capacity accordingly)"
  fi

  # ── Tofu outputs (warn-only — empty before first deploy) ───────────────────

  if command -v tofu >/dev/null 2>&1 && [[ -d "${REPO_ROOT}/infra/gcp" ]]; then
    backend_url="$(tofu -chdir="${REPO_ROOT}/infra/gcp" output -raw backend_url 2>/dev/null || true)"
    frontend_url="$(tofu -chdir="${REPO_ROOT}/infra/gcp" output -raw frontend_url 2>/dev/null || true)"
    if [[ -n "${backend_url}" ]]; then
      export BACKEND_URL="${backend_url}"
      pass "BACKEND_URL=${BACKEND_URL}"
    else
      warn "BACKEND_URL not in state yet (expected before Recipe 4 apply)"
    fi
    if [[ -n "${frontend_url}" ]]; then
      export FRONTEND_URL="${frontend_url}"
      pass "FRONTEND_URL=${FRONTEND_URL}"
    else
      warn "FRONTEND_URL not in state yet (expected before Recipe 5 apply)"
    fi
  fi

  # ── Summary ────────────────────────────────────────────────────────────────

  echo
  if [[ "${HARD_FAIL}" -eq 1 ]]; then
    echo -e "${RED}Preflight FAILED${NC} — fix red lines above before Day-1 deploy."
    return 1
  fi
  echo -e "${GREEN}Preflight PASSED${NC} — proceed to Day-1 in LIVE_DEPLOYMENT.md."
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _bootstrap_gcp_env
  exit $?
else
  _bootstrap_gcp_env || return 1 2>/dev/null || exit 1
fi
