#!/usr/bin/env bash
# scripts/smoke_gcp.sh — Recipe 7 end-to-end smoke test for GCP Tier A deploy.
#
# Checks:
#   1. Backend /healthz (no auth)
#   2. Optional frontend root (HTTP 200)
#   3. Authenticated POST /run/stream SSE chunks within 5 seconds (when BEARER_TOKEN set)
#
# Usage:
#   export BACKEND_URL="$(tofu -chdir=infra/gcp output -raw backend_url)"
#   export FRONTEND_URL="$(tofu -chdir=infra/gcp output -raw frontend_url)"   # optional
#   export BEARER_TOKEN="<WorkOS JWT from signed-in session>"                 # optional
#   ./scripts/smoke_gcp.sh
#
# For full end-to-end log analysis (auth, auto-provision, stream_ended), see
# docs/recipes/gcp/LOG_PIPELINE_GUIDE.md
#
# Exit codes: 0 = all executed checks passed, 1 = failure.

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-}"
FRONTEND_URL="${FRONTEND_URL:-}"
BEARER_TOKEN="${BEARER_TOKEN:-}"
SSE_TIMEOUT_SECONDS="${SSE_TIMEOUT_SECONDS:-5}"
THREAD_ID="${THREAD_ID:-smoke-$(date +%s)}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC}: $*"; }
fail() { echo -e "${RED}FAIL${NC}: $*"; exit 1; }
warn() { echo -e "${YELLOW}SKIP${NC}: $*"; }

if [[ -z "${BACKEND_URL}" ]]; then
  if command -v tofu >/dev/null 2>&1; then
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    BACKEND_URL="$(tofu -chdir="${REPO_ROOT}/infra/gcp" output -raw backend_url 2>/dev/null || true)"
  fi
fi

if [[ -z "${BACKEND_URL}" ]]; then
  fail "BACKEND_URL is required (export or run from repo with tofu outputs)"
fi

BACKEND_URL="${BACKEND_URL%/}"

echo "=== GCP Tier A smoke test ==="
echo "Backend:  ${BACKEND_URL}"
[[ -n "${FRONTEND_URL}" ]] && echo "Frontend: ${FRONTEND_URL}"
echo

# ── 1. Backend health ────────────────────────────────────────────────────────

health_body="$(curl -sf "${BACKEND_URL}/healthz" || curl -sf "${BACKEND_URL}/health")" || fail "/healthz request failed"
if ! echo "${health_body}" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  fail "/healthz did not return status=ok: ${health_body}"
fi
pass "/healthz returned ok"

# ── 2. Frontend root (optional) ──────────────────────────────────────────────

if [[ -n "${FRONTEND_URL}" ]]; then
  FRONTEND_URL="${FRONTEND_URL%/}"
  status_code="$(curl -s -o /dev/null -w '%{http_code}' "${FRONTEND_URL}/")"
  if [[ "${status_code}" != "200" && "${status_code}" != "307" && "${status_code}" != "308" ]]; then
    fail "frontend root returned HTTP ${status_code}, expected 200/307/308"
  fi
  pass "frontend root returned HTTP ${status_code}"
else
  warn "FRONTEND_URL unset — skipping frontend check"
fi

# ── 3. SSE stream (requires WorkOS Bearer token) ─────────────────────────────

if [[ -z "${BEARER_TOKEN}" ]]; then
  warn "BEARER_TOKEN unset — skipping /run/stream SSE check"
  warn "Obtain a token from a signed-in browser session (Recipe 5) and re-run"
  echo
  echo "Smoke complete (health checks only)."
  exit 0
fi

payload=$(cat <<EOF
{"thread_id":"${THREAD_ID}","input":{"messages":[{"role":"user","content":"Reply with exactly: smoke ok"}]}}
EOF
)

tmp_sse="$(mktemp)"
trap 'rm -f "${tmp_sse}"' EXIT

set +e
curl -sS -N \
  --max-time "${SSE_TIMEOUT_SECONDS}" \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "${payload}" \
  "${BACKEND_URL}/run/stream" > "${tmp_sse}" 2>/dev/null
curl_status=$?
set -e

if [[ ! -s "${tmp_sse}" ]]; then
  fail "/run/stream returned no data within ${SSE_TIMEOUT_SECONDS}s (curl exit ${curl_status})"
fi

if grep -q 'event: RUN_STARTED' "${tmp_sse}" || grep -q 'event: TEXT_MESSAGE' "${tmp_sse}"; then
  pass "/run/stream emitted SSE events within ${SSE_TIMEOUT_SECONDS}s"
elif grep -q '\[DONE\]' "${tmp_sse}"; then
  pass "/run/stream completed with [DONE] sentinel within ${SSE_TIMEOUT_SECONDS}s"
else
  fail "/run/stream response missing expected SSE markers: $(head -c 500 "${tmp_sse}")"
fi

# ── 4. Auth chain log check (warn-only) ──────────────────────────────────────

PROJECT="${GCP_PROJECT:-}"
if [[ -z "${PROJECT}" ]] && command -v tofu >/dev/null 2>&1; then
  PROJECT="$(tofu -chdir="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/infra/gcp" output -raw gcp_project_id 2>/dev/null || true)"
fi

if [[ -n "${PROJECT}" ]] && command -v gcloud >/dev/null 2>&1; then
  auth_rejects="$(gcloud logging read \
    'resource.labels.service_name="agent-backend-combined" AND textPayload:"auth_reject"' \
    --project="${PROJECT}" --limit=5 --format='value(textPayload)' 2>/dev/null || true)"
  if [[ -n "${auth_rejects}" ]]; then
    echo -e "${YELLOW}WARN${NC}: Recent auth_reject entries in backend logs:"
    echo "${auth_rejects}" | head -5
  else
    pass "No recent auth_reject entries in backend logs"
  fi
else
  warn "GCP_PROJECT unset or gcloud unavailable — skipping auth log check"
fi

echo
echo "Smoke complete (all checks passed)."
