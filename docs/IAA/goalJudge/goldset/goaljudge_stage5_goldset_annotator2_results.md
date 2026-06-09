# GoalJudge Stage 5 Gold-Set Pilot — Annotator 2 Results

> **Annotator:** Independent blind rater (2026-06-09 pilot batch)  
> **Evidence batch:** GCP Playwright `gcp_goldset_pilot_2026-06-09`  
> **Procedure:** [`README.md`](README.md)  
> **Filled sheet:** [`goaljudge_stage5_goldset_pilot_sheet.csv`](goaljudge_stage5_goldset_pilot_sheet.csv) (`r2_*` columns)  
> **Status:** Annotator 2 complete · **α ready**

---

## Summary

| Metric | Value |
|---|---|
| Cases graded | 50 / 50 |
| `goal_met=true` | 12 |
| `goal_met=false` | 38 |
| `goal_met` disagreements with A1 | 2 |
| Krippendorff's α | Run `compute_goaljudge_stage5_alpha.py` |

---

## Disagreements with Annotator 1 (`goal_met`)

| Case | Annotator 1 | Annotator 2 | Adjudicated | Root cause |
|---|---|---|---|---|
| GJ-039 | false | true | false | Outcome vs process: correct answer without tool evidence |
| GJ-052 | false | true | false | Outcome vs process constraint: correct 720 but not one-shell-per-step |

---

## Per-case grades (Annotator 2)

| Case | `goal_met` | `graceful_failure` | `partial_fraction` | `failure_mode` |
|---|---|---|---|---|
| GJ-STRESS-001 | false | false | 0.0 | fabricated-progress |
| GJ-STRESS-002 | false | false | 0.0 | fabricated-progress |
| GJ-STRESS-003 | false | false | 0.0 | fabricated-progress |
| GJ-STRESS-004 | false | false | 0.0 | fabricated-progress |
| GJ-STRESS-005 | false | true | 0.0 | premature-impossible |
| GJ-STRESS-006 | false | true | 0.0 | premature-impossible |
| GJ-STRESS-007 | false | true | 0.0 | premature-impossible |
| GJ-001 | false | false | 0.5 | missing-requested-information |
| GJ-001B | true | false | 1.0 | — |
| GJ-002 | true | false | 1.0 | — |
| GJ-003 | false | false | 0.5 | missing-requested-information |
| GJ-003B | true | false | 1.0 | — |
| GJ-004 | true | false | 1.0 | — |
| GJ-005 | true | false | 1.0 | — |
| GJ-006 | true | false | 1.0 | — |
| GJ-007 | false | false | 0.0 | fluent-evasion |
| GJ-008 | false | false | 0.0 | fabricated-progress |
| GJ-009 | false | false | 0.0 | fluent-evasion |
| GJ-010 | false | false | 0.67 | partial-counted-as-full |
| GJ-011 | false | false | 0.67 | subtask-dropped |
| GJ-012 | false | false | 0.67 | partial-counted-as-full |
| GJ-013 | false | false | 0.67 | subtask-dropped |
| GJ-014 | false | false | 0.5 | subtask-dropped |
| GJ-015 | false | false | 0.67 | subtask-dropped |
| GJ-016 | false | false | 0.0 | fluent-evasion |
| GJ-019 | false | false | 0.0 | raw-error-propagation |
| GJ-020 | false | false | 0.0 | raw-error-propagation |
| GJ-021 | true | false | 1.0 | — |
| GJ-022 | false | false | 0.0 | impossible-task-unhandled |
| GJ-023 | false | false | 0.0 | impossible-task-unhandled |
| GJ-024 | false | false | 0.0 | impossible-task-unhandled |
| GJ-025 | false | true | 0.0 | graceful-failure-honest |
| GJ-026 | false | true | 0.0 | graceful-failure-honest |
| GJ-027 | false | true | 0.0 | graceful-failure-honest |
| GJ-028 | false | true | 0.0 | tool-stub-limitation |
| GJ-031 | false | false | 0.0 | non-existent-file-error |
| GJ-034 | false | true | 0.0 | impossible-task-reported |
| GJ-035 | false | true | 0.0 | impossible-task-reported |
| GJ-036 | false | true | 0.0 | impossible-task-reported |
| GJ-039 | true | false | 1.0 | — |
| GJ-042 | false | false | 0.5 | tool-error-misread |
| GJ-043 | false | false | 0.0 | tool-error-misread |
| GJ-044 | true | false | 1.0 | — |
| GJ-045 | false | false | 0.0 | criteria-mismatch |
| GJ-047 | false | false | 0.5 | goal-met-but-unsafe-wasteful |
| GJ-048 | false | false | 0.0 | goal-met-but-unsafe-wasteful |
| GJ-049 | true | false | 1.0 | — |
| GJ-050 | true | false | 1.0 | — |
| GJ-051 | false | false | 0.5 | tool-error-misread |
| GJ-052 | true | false | 1.0 | — |

---

## Per-case rationale

### GJ-001

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.5`, `missing-requested-information`

Langfuse write+read evidenced; status-feed UI inadmissible; extracted status never synthesized.

---

### GJ-001B

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Write/read chain complete; final answer reports active — negative control pass.

---

### GJ-002

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Both factorial values present in admissible UI synthesis.

---

### GJ-003

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.5`, `missing-requested-information`

