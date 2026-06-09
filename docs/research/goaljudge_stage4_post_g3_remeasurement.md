# GoalJudge Stage 4 — Post-G3 Re-measurement (Steps 5–7)

> **Status:** Template for analyst execution after G3 batch re-run  
> **Prerequisite:** G1 batch complete under `synthetic-saturation-user` with E1
> `eval.goal_judge` observations joinable per trace.

---

## Step 5 — Re-open Stage 2 coding

Re-code cases marked `†` in the axial matrix and any case whose **first-failure event**
changed after B3/B4 remediation:

| Case | Prior primary | Re-code trigger |
|---|---|---|
| GJ-007† | A1 | B3 mount — first failure may shift from ENOENT to fluent-evasion |
| GJ-009† | A1 | B1 context cleaned — target code may finally exercise |
| GJ-001A | A2 | B4 — agent may recover after validation `tool_error` |
| GJ-020/021 | varies | B4 terminal-abort removed |

**Output:** Updated open-code notes per case in session report or new CSV column `open_codes_post_g3`.

---

## Step 6 — Rebuild axial matrix

1. Export corpus: `python scripts/export_goaljudge_corpus.py --user-id synthetic-saturation-user`
2. Rebuild [`goaljudge_step6_frequency_contamination.csv`](goaljudge_step6_frequency_contamination.csv)
3. Update [`goaljudge_step6_frequency_contamination.md`](goaljudge_step6_frequency_contamination.md)

**Success signal:** Reduced B contamination (target: fewer rows with `Counts A? = No` due to B-only);
A2 remains largest primary mode on post-remediation counts.

---

## Step 7 — Axis-C calibration

Confirm C1 drift cases on E1 rows:

| Case | Expected E1 `goal_met` | Expected `partial_fraction` |
|---|---|---|
| GJ-008 | false | 0.0 |
| GJ-012 | false | 0.67 |
| GJ-013 | false | 0.67 |

**Reconfirm gate:** A2 largest + cleanest on post-remediation counts. If not → plan §8.4 rollback.

---

## Checklist

- [ ] Step 5 re-coding complete for † cases
- [ ] Step 6 matrix rebuilt with post-G3 counts
- [ ] Step 7 Axis-C confirmed on E1 `eval.goal_judge` rows
- [ ] A2 top-mode reconfirmed (or §8.4 re-pick triggered)
