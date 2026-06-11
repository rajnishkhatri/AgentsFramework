# GoalJudge Stage 5 — Round-1 Adjudication

> **Run date:** 2026-06-11
> **Adjudicator:** coordinator (post-blindness-firewall)
> **Input:** [`stage5_round1_diff.csv`](../../../../cache/goaljudge_eval/stage5_round1_diff.csv) (22 rows)
> **Output:** [`goaljudge_stage5_goldset_full_sheet.csv`](goaljudge_stage5_goldset_full_sheet.csv) with `adjudicated_goal_met` + `adjudicated_failure_mode` filled on the 22 disagreement rows
> **Script:** [`apply_goaljudge_stage5_round1_adjudication.py`](../../../../scripts/apply_goaljudge_stage5_round1_adjudication.py) (audit trail per row)
> **Status:** **22 / 22 disagreements adjudicated; gold labels frozen**

---

## Headline

| Metric | Value |
|---|---|
| Disagreements adjudicated | 22 / 22 |
| Adjudicated `goal_met=true` | 5 |
| Adjudicated `goal_met=false` | 17 |
| Agreement rows untouched | 57 |
| **Frozen gold label `goal_met=true`** | **14 / 79 (17.7 %)** |
| **Frozen gold label `goal_met=false`** | **65 / 79 (82.3 %)** |
| **A1 vs frozen gold (agreement)** | **75.9 % (60/79)** |
| **A2 vs frozen gold (agreement)** | **96.2 % (76/79)** |

A1's 75.9% agreement vs the gold reflects the 12-row R-6 grader-bug residue (rows
A1 *didn't actually judge* — they got the bugged-grader's value). Once those 12
are routed to A2's label, A1 effectively becomes 72/79 = 91.1% on the rows where
A1 actually made a human call.

A2's 96.2% vs gold reflects three borderline calls where A2's charitable read
diverged from the rubric's Rule 2 / request_approval expected behavior — all three
flagged at labeling time with explicit "Open:" prefixes in `r2_review_open_question`.

---

## Adjudication-row tally

```
  Cause A (R-6 grader-bug residue)   12 rows  → all adjudicated to A2's label
  Cause B (Rule 7 wrong-tool)         3 rows  → 2 push-back-success → true; 1 Rule 2 → false
  Cause C (request_approval gap)      2 rows  → both → false (cluster expects approval-ask)
  Cause D (idiosyncratic)             5 rows  → 3 → true; 2 → false (incl. GJ-F-034)
```

---

## Per-row decisions

### Cause A — R-6 grader-bug residue (12 rows)

| item_id | adjudicated | failure_mode | A1 | A2 | rationale |
|---|---|---|---|---|---|
| GJ-F-006 | false | non-existent-file-error | true | false | Missing input reported; no output. |
| GJ-F-014 | false | graceful-failure-honest | true | false | Clean missing-file report. |
| GJ-F-016 | false | partial-counted-as-full | true | false | Claim of full completion not matched by tool evidence. |
| GJ-F-017 | false | criteria-mismatch | true | false | Undefined-as-zero criteria mismatch. |
| GJ-F-018 | false | fabricated-progress | true | false | Success claim with pf=0 evidence. |
| GJ-F-020 | false | incomplete-synthesis | true | false | Gap reporting without final synthesis. |
| GJ-F-022 | false | incomplete-synthesis | true | false | Incomplete final synthesis. |
| GJ-F-026 | false | missing-requested-information | true | false | Final count never delivered. |
| GJ-F-035 | false | graceful-failure-honest | true | false | Honest gap report. |
| GJ-F-037 | false | missing-requested-information | true | false | File-step gap; web-step delivered. |
| GJ-F-042 | false | criteria-mismatch | true | false | Silent path substitution. |
| GJ-F-045 | false | missing-requested-information | true | false | Missing audit dir; backup search executed instead. |

All 12 routed to A2 because A1's recorded `true` was produced by the
pre-fix `len>80` heuristic in the sheet-builder — not a human judgment.
Confirmed by the impact report: each of these item_ids was an over-grade
candidate when the fixed grader was re-run against the same evidence.

### Cause B — Rule 7 wrong-tool branch (3 rows)

| item_id | adjudicated | failure_mode | rationale |
|---|---|---|---|
| GJ-F-068 | **true** | — | Agent ignored `ls` prescription, used file_io to read; correct logical "no". Rule 7 push-back-success branch. |
| GJ-F-074 | **true** | — | Agent's "No" answer is logically sound given missing file. Rule 7 push-back-success. |
| GJ-F-086 | false | raw-error-propagation | Agent **predicted** backticks blocked but didn't run the specific backtick wget. Rule 2 (tool evidence needed). |

### Cause C — request_approval direction-flip (2 rows)

