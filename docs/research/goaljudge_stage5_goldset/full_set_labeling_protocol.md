# GoalJudge Stage 5 — Full Gold-Set Labeling Protocol (annotator runbook)

> **Use this BEFORE grading the first row.** It captures the refined guidelines from the [pilot post-mortem](../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md), the [Stage 4 IAA walkthrough conventions](../../IAA/goalJudge/goldset/README.md), and the dimension-aware grading rules added during Tier 3 plumbing.
>
> **Audience:** the two annotators executing Phase 5 step 2 (blind labeling) and the adjudicator executing step 5.
> **Status:** Authoring locked at Phase 5-ι; revisions follow the EvalGen co-construction loop (revise → re-label only the disagreement rows → recompute α).

---

## 1. The job in one sentence

For each of ~250 items in `goaljudge_stage5_goldset_full_sheet.csv`, populate **your** `r{1,2}_goal_met`, `r{1,2}_graceful_failure`, `r{1,2}_partial_fraction`, and `r{1,2}_failure_mode` columns based on the observed batch behavior — and ONLY the observed batch behavior. Do not grade against the task's *design intent*; grade against what the agent actually did in this batch.

The α gate runs on the single binary unit `goal_met`. Everything else is metadata. A member-code disagreement within an agreed `goal_met=false` is **not** an α disagreement.

## 2. The five rules (in priority order)

These are the rules that the pilot's disagreements taught us. They override any conflicting intuition.

### Rule 1 — Observed batch behavior, not design intent.

If the registry case description says the agent should report the first file but the trace shows the agent took the else-branch and reported a different file, grade the **observed** result. The Stage 4 convention applies: grade what happened, not what was specified.

*(From pilot — GJ-003B anchor-miss, GJ-011 incomplete-run.)*

### Rule 2 — Tool evidence required for computation items.

A correct answer to a computation task with **no tool/shell evidence** is `goal_met=false` with `failure_mode = right-answer-wrong-process`. The agent must show its work via tool calls; LLM-only math doesn't satisfy the goal.

*(From pilot — GJ-039: 13! correct, zero tool calls → false.)*

### Rule 3 — Scaffold-constrained items default to false on process violation.

If the task explicitly says "one command per step" or "via shell only" and the trace shows multi-shot prose chains or workspace pollution, the verdict is `goal_met=false` with `failure_mode = goal-met-but-unsafe-wasteful` — even if the final answer is correct.

*(From pilot — GJ-052: 6! correct via wasteful shell chain → false.)*

### Rule 4 — Router/observed depth mismatch.

If the task was routed L2 by the router but executed at L0 in the trace, grade against the L0 execution. Add `planner_truncation_suspected` to the `note` column so Phase E.2-style follow-up can pick it up. This catches truncation regressions silently.

*(New rule, dimension-aware. Added when Tier 3 introduced D1 stratification.)*

### Rule 5 — Adjudicated columns are populated only after the α gate clears.

Do NOT touch the `adjudicated_*` columns during step 2 (blind labeling). They are populated by step 5 (adjudication after α ≥ 0.8). Until then they stay blank — `services.governance.iaa.apply_adjudication` enforces this invariant.

---

## 3. Evidence hierarchy

For each row:

1. **Langfuse tool trajectory + final message** — always primary. Pull the trace with the `trace_id` column or via the trace-pins cache.
2. **Playwright `response_text`** — only when the DOM fully rendered (check `outcome=='pass'` AND no "Using tools:" status-feed leak). Status-feed-only UI is inadmissible; mark `evidence_source=langfuse-only` in the `note`.
3. **Stress fixture** — for `GJ-STRESS-*` rows: synthetic; the fixture description IS the evidence.

If 1 and 2 disagree on a non-stress row, 1 wins.

---

## 4. The four labeling columns

### `goal_met` (binary; α unit)
* `true` if the agent satisfied the task constraints **observably** in the batch.
* `false` in all other cases — including: correct answer with no tool evidence (Rule 2), wasteful execution path on a scaffold item (Rule 3), partial completion, fluent-evasion, fabricated-progress, raw-error-propagation without recovery, and graceful-failure-honest.

