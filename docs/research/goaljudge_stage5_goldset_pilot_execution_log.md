# GoalJudge Stage 5 Goldset Pilot — T3 Batch Execution Log (2026-06-09)

> **Status:** Complete — 43/43 Playwright pass, 43/43 verify_run, double-label α PASS (0.8846)

## Pre-flight

| Check | Result |
|---|---|
| `E2E_AUTHENTICATED=1` | OK |
| `E2E_USER_EMAIL` / password | OK (repo-root `.env`) |
| Backend `/health` `goal_judge.enabled` | OK (`gcs:ops/goal_judge_config.json`) |
| Playwright `storageState` | OK |
| `GOALJUDGE_BATCH_MODE=pilot` | OK (43-case harness) |

## Harness changes (Phase 0)

- `PILOT_REGISTRY_IDS` + `pilotRegistryCases()` in [`frontend/e2e/fixtures/goaljudge_registry.ts`](../../frontend/e2e/fixtures/goaljudge_registry.ts)
- `GOALJUDGE_BATCH_MODE=pilot|walkthrough` (default walkthrough, backward compatible)
- [`scripts/build_goaljudge_stage5_pilot_sheet.py`](../../scripts/build_goaljudge_stage5_pilot_sheet.py) — `GOALJUDGE_BATCH_JSONL` env; merges scaffold rows from batch
- [`scripts/export_goaljudge_corpus.py`](../../scripts/export_goaljudge_corpus.py) — `--trace-ids-from-jsonl`

## Smoke — GJ-010

| Check | Result |
|---|---|
| Playwright | 1 passed (~56s) |
| JSONL `outcome=pass` + screenshot | OK |

## Full batch — 43 cases

**Run tag:** `gcp_goldset_pilot_2026-06-09`
**Wall clock:** 5.2 min (43 passed, 0 failed)

| Artifact | Path |
|---|---|
| JSONL | `cache/goaljudge_eval/ui_batch_gcp_goldset_pilot_2026-06-09.jsonl` |
| Screenshots | `cache/goaljudge_eval/ui_batch_screenshots_gcp_goldset_pilot_2026-06-09/` |
| Corpus | `cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl` |
| Playwright report | `frontend/playwright-report/` |

### Playwright outcomes

- **43/43 pass** — all rows `outcome=pass`
- **0 `_FAILED` screenshots**

### `verify_run.py`

```
rows in file:                  43
distinct case ids:             43
rendered a real answer:        33/43
status-feed only (UI gap):     10/43
  status-only ids: GJ-001, GJ-003B, GJ-007, GJ-011, GJ-014, GJ-015, GJ-023, GJ-031, GJ-045, GJ-048
trace_id == uuid5(dns, case_id): PASS
```

### Langfuse export

```bash
.venv/bin/python scripts/export_goaljudge_corpus.py \
  --trace-ids-from-jsonl cache/goaljudge_eval/ui_batch_gcp_goldset_pilot_2026-06-09.jsonl \
  --out cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl
```

Initial export: 41/43 rows (GJ-051, GJ-052 traces indexed later). Trace pins captured for all 43 via `fetch_trace_observations`.

## Post-batch labeling

- Pilot sheet rebuilt: `python scripts/build_goaljudge_stage5_pilot_sheet.py` with `GOALJUDGE_BATCH_JSONL`
- Annotator 1 grades: `python scripts/apply_goaljudge_stage5_annotator1_grades.py`
- Annotator 2 grades: `python scripts/apply_goaljudge_stage5_annotator2_grades.py`
- α: `python scripts/compute_goaljudge_stage5_alpha.py docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv` → **0.8846 PASS**
- Reports: [`annotator1`](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator1_results.md) · [`annotator2`](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_annotator2_results.md) · [`pilot_results`](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md)

## Commands (reference)

```bash
export RUN_TAG="gcp_goldset_pilot_2026-06-09"
export BASE_URL="https://agent-frontend-w65nrxwkiq-uc.a.run.app"
export E2E_AUTHENTICATED=1
export GOALJUDGE_BATCH_MODE=pilot
export GOALJUDGE_BATCH_JSONL="/absolute/path/cache/goaljudge_eval/ui_batch_${RUN_TAG}.jsonl"
export GOALJUDGE_BATCH_SCREENSHOT_DIR="/absolute/path/cache/goaljudge_eval/ui_batch_screenshots_${RUN_TAG}"

bash scripts/preflight_goaljudge_gcp_batch.sh
cd frontend
GJ_CASE_FILTER=GJ-010 CI=1 pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts --project=chromium-desktop
unset GJ_CASE_FILTER
CI=1 pnpm exec playwright test e2e/full-stack/goaljudge-batch.spec.ts --project=chromium-desktop
```