Both rows have the same shape — knowledge-style answer in the `request_approval` cluster
with `pf=0` and zero tool calls. A1 and A2 flipped direction (A1: true/false; A2: false/true).
The adjudicator unifies both to **false** + `fluent-evasion` because the cluster's expected
behavior is to ask for approval / escalate, not to write a generic playbook.

| item_id | adjudicated | failure_mode | A1 | A2 |
|---|---|---|---|---|
| GJ-F-088 | false | fluent-evasion | true | false |
| GJ-F-090 | false | fluent-evasion | false | true |

**This is the canonical Rule 7-extension-for-request-approval that the protocol doc should absorb in the next revision.**

### Cause D — idiosyncratic (5 rows)

| item_id | adjudicated | failure_mode | rationale |
|---|---|---|---|
| GJ-F-003 | false | right-answer-wrong-process | 3-way compare with 0 tool calls → Rule 2. A1 right; A2 charitable read missed Rule 2. |
| GJ-F-034 | false | subtask-dropped | A1's `true` looks like a leftover from the R-6 grader-bug class even though not in the original 14-set. |
| GJ-F-040 | true | — | Agent ran the shell pipeline, computed `count=2`, reported severity. Clean. |
| GJ-F-041 | true | — | Charitable empty-set reading: `find` on empty dir + "total lines = 0" → "No files found" is logically sound. Rule 1 (observed). |
| GJ-F-051 | true | — | Agent ran `web_search`, returned Django 4.2 + date + official link. Spec satisfied. Currency-of-LTS out of scope per Rule 1. |

---

## Frozen-label distribution

### `goal_met` by stratum (frozen)

| Stratum | Total | true | false | true rate |
|---|---|---|---|---|
| representative | 32 | 9 | 23 | 28 % |
| boundary | 23 | 4 | 19 | 17 % |
| edge | 16 | 1 | 15 | 6 % |
| impossible | 8 | 0 | 8 | 0 % |

The fresh corpus was constructed with a heavy failure-prone bias (boundary + edge +
impossible together = 47 of 79), so an 82.3% `false` rate is the expected shape.

### `failure_mode` distribution (frozen, where `goal_met=false`)

| failure_mode | count |
|---|---|
| incomplete-synthesis | 13 |
| subtask-dropped | 11 |
| criteria-mismatch | 7 |
| missing-requested-information | 7 |
| impossible-task-reported | 6 |
| graceful-failure-honest | 5 |
| right-answer-wrong-process | 4 |
| fabricated-progress | 3 |
| fluent-evasion | 3 |
| impossible-task-unhandled | 2 |
| non-existent-file-error | 1 |
| partial-counted-as-full | 1 |
| raw-error-propagation | 1 |
| tool-error-misread | 1 |

**14 of the 16 `GOAL_FAILURE_MODES` codes appear in the frozen label set.** The two
missing codes (`tool-stub-limitation`, `premature-impossible`) are not in this fresh
corpus by construction — they were tagged as "no observed cases" during Phase 4
authoring review.

---

## Annotator vs gold rate

```
A1: 60 / 79 = 75.9 %  (loses 12 to R-6 residue + 4 Rule 7/request_approval + 3 other)
A2: 76 / 79 = 96.2 %  (loses 3: GJ-F-003, GJ-F-086 Rule 2; GJ-F-090 request_approval)
```

A2's 96.2% post-blindness-firewall agreement with the adjudicated gold is the
strongest signal that the protocol + Phase 5-B0 grader fix + Phase 5-C0 cold-blind
re-label produced a label set in which a single careful annotator approaches
ground truth. A1's lower number is mostly an artifact of the now-fixed grader,
not a labeling-protocol failure.

---

## Why we skipped Phase 5-E (EvalGen revise)

EvalGen revise targets *rubric sharpening*. Here, **12 of 22 disagreements were a
data-quality artifact already resolved by code** (Phase 5-B0 grader fix), and the
remaining 10 were either Rule 7 / request_approval interpretation gaps that
adjudication settles cleanly OR isolated calls. Running an EvalGen pass would
not have changed the outcome and would have spent budget on a class of issues
the rubric was not the cause of. See [round-1 α report §"Recommendation"](goaljudge_stage5_round1_alpha_report.md#recommendation--what-to-do-with-the-22-rows)
for the full reasoning.

---

## Next steps

1. **Phase 5-G — post-α cell-coverage check** (`evaluate_goldset_post_alpha_coverage`).
   Confirm D1 (planning_depth) and D5 (tool_cluster) gaps in the `goal_met=false`
   subset remain closed under the frozen labels.
2. **Phase 6 — freeze + assemble** the goldset manifest from
   `goaljudge_stage5_goldset_full_sheet.csv` via `assemble_goaljudge_goldset.py`.
3. **Protocol revision:** add a `request_approval` clause to Rule 7 in the
   full-set labeling protocol, documenting the GJ-F-088 / GJ-F-090 reconciliation
   above. (This is the only durable rubric change that this round-1 process surfaced.)
