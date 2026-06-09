# GoalJudge GCP Batch — Execution Log (2026-06-09)

> **Status:** Blocked on prod deploy (G4) + WorkOS E2E credentials

## Pre-flight (`scripts/preflight_goaljudge_gcp_batch.sh`)

| Check | Result |
|---|---|
| `E2E_AUTHENTICATED=1` | FAIL (unset) |
| `E2E_USER_EMAIL` / password | FAIL (unset) |
| Backend `/health` `goal_judge.enabled` | FAIL (`false`, `source=env`) |
| Playwright `storageState` | OK (`frontend/e2e/.auth/state.json`) |

Prod backend probe (2026-06-09):

```json
{"goal_judge":{"enabled":false,"downgrade_enabled":false,"source":"env"}}
```

## Blockers before smoke GJ-010

1. Deploy backend with this branch (GCS reader + `GOAL_JUDGE_ENABLED=true` + E1 sink)
2. Confirm `gs://…/ops/goal_judge_config.json` Posture A on GCS
3. Set `E2E_AUTHENTICATED=1`, `E2E_USER_EMAIL`, `E2E_USER_PASSWORD`
4. Verify single-case E1 `eval.goal_judge` observation on Langfuse

## Commands (when unblocked)

```bash
bash scripts/preflight_goaljudge_gcp_batch.sh

cd frontend
GJ_CASE_FILTER=GJ-010 E2E_AUTHENTICATED=1 \
  BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app \
  pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts

# Full corpus (22 cases)
E2E_AUTHENTICATED=1 \
  BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app \
  pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts
```
