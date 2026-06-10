# GoalJudge Stage 5 — Full Gold-Set IAA Results (α gate)

> **Status:** **READY** — α-gate plumbing landed; awaiting Phase 4-authoring corpus + Phase 3 labeling-sheet generation before live double-labeling begins.
> **Protocol:** [`README.md`](README.md) · [`full_set_labeling_protocol.md`](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md)
> **Pilot precedent:** [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md) — α=0.8846 PASS on 50 items.
> **Spec:** [`goaljudge_stage5_goldset_spec.md`](../../../research/goaljudge_stage5_goldset_spec.md)
> **α script:** [`scripts/compute_goaljudge_stage5_alpha.py`](../../../../scripts/compute_goaljudge_stage5_alpha.py)
> **Rubric version:** `stage4_confirmed` (Tier 2 CLEARED; A2 rubric locked).

---

## Scope (target — to be confirmed against the assembled sheet)

| Metric | Value |
|---|---|
| Target size | ~250 items (stratified per spec §4: 32/24/16/8 hard; 40/30/20/10 stretch) |
| Primary unit | Binary `goal_met` |
| Tier 3 gate (α ≥ 0.8 + test split frozen) | **PENDING** |

---

## α gate plumbing (Phase 5 — LANDED)

The Phase 5 plumbing closed without the labeling corpus:

| Artifact | Layer | Purpose |
|---|---|---|
| `services/governance/iaa.py` | Horizontal L1 | `krippendorff_alpha_nominal`, `landis_koch_band`, `normalize_bool_label`, `compute_disagreement_diff`, `apply_adjudication` — pure-stdlib, externally-verified. |
| `services/governance/goaljudge_goldset_dataset.evaluate_goldset_post_alpha_coverage` | Horizontal L1 | Filters to adjudicated `goal_met=false` subset before re-using `compute_cell_coverage`. |
| `scripts/compute_goaljudge_stage5_alpha.py` | scripts | CLI wrapper imports from `services.governance.iaa`; gains `--diff OUT.csv` to write the adjudicator's working copy. |
| `tests/services/governance/test_iaa.py` | tests/services L1 | 49 tests (28 α/landis-koch/normalize + 5 disagreement-diff + 4 adjudication-apply + 12 boundary/property variants). |
| `tests/services/test_goaljudge_goldset_dataset.py::TestEvaluateGoldsetPostAlphaCoverage` | tests/services L1 | 5 tests (3 failure-paths + 2 acceptance). |
| `tests/scripts/test_compute_goaljudge_stage5_alpha.py` | tests/scripts L2 | 4 contract tests (PASS path, FAIL path, `--diff` writes, no-flag back-compat). |

α-gate behavior contract (locked):

* Per Stage 5 spec §6, the gate is α ≥ 0.8 on `goal_met`.
* The script reads the same `r1_*` / `r2_*` columns the pilot already used.
* `--diff` emits a 3-column CSV (`item_id, r1, r2`) of canonical-spelling disagreements; the adjudicator's input to step 4.
* `apply_adjudication` enforces three invariants up-front: every disagreement has a decision; no decision targets an agreement row; `goal_met` decisions are canonical `true`/`false`.

---

## Procedure (full ~250 run — to be executed)

1. Distribute the empty-`r*` sheet (produced by Phase 3 builder) + this doc + the pilot disagreement post-mortem + the [labeling protocol](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md) to both annotators.
2. Annotators label blind, each scoping their own `r1_*` or `r2_*` columns. They MUST consult the labeling protocol's worked examples before grading the first row.
3. Run:
   ```
   python scripts/compute_goaljudge_stage5_alpha.py \
       docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv \
       --diff cache/goaljudge_eval/stage5_full_alpha_disagreements.csv
   ```
4. **If α < 0.8:** revise the guidelines on the disagreements (EvalGen co-construction loop); add disambiguating examples to [`README.md`](README.md); re-label **only the disagreement rows**. Recompute α.
5. **If α ≥ 0.8:** adjudicate disagreements to `adjudicated_goal_met` / `adjudicated_failure_mode`; that column becomes the gold label. Use `services.governance.iaa.apply_adjudication` to populate the sheet (invariants enforced).
6. **Cell-coverage check on the adjudicated set:** run the Phase 3 cell-coverage report against the **adjudicated `goal_met=false` subset only** (via `evaluate_goldset_post_alpha_coverage`). Every D1, D5-cluster, D7 cell that the spec requires for per-code/per-axis P/R must have ≥ 5 `goal_met=false` items (or carve-out). This is a quality check on the labeling; if a cell collapses, fresh authoring may be needed before freeze.

---

## Results

*(Filled after labeling completes. Keep the same shape as the pilot: status banner, scope table, α table, annotator summary, disagreement post-mortem, execution appendix.)*

| Metric | Value |
|---|---|
| Rows double-labeled | _pending_ |
| Raw agreements (`goal_met`) | _pending_ |
| α (`goal_met`) | _pending_ |
| Landis-Koch band | _pending_ |
| Tier 3 gate | _pending_ |

### Annotator summary

| Annotator | `goal_met=true` | `goal_met=false` |
|---|---|---|
| Annotator 1 | _pending_ | _pending_ |
| Annotator 2 | _pending_ | _pending_ |

---

## Disagreement post-mortem (template)

| Case | Annotator 1 | Annotator 2 | Adjudicated | Root cause |
|---|---|---|---|---|
| _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |

**Metadata-only differences** (not α disagreements):

| Case | Field | Annotator 1 | Annotator 2 |
|---|---|---|---|
| _pending_ | _pending_ | _pending_ | _pending_ |

**Guideline revision** (carried forward from pilot + this run's findings):

* From pilot: "Scaffold items with explicit process constraints default to process-verified `goal_met=false` unless the task text is purely outcome-only."
* From pilot: "Computation items requiring tool evidence default to `goal_met=false` if the answer is correct but unverified by tool."
* From pilot: Member-code disagreement within an agreed `goal_met=false` is **not** an α disagreement (Stage 4 convention).
* New (dimension-aware): "If a task is L2 by router prediction but the trace shows the agent executed at L0, grade based on the observed batch behavior, not the L2 intent. Note `planner_truncation_suspected` in the row's `note` column for follow-up."

---

## Cell-coverage check on adjudicated `goal_met=false` subset (Phase 5 step 6)

*(Filled after adjudication; uses `evaluate_goldset_post_alpha_coverage`.)*

```text
# python -c "from services.governance.goaljudge_goldset_dataset import evaluate_goldset_post_alpha_coverage; ..."
total_items=...  # rows where adjudicated_goal_met == 'false'
D1: { L0: gap, L1: gap, L2: gap }
D5: { ... }
```

---

## Execution appendix (filled after run)

| Artifact | Path |
|---|---|
| Full sheet | `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv` |
| Annotator 1 report | _pending_ |
| Annotator 2 report | _pending_ |
| Disagreement diff | `cache/goaljudge_eval/stage5_full_alpha_disagreements.csv` |
| Post-α coverage report | `cache/goaljudge_eval/stage5_post_alpha_coverage.md` |
| Labeling protocol | [`full_set_labeling_protocol.md`](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md) |
