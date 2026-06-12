# GoalJudge Stage 6 — Phase 0 Replay-Input Audit

> **Run date:** 2026-06-12
> **Inputs audited:** [`goaljudge_stage5_goldset_combined_sheet.csv`](../IAA/goalJudge/goldset/goaljudge_stage5_goldset_combined_sheet.csv) (101 rows, v0.9)
> × `corpus_gcp_fresh_stage5_rerun_2026-06-10.jsonl` + `corpus_gcp_goldset_pilot_2026-06-09.jsonl`
> × `ui_batch_gcp_fresh_stage5_rerun_2026-06-10.jsonl` + `ui_batch_gcp_goldset_pilot_2026-06-09.jsonl`
> **Gate (≥ 90 % joinable success_conditions): PASS — 100/101 (99 %).**
> **Plan:** [goaljudge_stage6_calibration.plan.md](../plans/goaljudge_stage6_calibration.plan.md) Phase 0; this doc locks the §4 seam decisions.

---

## 1. Coverage results

| Check | Result | Detail |
|---|---|---|
| Join key | **101/101** | `trace_id = uuid5(NAMESPACE_DNS, item_id).hex` verified exactly (GJ-F-001 → `4d2a8388…`). Works for fresh AND pilot rows. No sheet change needed — and none is allowed: `compute_test_split_hash` covers `source_trace_id` (`exclude_none=False`), so backfilling trace ids into the v0.9 sheet would break the frozen hash. |
| `eval.goal_judge` span present | **100/101** | Only **GJ-003** lacks the span (its pilot trajectory has unnamed spans and `per_criterion=null` — no fallback). GJ-003 is **excluded from replay and counted** in the report. |
| `success_conditions` present | **100/100** of spans | See §3 — they are constant boilerplate. |
| Recorded production verdict joinable | **97/101** | `goal_met` parseable on 97 corpus rows; 4 rows (incl. GJ-003) unparseable/absent. |

## 2. The central finding — full judge inputs were never persisted

The production judge received **full** `task_input` / `final_answer` / `evidence_digest`
in-process. What was *persisted* is doubly truncated:

1. **At telemetry construction** ([orchestration/react_loop.py:1399-1401](../../orchestration/react_loop.py)):
   `task_input[:500]`, `final_answer[:500]` (evidence_digest passed full).
2. **At publish** ([services/governance/black_box_publisher.py:37](../../services/governance/black_box_publisher.py)):
   `redact_text` truncates **every attribute value to `_MAX_DETAIL_VALUE_LEN = 200`**
   before the exporter ships it. The Langfuse observation therefore never contained
   more than 200 chars per field.

Observed in the spans: `final_answer` — 42/100 at exactly 200 (truncated), 21 empty;
`evidence_digest` — 63/100 at exactly 200 (truncated), 15 complete
(`"(no tool calls were made)"`, genuinely no-tool rows), 21 empty.

**Consequences:**

* **Wave-1/pilot full inputs are unrecoverable.** Re-exporting from Langfuse cannot
  help — truncation happened before publish. Tool *outputs* are also absent from the
  trajectory (`step.executed` records LLM call metrics, not tool results), so the
  digest cannot be faithfully reconstructed offline either.
* **WAVE-2 PREREQUISITE (new):** before the wave-2 GCP batch runs, raise/except the
  eval-observation caps so wave-2 traces persist full judge inputs — otherwise v1
  calibration inherits the same fidelity ceiling. Concretely: lift the `[:500]`s at
  `react_loop.py:1399-1401` (or make them config-driven) **and** give
  `eval.goal_judge` attributes an exemption / larger bound than
  `_MAX_DETAIL_VALUE_LEN=200` in the publish path. Tracked in the
  [wave-2 plan](../plans/goaljudge_stage5_phase6c_v09_and_wave2.plan.md) §5.2 ordering.
* The sheet's own columns don't fill the gap: `evidence_summary` is **empty on all 79
  fresh rows** (annotators read evidence from the UI + Langfuse bundles, never the
  sheet) and `claim` is empty on the same 79. `GoldsetItem.final_answer` /
  `.evidence_digest` are therefore empty strings for fresh rows — **not** replay inputs.
* The **full final answer does survive** in one place: `ui_batch_*.jsonl`
  `response_text` (DOM capture) — **101/101 coverage**, median 252 / max 3605 chars,
  well past both caps. (Strip the `Using tools: …` status prefix per the Playwright
  skill before use.)

## 3. `success_conditions` — constant generic boilerplate (production finding)

All 100 spans carry **the identical pair**:

> 1. "All planned branches are addressed in the final synthesis."
> 2. "Final answer is concise, actionable, and internally consistent."

`plan_builder` emitted generic defaults on every one of these 101 runs — the
production judge has **never** evaluated against task-specific success conditions in
this corpus. Two consequences:

* **For replay:** the conditions join is trivial — the pair is a constant. Replaying
  with it is production-faithful by definition.
