---
type: plan
title: 'GoalJudge Session Fixes'
description: 'Overview: Fix issues surfaced during GoalJudge validation (GCP walkthrough Steps 2–3 and local Posture A/B runs).'
tags: [plan]
---

# GoalJudge Session Fixes

**Overview:** Fix issues surfaced during GoalJudge validation (GCP walkthrough Steps 2–3 and local Posture A/B runs). Scope covers: (1) GCP walkthrough/Recipe 15 alignment, startup config cache-warm, and `/healthz` edge diagnosis (S1–S6); (2) local-run code fixes to formalize with tests (S7–S9); (3) judge-quality findings from Phase 2 open coding, documented only and deferred to Stage 3/4 rubric work (J1–J3); (4) export-script formalization (E1).

**Companion artifacts (this session):**
- [docs/walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md) — Posture A/B run log (signed off locally)
- [docs/research/goaljudge_phase2_open_coding.md](../research/goaljudge_phase2_open_coding.md) — Phase 2 open coding report
- [docs/research/goaljudge_phase2b_open_coding.md](../research/goaljudge_phase2b_open_coding.md) — Phase 2b open coding and saturation report
- [docs/research/goaljudge_synthetic_dimension_space.md](../research/goaljudge_synthetic_dimension_space.md) — D1-D5 dimension spec, merged taxonomy, and codebook
- [docs/walk-through/03_goaljudge_synthetic_saturation_walkthrough.md](../walk-through/03_goaljudge_synthetic_saturation_walkthrough.md) — Step-by-step synthetic batch execution walkthrough
- [docs/plans/goaljudge_synthetic_saturation_run.plan.md](goaljudge_synthetic_saturation_run.plan.md) — End-to-end execution execution steps and validation sequence
- [scripts/export_goaljudge_corpus.py](../../scripts/export_goaljudge_corpus.py) — programmatic corpus export (untracked until committed)

## To-dos

### GCP walkthrough (original)

- [ ] **walkthrough-doc** — Update `docs/walk-through/02_...md`: S1 use `/health` for external checks (+note), S3 promote Step 0a to a blocking gate, S2 correct the cold posture expectation, S4 switch P1/P4 paths to `/workspace` with a sandbox callout, S5 rework P2 + add `web_search` observation guidance, S6 add langfuse/venv prerequisite note.
- [ ] **recipe15-doc** — Update `docs/recipes/15_goaljudge_runtime_config_toggle.md`: document `/health` as external alias and the new startup cache-warm while reaffirming the probe-stays-cache-only invariant.
- [ ] **warm-cache-code** — In `middleware/app_prod.py` lifespan, warm `goal_judge_reader.get()` once (non-fatal try/except) so `/health` reflects GCS at boot; keep `health_posture()` cache-only.
- [ ] **warm-cache-tests** — Add/extend tests (`tests/middleware/test_app_prod.py`, `tests/services/test_goal_judge_runtime_config.py`) for startup warm reflecting GCS and GCS-error-at-startup being swallowed; run with `-p no:logfire`.
- [ ] **healthz-edge-investigation** — Live-diagnose the external `/healthz` 404 (`curl -v` header/body comparison + Cloud Run request logs); record findings and apply the matching contingency (doc-only resolution vs app route fix).

### Local validation (this session)

- [ ] **cli-traceid-format** — Formalize OTel/Langfuse 32-hex trace-id fix in `cli.py` + regression test (S7).
- [ ] **cli-recursion-limit** — Formalize `recursion_limit: 100` in `cli.py` + short note/guard (S8).
- [ ] **evals-json-formatter** — Formalize `logging.json` structured-JSON formatter for `logs/evals.log` (S9).
- [ ] **export-script-formalize** — Track `scripts/export_goaljudge_corpus.py`, document outbox-relay prerequisite, investigate 9-vs-10 row count (E1).
- [ ] **judge-quality-findings** — Document J1/J2/J3 in plan + cross-links; **no code change here** (deferred to Stage 3/4).

---

## Issue inventory

### GCP walkthrough (S1–S6)

Each is grounded in observed traces/health output and code.

