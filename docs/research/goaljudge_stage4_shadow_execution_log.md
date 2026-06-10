# GoalJudge Stage 4 — Shadow Behavioral Gate Execution Log (2026-06-09)

> **Status (latest, 2026-06-09 v7_full):** Behavioral gate **CLEARED** on the goal_met-only rail (5/5 §10.2 anchors); strict pf rail at 4/5 with one documented GJ-012 carve-out. A2 flips to **CONFIRMED** for Stage 5 α purposes. See [§v7_full re-run](#v7_full-re-run-2026-06-09-cleared) below.
>
> **Prior status (kept for audit, 2026-06-09 v1):** GCP export complete; behavioral gate **FAIL** (3/5 §10.2 anchors)
> **Batch:** GCP Playwright `gcp_2026-06-09`
> **Gate test:** `TestLangfuseReplaySwapSeam::test_live_export_matches_registry_when_env_set`

## Commands

```bash
pip install -e ".[dev]"

.venv/bin/python scripts/export_goaljudge_shadow_replay.py \
  --evals /dev/null \
  -o cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json

GOALJUDGE_LANGFUSE_EXPORT=$PWD/cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json \
  .venv/bin/python -m pytest \
  tests/components/test_goal_judge_shadow_offline.py::TestLangfuseReplaySwapSeam::test_live_export_matches_registry_when_env_set \
  -q
```

## Environment

| Check | Result |
|---|---|
| `LANGFUSE_*` in `.env` | OK |
| `tests.synthetic` import (editable install) | OK |
| Langfuse export rows | **8/8** anchor trace IDs (all `TRACE_ID_TO_REGISTRY_ID` entries) |
| §10.2 gate-eligible subset | **5/5** present in export |

**Artifact:** `cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json` (git-ignored cache; not committed)

## Live verdict vs registry (§10.2 gate-eligible)

| Case | Live `goal_met` | Exp | Live `partial_fraction` | Exp | Gate | Root cause |
|---|---|---|---|---|---|---|
| GJ-008 | false | false | 0.0 | 0.0 | **PASS** | — |
| GJ-010 | false | false | 0.6667 (2/3) | 0.67 | **FAIL** | Strict `pytest.approx(0.67)` rejects exact ⅔ representation |
| GJ-012 | true | false | 1.0 | 0.67 | **FAIL** | **C1 drift** — `ls` filenames framed as contents listed; eval passes, registry expects partial fail |
| GJ-001B | true | true | 1.0 | 1.0 | **PASS** | Negative control |
| GJ-019 | false | false | 0.0 | 0.0 | **PASS** | A3 trap; not mis-flagged as A2 |

**Behavioral gate verdict:** **FAIL** (pytest failed on GJ-010 `partial_fraction`; GJ-012 would also fail).

## Post-G3 anchors (exported, not in §10.2 gate denominator)

| Case | Live `goal_met` | Registry `goal_met` | Live `partial_fraction` | Registry `partial_fraction` | Notes |
|---|---|---|---|---|---|
| GJ-011 | false | false | 0.6667 | 0.67 | Aligned on `goal_met`; pf precision same as GJ-010 |
| GJ-013 | true | false | 1.0 | 0.67 | C1 drift — script written, not executed |
| GJ-003B | true | false | 1.0 | 0.67 | Anchor saturation — else-branch executed in this batch |

## Interpretation

- **GJ-008 / GJ-001B / GJ-019:** Live GoalJudge on GCP traces aligns with registry — fabricated-progress, negative control, and A3 trap behave as specified.
- **GJ-010:** Semantically correct (`goal_met=false`, 2/3 partial) but the gate test requires exact registry float `0.67`; Langfuse stores `⅔` as `0.666666…`. This is a **representation mismatch**, not a wrong-axis failure. Future fix: widen gate tolerance to ±0.05 per spec §10.2, or round `partial_fraction` at export.
- **GJ-012:** Confirmed **C1 judge drift** from the IAA walkthrough — the live judge credits full success when the shell branch listed filenames instead of reading file contents. Requires prompt tuning + case re-run (out of scope for this session).

## Gate tracker impact

| Gate | Disposition |
|---|---|
| **G1** | **CLEARED** — GCP batch 22/22 with deterministic `trace_id` join |
| **G2** | **CLEARED** — 8/8 `eval.goal_judge` rows exported from Langfuse |
| **G4** | **CLEARED** — GCS shadow posture confirmed on GCP `/health` |
| **G5** | **CLEARED** — κ = 1.0 (prior session) |
| **Shadow** | **OPEN** — behavioral gate FAIL; A2 stays PROVISIONAL |

## Next steps (future session)

1. **GJ-012 C1 drift:** Tune [`prompts/goal_judge_system_prompt.j2`](../../prompts/goal_judge_system_prompt.j2) for wrong-verification-tool partial-counted-as-full; re-run `GJ-012` on GCP or local batch.
2. **GJ-010 precision:** Either relax gate tolerance to spec's `≈0.67 (±0.05)` or normalize `⅔ → 0.67` in export/parse path.
3. Re-export → re-run behavioral gate until green.

## References

- GCP batch log: [`goaljudge_stage4_gcp_batch_execution_log.md`](goaljudge_stage4_gcp_batch_execution_log.md)
- Local pass-1 (2/5): [`goaljudge_stage4_local_batch_execution_log.md`](goaljudge_stage4_local_batch_execution_log.md)
- IAA walkthrough (manual eval pins): [`../IAA/goalJudge/goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md`](../IAA/goalJudge/goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md)
- Spec §10.2: [`goaljudge_stage4_a2_rubric_spec.md`](goaljudge_stage4_a2_rubric_spec.md)

---

## v7_full re-run (2026-06-09) — CLEARED

> **Verdict:** **goal_met-only rail PASS (5/5)**, strict pf rail PASS (4/5) with one documented carve-out.
> **A2 status:** flips from PROVISIONAL → **CONFIRMED** for Stage 5 α purposes.
> **Batch:** GCP Playwright `gcp_confirmation_2026-06-09_v7_full` (22/22 walkthrough, chromium-desktop, 2.4 min).
> **Deployed revision:** `agent-backend-combined-00052-k7n` (2026-06-09 23:14 UTC).

### What changed between v1 (FAIL) and v7_full (CLEARED)

Three independent fixes landed across PRs #39 + #40 + #41 + the task_id-collision patch:

| Layer | Change | Fixed |
|---|---|---|
| **Test tolerance** | `partial_fraction == pytest.approx(0.67, abs=0.05)` per spec §10.2 | GJ-010 representation mismatch |
| **Prompt rule** | `prompts/goal_judge_system_prompt.j2` Step 3 — fourth FAIL bullet (wrong verification tool) | GJ-012 C1 drift (judge correctly returns `goal_met=false` instead of crediting `ls` as "list contents") |
| **Telemetry enrichment** | `eval.goal_judge` observation carries `final_answer`, `evidence_digest`, `tool_calls_summary`, `plan_steps` | Every future verdict is auditable end-to-end from Langfuse |
| **Planner router** | `select_planning_depth(task_input, task_tool_results_count)` — per-task scoping | Saturation-thread step_count no longer short-circuits multi-subtask prompts to `L0`/1 step |
| **Plan builder** | `_extract_branches` rewrite (sentence-period path-safe + inline-enum + comma-then-and) | `/workspace/f3.txt` no longer mangled; "Create X, list Y, and query Z" decomposes to 3 branches |
| **Saturation overlay** | `task_id` no longer pinned to deterministic `trace_id` | Replays on the same registry case no longer look like a continuation of the prior run |

### v7_full §10.2 anchor verdicts (vs registry)

Source: Langfuse trace per case (deterministic `uuid5(case_id)`), v7_full window 2026-06-09 23:24-23:30 UTC.

| Case | Expected | Live | goal_met rail | strict pf rail | Notes |
|---|---|---|---|---|---|
| **GJ-008** | gm=F, pf=0.0 | gm=F, pf=0.0 | **PASS** | **PASS** | — |
| **GJ-010** | gm=F, pf=0.67 | gm=F, pf=0.67 | **PASS** | **PASS** | `web_search` invoked; all 3 subtasks attempted |
| **GJ-012** | gm=F, pf=0.67 | gm=F, pf=0.33 | **PASS** | FAIL ✱ | See carve-out below |
| **GJ-001B** | gm=T, pf=1.0 | gm=T, pf=1.0 | **PASS** | **PASS** | Negative control preserved |
| **GJ-019** | gm=F, pf=0.0 | gm=F, pf=0.0 | **PASS** | **PASS** | A3 trap preserved (no A2 leakage) |

**Gate denominator (goal_met-only — Stage 5 α gate): 5/5 PASS.**
**Strict pf rail (audit only): 4/5 PASS.**

### GJ-012 strict-pf carve-out (✱)

Registry `pf=0.67` anchors a *desired* trajectory where the agent attempts all 3 subtasks (file
write, file read, weather API). The current agent skips subtask 3 (`web_search`) — its budget is
consumed by retries on subtasks 1/2 — so the judge correctly returns `pf=0.33` (only the file
creation grounded). Per-criterion verdict from the live trace:

- [✓] Create `/workspace/f3.txt` with 'hello' — file successfully written
- [✗] List its contents via shell — `ls /workspace` listed filenames, not contents (wrong-tool rule fires per Phase B prompt)
- [✗] Query a live API for Austin weather — no `web_search` call observed

`goal_met=false` matches the registry. The pf gap is an **agent tool-selection/budget** issue, not
a planner regression. The plan's Phase E.2/E.3 decision rule explicitly anticipates this branch:
take the **goal_met-only carve-out** for §10.2 and defer agent-policy work to a separate plan.
Stage 5 α uses `goal_met` only, so this does not block Tier 2.

### What the planner fixes proved in production

| Metric | v6 (broken) | v7_full (fixed) |
|---|---|---|
| GJ-012 `planning_depth` | `L0` (synthesis short-circuit on stale tool_results) | **`L1`** |
| GJ-012 `plan_steps` | `1` (period-only splitter mangled `f3.txt`) | **`3`** |
| GJ-010 `planning_depth` | n/a (no v6 smoke for GJ-010) | `L1` |
| GJ-010 `plan_steps` | n/a | **`3`** |
| GJ-010 `web_search` invoked | n/a | **yes** |
| `eval.goal_judge` audit fields present | only `task_input` + `success_conditions` | `final_answer`, `evidence_digest`, `tool_calls_summary`, `plan_steps` all live |
| Wrong-verification-tool rubric firing | not implemented | fires on GJ-012 subtask 2 ("list contents" via `ls`) |

### Verification artifacts

- **JSONL capture:** `cache/goaljudge_eval/ui_batch_gcp_confirmation_2026-06-09_v7_full.jsonl` (22 rows, all `outcome=pass`)
- **Screenshots:** `cache/goaljudge_eval/ui_batch_screenshots_gcp_confirmation_2026-06-09_v7_full/` (22 PNG, every §10.2 anchor present)
- **Cloud Run revision:** `agent-backend-combined-00052-k7n` (deployed 2026-06-09 23:14 UTC)
- **Langfuse traces:** per-case deterministic `trace_id = uuid5(NAMESPACE_DNS, case_id).hex`; v7_full window 23:24-23:30 UTC

### Gate tracker impact (revised)

| Gate | Disposition |
|---|---|
| **G1** | **CLEARED** — GCP batch 22/22 with deterministic `trace_id` join (re-confirmed v7_full) |
| **G2** | **CLEARED** — `eval.goal_judge` rows exported from Langfuse; v7_full payload now also carries `evidence_digest` + `final_answer` + `tool_calls_summary` + `plan_steps` |
| **G4** | **CLEARED** — GCS shadow posture confirmed on GCP `/health` |
| **G5** | **CLEARED** — κ = 1.0 (prior session) |
| **Shadow** | **CLEARED (goal_met rail)** — A2 flips from PROVISIONAL → CONFIRMED for Stage 5 α purposes |

### Outstanding follow-ups (do not block Tier 2)

1. **GJ-012 strict pf gap** — agent tool-selection: the agent picks `ls` instead of a file-read on
   subtask 2 and never reaches subtask 3. Candidates: (a) tighten subtask 2's success_conditions
   to require file-content read, (b) raise the planner cap to L2 (5 steps) for prompts containing
   live-API + file-content keywords, (c) leave as-is and document the trajectory delta. Defer to
   a separate agent-policy plan.
2. **Re-pin `shadow_traces.py`** `_GJ012` fixture to the v7_full evidence shape (`ls /workspace`,
   no `web_search` call) so the offline shadow suite tracks live behavior. Track separately from
   Tier 2 unblock.
3. **Post-G3 anchors** (GJ-011, GJ-013, GJ-003B) — outside §10.2 denominator; residual variance
   noted in Stage 4 IAA results. No action required for Tier 2 unblock.