* **As a finding:** generic conditions are a plausible contributor to judge error
  (the judge can't check task-specific completion it was never told about). Out of
  Stage 6 scope — Stage 6 measures the judge as deployed — but flagged for separate
  investigation.

## 4. Zero-cost production-shadow calibration (recorded verdicts vs. gold)

The corpus rows record the production judge's **full-fidelity** verdicts (truncation
only affected persistence, not the in-process judge inputs). Comparing them to the
adjudicated gold labels — no replay, no LLM cost, n = 97:

| Metric | Value | §2.8 gate | Read |
|---|---|---|---|
| Raw agreement | 81/97 = **0.835** | — | |
| Precision on `goal_met=False` | **0.896** | ≥ 0.90 | *just* under the gate |
| Recall on `goal_met=False` | **0.896** | ≥ 0.70 | comfortably clear |
| False-downgrade rate | **0.400** (8/20 gold-met) | ≤ 0.02 | see caveat below |
| α (judge vs gold, ~κ) | **0.4987** | ≥ 0.6 | **below the prerequisite** |

Confusion: TP=69, FP=8, FN=8, TN=12.

**Caveats:** the gold corpus deliberately oversamples failures (79 % not-met), so the
0.400 is the rate *conditional on gold-met* over a 20-row subset — not the
production-traffic FD-rate. Still, 8/20 wrongly-failed clean successes is not a
sample-size artifact at this magnitude. And the verdicts are single-shot from the
2026-06-09/06-10 deployed prompt+model.

**The misfire lists align exactly with known rubric blind spots:**

* FP (judge=not-met, gold=met): GJ-F-015, **GJ-F-068, GJ-F-074** (the Rule 7
  push-back-success adjudications), GJ-F-039/041/091, GJ-004, GJ-005 — the judge
  penalizes correct push-back and registry-true rows.
* FN (judge=met, gold=not-met): **GJ-F-003** (right-answer-wrong-process),
  **GJ-F-034** (subtask-dropped), GJ-F-004/057/062/063, GJ-012, GJ-022 — the judge
  passes fluent answers whose process or coverage was wrong.

This is the early-warning signal the calibration plan's Phase 4 hoped for, delivered
at Phase 0 for free: **as deployed on 2026-06-10, the judge would not clear the §2.8
gates** (α below prerequisite; FD-rate far above ceiling on this stratified sample).
The Stage 6 build remains exactly as planned — these numbers are what the harness
will formalize, CI-bound, and re-measure at v1.

## 5. ECE proxy viability

`criteria_met` is recorded as stringified floats and is effectively **trimodal**:
0.0 × 64, 0.5 × 11, 0.6 × 1, 0.9 × 21 (n = 97). With only two conditions per run
(§3), the proxy can mathematically only take values {0, 0.5, 1}-ish. **Decision:**
ECE is reported over this coarse proxy with the degeneracy caveat stated inline;
treat it as a sanity plot, not a calibration curve, until conditions become
task-specific.

## 6. Locked §4 decisions (amending the plan)

| Seam | Decision |
|---|---|
| **Join key** | Derive `trace_id = uuid5(NAMESPACE_DNS, item_id).hex` in the harness. Never backfill the sheet (hash freeze). |
| **Primary v0.9 signal** | **Recorded production verdicts** (full input fidelity, already persisted). The replay run validates harness mechanics and measures prompt/model drift since 06-10 — it does not replace the recorded-verdict baseline at v0.9. |
| **Replay `task_input`** | Sheet `task` column (full, human-authored; matches span prefix). |
| **Replay `final_answer`** | `ui_batch` `response_text` joined by derived trace_id, status-prefix stripped (101/101 coverage). |
| **Replay `evidence_digest`** | Span value as-is, with a per-row `input_fidelity` flag: `full` (15 no-tool rows + empty-digest rows whose runs made no tool calls), `truncated` (200-cap rows), `unknown-empty` (21 rows). Report stratifies by this flag. No offline reconstruction (tool outputs not persisted). |
| **Replay `success_conditions`** | The constant boilerplate pair (verified identical on 100/100). |
| **GJ-003** | Excluded from replay; counted in the report. |
| **ECE proxy** | `criteria_met`, coarse-trimodal caveat inline (§5). |
| **Wave-2 prerequisite** | Telemetry cap lift for `eval.goal_judge` (§2) must land **before** the wave-2 GCP batch. |

## 7. Phase 0 verdict

**PASS — proceed to Phase 1.** Coverage gate cleared (99 %). The §4 seams are
locked, with one plan amendment (recorded-verdict baseline as the primary v0.9
signal) and one new wave-2 prerequisite (telemetry cap lift). The free shadow
calibration says the judge as deployed would fail §2.8 today — which raises, not
lowers, the value of building the harness: every prompt/model improvement from here
needs exactly this measurement loop to prove itself.
