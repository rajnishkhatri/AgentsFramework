# GoalJudge Registry Batch

The flagship full-stack (T3) workflow: drive every GoalJudge registry prompt
through the real chat UI on Cloud Run, capture each result, and reconcile against
the backend. This is the worked example of everything in the companion skill.

- **Spec:** `frontend/e2e/full-stack/goaljudge-batch.spec.ts`
- **Plan:** `docs/plans/goaljudge_gcp_playwright_batch.plan.md`
- **Cases:** `frontend/e2e/fixtures/goaljudge_registry.ts` (+ `.json`)
- **Output:** `cache/goaljudge_eval/ui_batch.jsonl` (append-only) + screenshots

## Prerequisites

```bash
cd frontend
export BASE_URL=https://agent-frontend-w65nrxwkiq-uc.a.run.app
export E2E_AUTHENTICATED=1
export E2E_USER_EMAIL=...        # repo-root .env / secret store
export E2E_USER_PASSWORD=...     # (or E2E_USER_OTP=...)
```

## Run

```bash
# Smoke one case first (cheap drift check):
GJ_CASE_FILTER=GJ-010 pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts

# Full subset GJ-001…GJ-022 (includes B-variants GJ-001B, GJ-003B):
pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts

# Cap size while iterating:
GOALJUDGE_BATCH_LIMIT=5 pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts
```

Env knobs (from the spec header): `GJ_CASE_FILTER` (single case),
`GOALJUDGE_BATCH_LIMIT` (cap), `GOALJUDGE_BATCH_JSONL` (output path override),
`GOALJUDGE_BATCH_SCREENSHOT_DIR` (screenshot dir override). `test.setTimeout` is
180s per case.

## How the cases are selected

`filterCases({ caseFilter, limit })` → `walkthroughCases()` returns the GJ-001…
GJ-022 subset, numeric-sorted, **including** B-variants (GJ-001B, GJ-003B) — so
the "22-case" subset is 22 *distinct ids* but **not** a clean GJ-001..GJ-022
sequence. Regenerate the JSON from the Python registry when cases change:

```bash
python scripts/export_goaljudge_registry_json.py
```

Each case row has: `id`, `prompt`, `target_code`, `target_axes`
(`goal_met`/`graceful_failure`/`partial_fraction`), `stratum`, `domain`,
`expected_feasibility`, `provenance`, `trace_id`, `session_id`.

## The thread bridge (the crux)

`installGoalJudgeThreadBridge(page, caseRow)` intercepts `**/api/run/stream` and
rewrites the **outbound body** so `thread_id = gj:{case_id}:{trace_id}`. The
backend parses that, resolves it to the registry `session_id`, and joins the UI
run to the case.

**FE-AP-7 (server owns provenance):** the bridge `throw`s if the request body
contains a client-generated `trace_id`. The `trace_id` is derived deterministically
as `uuid5(NAMESPACE_DNS, case_id).hex` and is **not** sent from the client — the
server generates the real trace id. Never "fix" a test by injecting `trace_id`
into the body; encode the join key in `thread_id` (which the server tolerates) and
let the server own the trace.

## What each row captures

`appendCapture(...)` writes one JSONL row per case to
`cache/goaljudge_eval/ui_batch.jsonl`:
`case_id, trace_id, session_id, target_code, target_axes, prompt, thread_title,
response_text (sliced to 4000), tool_card_count, screenshot_path, finished_at,
base_url`. A full-page screenshot per case is also attached to the Playwright
report and saved under the screenshot dir.

The capture's success assertion is intentionally minimal —
`expect(responseText.length).toBeGreaterThan(0)` — because the *analysis* (did it
render a real answer vs. only a status feed) happens afterward over the JSONL, not
inline. See gotcha #5 and #4 for why.

## Verification

The DOM capture is one signal; the backend is the other. They can disagree —
observed: the backend completed **all** cases (bridge line logged + Langfuse trace
for each) while only ~half surfaced a rendered answer in the live region. That gap
is a **frontend stream→DOM** issue, not a backend or harness defect.

**1. Reconcile the capture** (status-prefix strip + last-write dedupe both matter):
```bash
python ~/.claude/skills/playwright-agentic-e2e/scripts/verify_run.py \
  --jsonl cache/goaljudge_eval/ui_batch.jsonl \
  --status-prefix "Using tools:" --id-namespace dns --dedupe --expect-cases 22
```
Expect: 22 distinct cases, `trace_id == uuid5(dns, case_id)` PASS, and an
M/22-rendered split. (The JSONL is append-only; without `--dedupe` re-runs inflate
the row count — it's held 27 rows for 22 distinct cases.)

**2. Cloud Logging** — bridge/saturation line is in `jsonPayload.message`:
```bash
gcloud logging read \
  'resource.type="cloud_run_revision"
   AND resource.labels.service_name="agent-backend-combined"
   AND jsonPayload.message=~"goaljudge_saturation"' \
  --project=agent-prod-gcp-dev --freshness=1h \
  --format='value(timestamp, jsonPayload.message)' --limit=200
```
Dedupe by run id, then compare distinct count to your rows.

**3. Langfuse** — count traces for the run window:
```python
lf.api.trace.list(user_id="synthetic-saturation-user", limit=200)
```
The captured `trace_id`s should resolve to real traces.

## Known limitation (G3)

GoalJudge verdict axes (`goal_met` / `graceful_failure` / `partial_fraction`) are
**not** emitted as queryable structured `jsonPayload` fields on GCP. You can verify
the **integrity** layer — the right set of runs/traces exists, ids match — but the
semantic axes read N/A on that platform. Verify what's queryable; note what isn't.

## Shadow posture (read, don't change)

`gs://agent-prod-gcp-dev-agent-facts/ops/goal_judge_config.json`:
`goal_judge_enabled=true`, `goal_judge_downgrade_enabled=false` (observe, never
downgrade). **Do not overwrite** this object.