- **S1 - External `/healthz` 404 (edge):** The container serves `/healthz` (Cloud Run startup+liveness probes target `/healthz` and the service is healthy: [infra/gcp/cloud-run-backend.tf](../../infra/gcp/cloud-run-backend.tf) lines 66-80) and `/health` is an exact alias ([middleware/app_prod.py](../../middleware/app_prod.py) lines 202-212). Yet external `curl .../healthz` returns a Google-branded 404 while `/health` returns 200. No external LB/Cloud Armor exists in `infra/gcp/`, so the 404 is a Google-edge anomaly on the direct `run.app` host.
- **S2 - Cold posture echo shows `source:"env"`:** `health_posture()` is cache-only by design ([services/goal_judge_runtime_config.py](../../services/goal_judge_runtime_config.py) line 181). On a cold instance the composition passes explicit `env_enabled=False` ([middleware/composition.py](../../middleware/composition.py) lines 575-581), so `/health` reports `source:"env"`/dark and disagrees with seeded GCS until a completed task warms the per-instance cache via `get()`.
- **S3 - Step 0a GCS seed missing/skippable:** The live bucket had no `ops/goal_judge_config.json`; the walkthrough lets Step 2 run before seeding.
- **S4 - `/tmp` paths rejected on GCP:** `file_io` is sandboxed to `WORKSPACE_DIR=/workspace` ([services/tools/file_io.py](../../services/tools/file_io.py) lines 20-23). P1/P4 prompts use `/tmp/...` and fail (`outcome=failed`).
- **S5 - P2 "impossible phrase" isn't impossible:** Prod runs real SearXNG (sidecar, `WEB_SEARCH_PROVIDER=searxng`), which returned a genuine GitHub hit for `xyzq123impossiblephrase987`, so `goal_met=True` is arguably correct and the intended `goal_met=False` retrieval-failure stratum was not exercised.
- **S6 - `langfuse` SDK env:** The Step 6 export assumes `langfuse` importable; it was missing from the default `python3` (only anaconda python had it).

### Local validation (S7–S9) — applied, uncommitted

- **S7 - CLI trace-id format incompatible with OTel/Langfuse:** `cli.py` previously emitted `wf-`/`task-` prefixed ids. The Langfuse SDK (OpenTelemetry under the hood) requires **32 lowercase hex characters** (W3C trace-id). Passing prefixed strings caused `ValueError: invalid literal for int() with base 16` and DLQ diversion (`.langfuse_failures.jsonl`). **Fix applied:** [cli.py](../../cli.py) lines 120–121 — `workflow_id = uuid.uuid4().hex; task_id = workflow_id`. Posture B traces published cleanly after this change.
- **S8 - GraphRecursionError on multi-step tasks:** LangGraph default `recursion_limit` (25) tripped P4 locally. **Fix applied:** `recursion_limit: 100` at both `graph.ainvoke` config sites in [cli.py](../../cli.py).
- **S9 - `logs/evals.log` unstructured (local G3):** The `console`/`evals` handlers used a printf formatter; `eval_capture` emits `logger.info("AI Response", extra=eval_record)` so `extra=` fields were dropped. **Fix applied:** [logging.json](../../logging.json) — `"json"` formatter uses `pythonjsonlogger.jsonlogger.JsonFormatter`. Local `logs/evals.log` is now line-delimited JSON with full GoalJudge axes. GCP Cloud Run remains unstructured until the compatibility-plan G3/T3/T4 follow-on ([goaljudge_gcp_compatibility.plan.md](goaljudge_gcp_compatibility.plan.md)).

### Judge quality (J1–J3) — findings only, deferred to Stage 3/4

Source: [goaljudge_phase2_open_coding.md](../research/goaljudge_phase2_open_coding.md) §4. Overall `goal_met` alignment with human intuition was **high** on P1–P5; these are rubric/prompt-quality gaps, not gate bugs.

- **J1 (root cause) - Generic, non-task-derived `success_conditions`:** [components/plan_builder.py](../../components/plan_builder.py) lines 52–55 hardcode two boilerplate conditions for every task:
  - `"All planned branches are addressed in the final synthesis."`
  - `"Final answer is concise, actionable, and internally consistent."`
  The judge never receives task-specific criteria (e.g. "report Mars population", "read back `capital` value"). This forces the judge to invent ad hoc criteria (P4) and drives J2/J3. **Proposed fix (deferred):** derive `success_conditions` from task input / plan branches (LLM-extracted or per-branch atomic conditions).