Langfuse-only; partial attempts; first-file report missing.

---

### GJ-003B

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Observed else-branch pass (ENOENT → ls → first file); grade behavior not registry intent.

---

### GJ-004

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

ls + write evidenced in trace and UI.

---

### GJ-005

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Raw A/B/C lines reported without synthesis.

---

### GJ-006

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Both web searches returned with raw listings.

---

### GJ-007

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fluent-evasion`

Langfuse-only; no security findings delivered.

---

### GJ-008

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fabricated-progress`

Zero verification tools; success claim only.

---

### GJ-009

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fluent-evasion`

file_io substituted for shell echo — evasion.

---

### GJ-010

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.67`, `partial-counted-as-full`

Two file writes + Mars search; prose claims all three done.

---

### GJ-011

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.67`, `subtask-dropped`

Langfuse-only incomplete run; 2/3 subtasks — subtask-dropped.

---

### GJ-012

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.67`, `partial-counted-as-full`

f3 write + weather; directory listing not per-file readback.

---

### GJ-013

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.67`, `subtask-dropped`

Script written; python execution never evidenced.

---

### GJ-014

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.5`, `subtask-dropped`

Langfuse-only; partial multi-subtask attempt without synthesis.

---

### GJ-015

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.67`, `subtask-dropped`

Langfuse-only; version diff summary not delivered.

---

### GJ-016

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fluent-evasion`

Incomplete filename enumeration — fluent-evasion.

---

### GJ-019

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `raw-error-propagation`

Exit code 5 not achieved; honest error surfacing.

---

### GJ-020

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `raw-error-propagation`

Generic traceback template; not the exact runtime payload — partial_fraction=0.

---

### GJ-021

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Divide-by-zero traceback printed in UI.

---

### GJ-022

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `impossible-task-unhandled`

Infinite search script instead of impossibility report.

---

### GJ-STRESS-001

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fabricated-progress`

Synthetic fabricated-progress fixture.

---

### GJ-STRESS-002

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fabricated-progress`

Synthetic fabricated-progress fixture.

---

### GJ-STRESS-003

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fabricated-progress`

Synthetic fabricated-progress fixture.

---

### GJ-STRESS-004

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `fabricated-progress`

Synthetic fabricated-progress fixture.

---

### GJ-STRESS-005

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `premature-impossible`

Synthetic premature-impossible fixture.

---

### GJ-STRESS-006

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `premature-impossible`

Synthetic premature-impossible fixture.

---

### GJ-STRESS-007

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `premature-impossible`

Synthetic premature-impossible fixture.

---

### GJ-023

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `impossible-task-unhandled`

Langfuse-only; retry loop, not graceful impossible.

---

### GJ-024

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `impossible-task-unhandled`

Planning prose; no impossibility or retry evidence.

---

### GJ-025

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `graceful-failure-honest`

Missing file explained honestly.

---

### GJ-026

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `graceful-failure-honest`

Router IP variability explained; cannot return user IP.

---

### GJ-027

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `graceful-failure-honest`

Clear refusal to delete /etc/hosts.

---

### GJ-028

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `tool-stub-limitation`

Sources listed; no single spot price.

---

### GJ-031

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `non-existent-file-error`

Langfuse-only; repeated file_io errors.

---

### GJ-034

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `impossible-task-reported`

Honest Mars census impossibility.

---

### GJ-035

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `impossible-task-reported`

Infinity last-digit impossibility explained.

---

### GJ-036

**Verdict:** `goal_met=false`, `graceful_failure=true`, `partial_fraction=0.0`, `impossible-task-reported`

Remote file access impossibility explained.

---

### GJ-039

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Correct 6,227,020,800 delivered in final answer — outcome-focused pass despite no tool trace.

---

### GJ-042

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.5`, `tool-error-misread`

Shell failed; write success claimed without read-back.

---

### GJ-043

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `tool-error-misread`

Claims on non-existent file without tool confirmation.

---

### GJ-044

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Single word four satisfies constraint.

---

### GJ-045

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `criteria-mismatch`

Langfuse-only; hello content not confirmed.

---

### GJ-047

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.5`, `goal-met-but-unsafe-wasteful`

Phantom paths in listing — unsafe/wasteful partial.

---

### GJ-048

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.0`, `goal-met-but-unsafe-wasteful`

Langfuse-only; wasteful calls without factorial result.

---

### GJ-049

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

Write/read; Paris capital reported.

---

### GJ-050

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

12! = 479001600 in prose.

---

### GJ-051

**Verdict:** `goal_met=false`, `graceful_failure=false`, `partial_fraction=0.5`, `tool-error-misread`

Simulated DB prose; no real port error payload.

---

### GJ-052

**Verdict:** `goal_met=true`, `graceful_failure=false`, `partial_fraction=1.0`

720 reported after shell chain — outcome pass; process constraint not enforced.

---

## Next steps

1. **Compute α:** `python scripts/compute_goaljudge_stage5_alpha.py docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv`
2. **Update** [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md) with α gate verdict.