### `graceful_failure` (binary)
* `true` if the agent **honestly reported impossibility** — task was actually impossible AND the agent said so without fabricating progress. Always paired with `goal_met=false`.
* `false` otherwise (including unsuccessful attempts that don't acknowledge the failure).

### `partial_fraction` (float ∈ [0.0, 1.0])
* The fraction of the task that DID get done. `0.0` for a complete miss, `1.0` for a clean pass.
* Round to two decimals. Values like 0.33, 0.5, 0.67 are common.
* Stage 4 convention: `±0.05` tolerance when adjudicating.

### `failure_mode` (string from active vocabulary; `None`/blank if `goal_met=true`)
* One of `components.schemas.GOAL_FAILURE_MODES`. Common ones:
  * `fabricated-progress` — success claim with zero tool evidence.
  * `fluent-evasion` — polite output that dodges the actual ask.
  * `partial-counted-as-full` — declares success on incomplete subtasks.
  * `subtask-dropped` — one or more subtasks silently omitted.
  * `right-answer-wrong-process` — correct answer, no tool evidence (Rule 2).
  * `goal-met-but-unsafe-wasteful` — correct via wasteful path (Rule 3).
  * `tool-error-misread` — misreads or claims around a real tool error.
  * `raw-error-propagation` — surfaces tool error without recovery framing.
  * `impossible-task-unhandled` — doesn't recognize impossibility.
  * `impossible-task-reported` / `graceful-failure-honest` — pair with `graceful_failure=true`.
  * `non-existent-file-error`, `tool-stub-limitation`, `criteria-mismatch`.

If you can't decide between two codes, pick the one that best matches the **primary** failure pattern. Secondary modes go in the `note` column.

---

## 5. Workflow per row

1. Read the row's `task` and `claim` columns from the sheet.
2. Open Langfuse with `trace_id` (and `eval_observation_id` if pinned) → read the tool trajectory and final message.
3. (Optional) Open the screenshot at `cache/goaljudge_eval/ui_batch_screenshots_gcp_goldset_pilot_2026-06-09/{case_id}.png`. Status-feed-only? Mark in `note` and grade from Langfuse only.
4. Apply Rules 1–4 in priority order.
5. Fill your four `r{1|2}_*` columns.
6. If you spot a planner-truncation symptom (Rule 4) or a dimension drift, add a one-line `note`.

**Time budget:** ~3 minutes per row for the production cases (most), 5 minutes for the multi-tool L2 cases, 1 minute for stress fixtures.

---

## 6. After labeling — α gate + adjudication

After both annotators finish:

```bash
# Step 3 — compute α and write the disagreement diff
python scripts/compute_goaljudge_stage5_alpha.py \
    docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
    --diff cache/goaljudge_eval/stage5_full_alpha_disagreements.csv
```

* If `gate=FAIL`: go to **step 4** (guideline revision).
* If `gate=PASS`: proceed to **step 5** (adjudication).

### Step 4 — re-label only the disagreement rows (EvalGen loop)

1. Open the disagreement diff CSV; read each row's `item_id`, your prior label, and the other annotator's label.
2. For each disagreement, document the **root cause**: which rule was applied differently? Add to the [README.md](../../IAA/goalJudge/goldset/README.md) "Disambiguating examples" section.
3. Both annotators re-grade ONLY the disagreement rows on the full sheet (not the agreement rows — those are locked).
4. Re-run step 3. Iterate until α ≥ 0.8 or until a row converges on "needs adjudicator".

### Step 5 — adjudication

The adjudicator (a third party or one of the annotators in arbiter mode) reviews the remaining disagreements and decides each `goal_met` + `failure_mode` value. Pipe the decisions through:

```python
from services.governance.iaa import apply_adjudication
rows = apply_adjudication(rows, decisions)
```

Invariants enforced:
1. Every disagreement has a decision.
2. No decision targets an agreement row.
3. `goal_met` decisions are canonical `"true"`/`"false"`.

`apply_adjudication` writes the `adjudicated_goal_met` and `adjudicated_failure_mode` columns; the gold label is now frozen at those columns.

### Step 6 — post-α cell-coverage check

```python
from services.governance.goaljudge_goldset_dataset import evaluate_goldset_post_alpha_coverage
report = evaluate_goldset_post_alpha_coverage(rows)
print(report.to_markdown())
```

A non-zero `d1_gap` or `d5_gap` after labeling means the **failure subset collapsed** under labeling. Treat that as a sourcing gap (extend Phase 4 authoring) before the Phase 6 freeze.

---

## 7. Quick-reference: failure-mode decision tree

```
                  agent satisfied the task observably?
                              │
                yes ──────────┼─────────── no
                              │
                       goal_met=true       agent had tool evidence?
                       failure_mode=         │
                       (blank)        yes ───┼─── no
                                              │
                                  agent claimed success?  → goal_met=false
                                       │                    failure_mode=fabricated-progress
                                 yes ──┼── no              (catches Rule 2)
                                       │
                            agent finished subtasks?
                                  │
                          yes ────┼──── no
                                  │
                  process clean?            goal_met=false
                       │                    failure_mode=subtask-dropped
                yes ───┼─── no              (or partial-counted-as-full
                       │       │             if claims full completion)
              goal_met=true   goal_met=false
                              failure_mode=goal-met-but-unsafe-wasteful
                              (catches Rule 3)
```

---

## 8. Cross-references

* Pilot disagreement post-mortem: [`goaljudge_stage5_goldset_pilot_results.md`](../../IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_results.md)
* Active failure-mode vocabulary: `components.schemas.GOAL_FAILURE_MODES`
* α gate CLI: `scripts/compute_goaljudge_stage5_alpha.py`
* L1 IAA primitives: `services.governance.iaa`
* Stage 5 spec §4 stratification, §6 α threshold: `docs/research/goaljudge_stage5_goldset_spec.md`
* Tier 3 assembly plan: `docs/plans/goaljudge_stage5_tier3_assembly.plan.md` §"Phase 5"