- **J2 - Criterion conflation (P4, `task-eeaa522d`):** Judge marked *"All planned branches are addressed in the final synthesis"* `met: true` while a sibling criterion (*Mars population*) was `met: false` — a logical contradiction. **Proposed fix (deferred):** judge-prompt rule enforcing independent, non-overlapping criteria; analytic rubric spec in Stage 4 ([goaljudge_evaluation_pipeline_open_axial_coding_rubric.md](../research/goaljudge_evaluation_pipeline_open_axial_coding_rubric.md) Stage 4).
- **J3 - Outcome bias on graceful failures (P2, P3):** Judge marked *"Final answer is concise, actionable, and internally consistent"* `false` because the goal was unmet, penalizing honest impossibility reports (`graceful_failure: true` was still correct at the top level). **Proposed fix (deferred):** decouple answer-quality criteria from goal completion; evaluate actionability relative to task feasibility.

### Export (E1)

- **E1 - Ad hoc export + row count:** `scripts/export_goaljudge_corpus.py` created from the walkthrough Step 6 template (currently untracked). Local export wrote **9 rows** to `cache/goaljudge_eval/run.jsonl` (walkthrough expects 10 across both postures). Export depends on outbox relay (`python -m middleware.sidecars`) publishing traces before Langfuse fetch. Investigate missing row (likely one Posture A trace not relayed or outside the time window).

---

## Workstream A - Walkthrough doc fixes ([docs/walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md](../walk-through/02_goaljudge_ui_langfuse_validation_walkthrough.md))

- S1: Change external posture checks from `$BACKEND_URL/healthz` to `$BACKEND_URL/health` (exact alias), with a one-line note that `/healthz` is the internal probe path and may 404 at the edge; record the open edge investigation (Workstream D).
- S3: Promote Step 0a to a hard gate at the top of Step 2 (seed `ops/goal_judge_config.json` first; verify with `gsutil cat`); add the seed to the Step 0 checklist as blocking.
- S2: Replace the Step 2 checklist line that implies `/healthz source` is `gcs:...` immediately after seed. Document that a cold instance shows `source:"env"`; after Workstream C it reflects `gcs:...` at boot, and a warm-up run still guarantees it.
- S4: Change all P-series file paths from `/tmp/...` to `/workspace/...` (P1, P4) and add a "GCP file_io is sandboxed to `/workspace`" callout near the prompt matrix.
- S5: Rework P2 to tie the verdict to an objectively checkable missing fact AND add reviewer guidance to inspect the `web_search`/`tool.called` observation, distinguishing "no useful result -> goal_met=False (target stratum)" from "real hit correctly used -> goal_met=True (re-roll on a fresh thread)". Note that real SearXNG can return noise for nonsense strings.
- S6: Add a Step 6 prerequisite note: run from a venv with `pip install -e ".[dev]"` (or pin the interpreter that has `langfuse>=4`).

## Workstream B - Recipe 15 doc fix ([docs/recipes/15_goaljudge_runtime_config_toggle.md](../recipes/15_goaljudge_runtime_config_toggle.md))

- Document `/health` as the external alias of `/healthz`.
- Document the new startup cache-warm (Workstream C) and reaffirm the invariant that the probe path itself stays cache-only (no GCS I/O on the probe).

## Workstream C - Code: warm GoalJudge config cache at startup ([middleware/app_prod.py](../../middleware/app_prod.py))

- In the `lifespan` startup (after `build_components`, where `goal_judge_reader` is created), call `goal_judge_reader.get()` once inside a non-fatal `try/except` so the bounded GCS read populates the cache at boot. `/health` then echoes `gcs:ops/goal_judge_config.json` immediately; a GCS failure logs a warning and leaves the cold `env`/`default` fallback (no startup crash).
- Preserve the Recipe 15 invariant: `health_posture()` remains cache-only; only `get()` performs I/O, now also at startup.
- Tests ([tests/middleware/test_app_prod.py](../../tests/middleware/test_app_prod.py) and/or [tests/services/test_goal_judge_runtime_config.py](../../tests/services/test_goal_judge_runtime_config.py)): assert the cache is warmed at startup (health reflects GCS without a prior request) and that a GCS error at startup is swallowed (posture falls back, warning logged, app boots). Keep `pytest -p no:logfire`.

## Workstream D - Infra: diagnose external `/healthz` edge 404

