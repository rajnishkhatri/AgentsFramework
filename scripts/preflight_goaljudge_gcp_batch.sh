#!/usr/bin/env bash
# Pre-flight checks for GoalJudge GCP Playwright batch (G1/G2/G4).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_URL="${BASE_URL:-https://agent-frontend-w65nrxwkiq-uc.a.run.app}"
BACKEND_URL="${BACKEND_URL:-https://agent-backend-combined-w65nrxwkiq-uc.a.run.app}"

echo "=== GoalJudge GCP batch preflight ==="
echo "frontend: $FRONTEND_URL"
echo "backend:  $BACKEND_URL"

fail=0

check() {
  if eval "$2"; then
    echo "OK  $1"
  else
    echo "FAIL $1"
    fail=1
  fi
}

check "E2E_AUTHENTICATED" 'test "${E2E_AUTHENTICATED:-0}" = "1"'
check "E2E_USER_EMAIL set" 'test -n "${E2E_USER_EMAIL:-}"'
check "E2E_USER_PASSWORD set" 'test -n "${E2E_USER_PASSWORD:-}"'

if curl -sf "$BACKEND_URL/health" | python3 -c "
import json, sys
d = json.load(sys.stdin)
gj = d.get('goal_judge') or {}
assert gj.get('enabled') is True, f'goal_judge not enabled: {gj}'
src = str(gj.get('source', ''))
assert 'gcs' in src or src.startswith('file:'), f'unexpected source: {src}'
print(f\"goal_judge enabled source={src}\")
"; then
  echo "OK  backend /health goal_judge posture"
else
  echo "FAIL backend /health goal_judge posture (deploy PR3 + GCS seed required)"
  fail=1
fi

if test -f "$ROOT/frontend/e2e/.auth/state.json"; then
  echo "OK  playwright storageState present"
else
  echo "WARN playwright storageState missing — run auth setup first"
fi

echo ""
if test "$fail" -eq 0; then
  echo "Preflight passed. Run smoke:"
  echo "  cd frontend && GJ_CASE_FILTER=GJ-010 E2E_AUTHENTICATED=1 BASE_URL=$FRONTEND_URL pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts"
else
  echo "Preflight failed — fix blockers before batch (see docs/plans/goaljudge_gcp_playwright_execution.plan.md)"
  exit 1
fi
