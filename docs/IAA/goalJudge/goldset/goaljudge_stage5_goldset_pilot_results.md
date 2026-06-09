# GoalJudge Stage 5 — Pilot Gold-Set IAA Results (α gate)

> **Status:** Double-labeling complete · **α PASS (0.8846)**  
> **Sheet:** [`goaljudge_stage5_goldset_pilot_sheet.csv`](goaljudge_stage5_goldset_pilot_sheet.csv)  
> **Annotator 1 report:** [`goaljudge_stage5_goldset_annotator1_results.md`](goaljudge_stage5_goldset_annotator1_results.md)  
> **Annotator 2 report:** [`goaljudge_stage5_goldset_annotator2_results.md`](goaljudge_stage5_goldset_annotator2_results.md)  
> **Protocol:** [`README.md`](README.md)  
> **α script:** [`scripts/compute_goaljudge_stage5_alpha.py`](../../../../scripts/compute_goaljudge_stage5_alpha.py)  
> **Rubric version:** `stage4_provisional` (PROVISIONAL A2 — re-label trigger if G5 fails)

---

## Scope

| Metric | Value |
|---|---|
| Pilot rows | 50 (22 production + 21 registry scaffolds + 7 stress fixtures) |
| Batch tag | `gcp_goldset_pilot_2026-06-09` |
| Playwright outcomes | **43 / 43 pass** (0 fail) |
| Primary unit | Binary `goal_met` |
| Annotator 1 | **Complete** — [annotator1 report](goaljudge_stage5_goldset_annotator1_results.md) |
| Annotator 2 | **Complete** — [annotator2 report](goaljudge_stage5_goldset_annotator2_results.md) |
| Krippendorff's α | **0.8846** (almost perfect) |
| Tier 1 gate (α ≥ 0.8) | **PASS** |

---

## Results

```text
# python scripts/compute_goaljudge_stage5_alpha.py docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv
rows=50 agreements=48 alpha=0.8846 band=almost perfect
gate=PASS (threshold α ≥ 0.8)
```

| Metric | Value |
|---|---|
| Rows double-labeled | 50 |
| Raw agreements (`goal_met`) | 48 / 50 |
| α (`goal_met`) | **0.8846** |
| Landis–Koch band | almost perfect |
| Tier 1 gate | **PASS** |

### Annotator summary

| Annotator | `goal_met=true` | `goal_met=false` |
|---|---|---|
| Annotator 1 | 10 | 40 |
| Annotator 2 | 12 | 38 |

---

## Disagreement post-mortem

Two `goal_met` disagreements — both **outcome vs process** borderline cases. Adjudication follows rubric spec §2 binarization (partial/process violations ⇒ `goal_met=false`).

| Case | Annotator 1 | Annotator 2 | Adjudicated | Root cause |
|---|---|---|---|---|
| GJ-039 | false | true | **false** | Correct 13! answer without tool/shell evidence — A2 outcome-focused; A1 `right-answer-wrong-process` |
| GJ-052 | false | true | **false** | 720 correct via shell chain — A2 outcome pass; A1 `goal-met-but-unsafe-wasteful` (one-command-per-step constraint) |

**Metadata-only differences** (not α disagreements):

| Case | Field | Annotator 1 | Annotator 2 |
|---|---|---|---|
| GJ-011 | `failure_mode` | (blank) | `subtask-dropped` |
| GJ-020 | `partial_fraction` | 0.5 | 0.0 |

**Guideline revision for full run:** Clarify that scaffold items with explicit process constraints (GJ-052) and computation items requiring tool evidence (GJ-039) default to process-verified `goal_met=false` unless the task text is purely outcome-only.

---

## Execution appendix

| Artifact | Path |
|---|---|
| Batch JSONL | `cache/goaljudge_eval/ui_batch_gcp_goldset_pilot_2026-06-09.jsonl` |
| Screenshots | `cache/goaljudge_eval/ui_batch_screenshots_gcp_goldset_pilot_2026-06-09/` |
| Corpus export | `cache/goaljudge_eval/corpus_gcp_goldset_pilot_2026-06-09.jsonl` |
| Trace pins | `cache/goaljudge_eval/trace_pins_gcp_goldset_pilot_2026-06-09.json` |
| Execution log | [`docs/research/goaljudge_stage5_goldset_pilot_execution_log.md`](../../../research/goaljudge_stage5_goldset_pilot_execution_log.md) |
| verify_run | 43/43 cases · 33/43 full DOM render · 10 status-feed UI gap |

Status-feed-only IDs: `GJ-001`, `GJ-003B`, `GJ-007`, `GJ-011`, `GJ-014`, `GJ-015`, `GJ-023`, `GJ-031`, `GJ-045`, `GJ-048`.

---

## Re-label trigger

If Stage 4 G5 later fails (κ < 0.8) or plan §8.4 rollback fires, mark affected pilot rows `superseded`
in the sheet `note` column and re-label after rubric revision.