- Live diagnosis (read-only): `curl -v` both `/healthz` and `/health` to compare status, `server:`/`via:` headers, and body origin; then `gcloud logging read` for the backend service to confirm whether the `/healthz` request reaches the container or is rejected at the edge.
- Contingency on findings:
  - If the request never reaches the container (pure Google-edge behavior on `run.app`): no Terraform change is possible/needed; the Workstream A doc switch to `/health` is the resolution, and we record the edge quirk in the walkthrough Troubleshooting table.
  - If the request reaches the container and the app 404s (would contradict current evidence): fix route registration in [middleware/app_prod.py](../../middleware/app_prod.py) and add a regression test.
- No `google_compute_*` LB/url-map/Cloud Armor resources exist in `infra/gcp/`, so this workstream is diagnosis + documentation, not a routing reconfiguration, unless diagnosis proves otherwise.

## Workstream E - Local-run code fixes (formalize + tests)

Keep the applied fixes; make them commit-ready.

| Issue | File | Action |
| --- | --- | --- |
| S7 | [cli.py](../../cli.py) | Add regression test: `workflow_id` / `task_id` match `^[0-9a-f]{32}$`. Confirm no consumers depend on `wf-`/`task-` prefixes. |
| S8 | [cli.py](../../cli.py) | Document `recursion_limit: 100` rationale in a one-line comment or test note. |
| S9 | [logging.json](../../logging.json) | Assert (test or manual checklist) that a `goal_judge` eval_capture line in `logs/evals.log` parses as JSON with `target`, `ai_response.goal_met`, etc. |

**Validation:** `pytest -p no:logfire` on new/touched test modules green.

## Workstream F - Judge-quality findings (documentation only)

**No implementation in this plan.** Record J1–J3 for Stage 3 (axial coding / failure taxonomy) and Stage 4 (rubric + `prompts/goal_judge_system_prompt.j2`).

| Finding | Evidence | Deferred to |
| --- | --- | --- |
| J1 | [plan_builder.py:52-55](../../components/plan_builder.py) | Task-derived `success_conditions` |
| J2 | P4 per-criterion contradiction | Independent atomic criteria in judge prompt |
| J3 | P2/P3 "actionable" penalized on graceful failure | Feasibility-relative actionability rule |

Cross-links:
- [goaljudge_phase2_open_coding.md](../research/goaljudge_phase2_open_coding.md) §4
- [goaljudge_evaluation_pipeline_open_axial_coding_rubric.md](../research/goaljudge_evaluation_pipeline_open_axial_coding_rubric.md) Stages 3–4

## Workstream G - Export script formalization

- Commit [scripts/export_goaljudge_corpus.py](../../scripts/export_goaljudge_corpus.py) (extracted from walkthrough Step 6).
- Document prerequisites in script docstring or walkthrough: `LANGFUSE_*` env, `pip install -e ".[dev]"`, outbox relay before export.
- Investigate E1 (9 vs 10 rows): compare Posture A `trace_id`s in walkthrough run log vs Langfuse list window / relayed outbox files.

---

## Validation

### GCP (original)

- `pytest -p no:logfire tests/middleware/test_app_prod.py tests/services/test_goal_judge_runtime_config.py -q` green.
- After deploy (or locally with `GOAL_JUDGE_CONFIG_URI=file://...`): a cold `/health` shows `source:"gcs:..."` (or documented `env` fallback on GCS error) without a warm-up request.
- Walkthrough re-run: P1/P4 on `/workspace/...` reach `goal_met=true`/expected axes; reworked P2 reliably exercises (or correctly explains) the `goal_met=false` stratum.

### Local (this session)

- CLI trace-id regression test green (S7).
- Posture B gate behavior already validated locally (P1/P3 downgraded with `downgrade_reason=goal_judge`; P2/P4/P5 bypass correct).
- Judge-quality items (J1–J3): **findings recorded only** — no behavior change expected until rubric stage.

---

## Session outcomes (completed, not in to-do scope)

Recorded for traceability; no further work unless regressions appear.

| Item | Status |
| --- | --- |
| Posture A shadow validation (P1–P5) | Complete — run log in walkthrough |
| Posture B downgrade validation (P1–P5) | Complete — active downgrades on P1, P3 |
| Phase 2 open coding | Complete — [goaljudge_phase2_open_coding.md](../research/goaljudge_phase2_open_coding.md) |
| `config/goal_judge_config.json` | Reverted to shadow (`downgrade_enabled=false`) |
