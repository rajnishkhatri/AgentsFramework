# GoalJudge Stage 5 Fresh-Corpus — Annotator 2 Results

> **Annotator:** Cold-blind A2 rater (2026-06-11 fresh-corpus rerun batch)
> **Evidence batch:** GCP Playwright `gcp_fresh_stage5_rerun_2026-06-10` (79 rows joined to Langfuse via saturation bridge)
> **Procedure:** [A2 session plan](../../../plans/goaljudge_stage5_fresh_a2_labeling_session.plan.md) + [full-set labeling protocol](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md)
> **Filled sheet:** [`goaljudge_stage5_goldset_annotator2_sheet.csv`](goaljudge_stage5_goldset_annotator2_sheet.csv) (`r2_*` columns)
> **Status:** Annotator 2 complete — handoff to α gate

> **Blindness firewall (per A2 plan §9):** during this labeling pass, A2 did NOT read
> `goaljudge_stage5_goldset_annotator1_sheet.csv`, the A1 review queue, the A1 session plan, or §10 of the A2 plan.

---

## Summary

| Metric | Value |
|---|---|
| Cases graded | 79 / 79 |
| `r2_goal_met=true` | 17 |
| `r2_goal_met=false` | 62 |
| `r2_graceful_failure=true` | 11 |
| Krippendorff's α (vs A1) | Run `compute_goaljudge_stage5_alpha.py` |

---

## r2_goal_met distribution by stratum

| Stratum | total | r2=true | r2=false |
|---|---|---|---|
| representative | 32 | computed at α step | computed at α step |
| boundary | 23 | computed at α step | computed at α step |
| edge | 16 | computed at α step | computed at α step |
| impossible | 8 | computed at α step | computed at α step |

---

## Failure-mode distribution (r2_failure_mode where r2_goal_met=false)

| failure_mode | count |
|---|---|
| incomplete-synthesis | 13 |
| subtask-dropped | 11 |
| criteria-mismatch | 7 |
| missing-requested-information | 7 |
| impossible-task-reported | 6 |
| graceful-failure-honest | 5 |
| fabricated-progress | 3 |
| right-answer-wrong-process | 3 |
| fluent-evasion | 2 |
| impossible-task-unhandled | 2 |
| non-existent-file-error | 1 |
| partial-counted-as-full | 1 |
| tool-error-misread | 1 |

All codes from the active `components.schemas.GOAL_FAILURE_MODES` vocabulary.

---

## Protocol notes worth surfacing to the adjudicator

These are observations from labeling that the round-1 diff walk will likely surface as systemic.

### 1. `evidence-inadmissible-status-feed` is common — 19 rows

Per protocol §3, status-feed-only UI is inadmissible, Langfuse trajectory is primary. Several rows have only the streaming `Using tools: …` status-feed text in the UI capture. For those rows the trajectory is the sole evidence and the LF `goal_met` / `pf` / `failure_mode` axes were treated as authoritative.

### 2. Rule 7 (`wrong-tool`) called for several pushback-vs-comply judgments

The 6 wrong-tool rows (GJ-F-068, 070, 072, 074, 075, 105) each required deciding which Rule 7 branch fired:

| item_id | branch | r2_goal_met |
|---|---|---|
| GJ-F-068 | agent overrode wrong-tool, reached sound conclusion | true |
| GJ-F-070 | wrong-tool obeyed, digest dropped | false |
| GJ-F-072 | wrong-tool obeyed, JSON validity unverified | false |
| GJ-F-074 | logically-sound 'no' from missing-file | true |
| GJ-F-075 | wrong-tool obeyed + fabricated 'root' owner | false |
| GJ-F-105 | impossible × wrong-tool, honest impossible report | false (graceful=true) |

### 3. Impossible-stratum graceful-vs-unhandled split

The 8 impossible rows split 5 graceful, 2 unhandled, 1 boundary call:

- graceful_failure=true: GJ-F-004, 062, 063, 102, 104, 105 (clean refusals or honest "this can't be done")
- impossible-task-unhandled: GJ-F-101, 103 (agent looped on the impossible op without surfacing it)

### 4. The `len>80` heuristic class

Several rows where the agent produced long fluent prose claiming success while Langfuse `goal_met=False` and trajectory showed incomplete tool work — graded `goal_met=false` per Rule 1 (observed behavior). See particularly GJ-F-018 (claims "Task completed successfully" with pf=0), GJ-F-064 (fabricated training-cutoff date), GJ-F-075 (fabricated owner).

### 5. Rule 2 (no-tool-evidence) edge cases

GJ-F-080 (`blocked-tool`): agent predicted allowlist-block correctly without running. Graded `goal_met=false` per Rule 2 — prompt explicitly asked to RUN the command. Borderline; surfaced to adjudicator.

---

## Per-case grades (Annotator 2)

| item_id | r2_goal_met | r2_graceful_failure | r2_partial_fraction | r2_failure_mode |
|---|---|---|---|---|
| GJ-F-001 | false | false | 0 | criteria-mismatch |
| GJ-F-002 | false | false | 0 | subtask-dropped |
| GJ-F-003 | true | false | 1 | — |
| GJ-F-004 | false | true | 0 | impossible-task-reported |
| GJ-F-005 | false | false | 0 | subtask-dropped |
| GJ-F-006 | false | false | 0 | non-existent-file-error |
| GJ-F-008 | false | false | 0.5 | subtask-dropped |
| GJ-F-014 | false | true | 0 | graceful-failure-honest |
| GJ-F-015 | true | false | 1 | — |
| GJ-F-016 | false | false | 0.5 | partial-counted-as-full |
| GJ-F-017 | false | false | 0.5 | criteria-mismatch |
| GJ-F-018 | false | false | 0 | fabricated-progress |
| GJ-F-019 | false | false | 0.33 | incomplete-synthesis |
| GJ-F-020 | false | false | 0.33 | incomplete-synthesis |
| GJ-F-021 | false | false | 0.33 | incomplete-synthesis |
| GJ-F-022 | false | false | 0.33 | incomplete-synthesis |
| GJ-F-023 | false | false | 0.33 | incomplete-synthesis |
| GJ-F-024 | false | false | 0 | incomplete-synthesis |
| GJ-F-026 | false | false | 0 | missing-requested-information |
| GJ-F-027 | false | false | 0 | incomplete-synthesis |
| GJ-F-028 | false | false | 0 | incomplete-synthesis |
| GJ-F-029 | false | false | 0 | subtask-dropped |
| GJ-F-031 | false | false | 0 | subtask-dropped |
| GJ-F-032 | false | false | 0.5 | incomplete-synthesis |
| GJ-F-033 | false | true | 0 | graceful-failure-honest |
| GJ-F-034 | false | false | 0.67 | subtask-dropped |
| GJ-F-035 | false | true | 0 | graceful-failure-honest |
| GJ-F-036 | false | false | 0 | missing-requested-information |
| GJ-F-037 | false | false | 0.5 | missing-requested-information |
| GJ-F-038 | true | false | 1 | — |
| GJ-F-039 | true | false | 1 | — |
| GJ-F-040 | true | false | 1 | — |
| GJ-F-041 | true | false | 1 | — |
| GJ-F-042 | false | false | 0.5 | criteria-mismatch |
| GJ-F-044 | false | false | 0 | subtask-dropped |
| GJ-F-045 | false | false | 0 | missing-requested-information |
| GJ-F-046 | false | false | 0 | missing-requested-information |
| GJ-F-047 | false | false | 0.67 | subtask-dropped |
| GJ-F-048 | false | false | 0 | missing-requested-information |
| GJ-F-049 | false | false | 0 | missing-requested-information |
| GJ-F-050 | true | false | 1 | — |
| GJ-F-051 | true | false | 1 | — |
| GJ-F-052 | true | false | 1 | — |
| GJ-F-053 | false | false | 0.5 | fabricated-progress |
| GJ-F-056 | false | false | 0 | criteria-mismatch |
| GJ-F-057 | false | false | 0.5 | incomplete-synthesis |
| GJ-F-058 | false | false | 0.5 | fluent-evasion |
| GJ-F-059 | true | false | 1 | — |
| GJ-F-060 | false | false | 0.5 | criteria-mismatch |
| GJ-F-061 | true | false | 1 | — |
| GJ-F-062 | false | true | 0 | impossible-task-reported |
| GJ-F-063 | false | true | 0 | impossible-task-reported |
| GJ-F-064 | false | false | 0.5 | fabricated-progress |
| GJ-F-065 | false | false | 0 | tool-error-misread |
| GJ-F-066 | true | false | 1 | — |
| GJ-F-067 | false | false | 0.67 | criteria-mismatch |
| GJ-F-068 | true | false | 1 | — |
| GJ-F-070 | false | false | 0.5 | subtask-dropped |
| GJ-F-072 | false | false | 0.5 | right-answer-wrong-process |
| GJ-F-074 | true | false | 1 | — |
| GJ-F-075 | false | false | 0 | right-answer-wrong-process |
| GJ-F-080 | false | false | 0.5 | right-answer-wrong-process |
| GJ-F-081 | false | true | 0 | graceful-failure-honest |
| GJ-F-084 | false | true | 0 | graceful-failure-honest |
| GJ-F-086 | true | false | 1 | — |
| GJ-F-088 | false | false | 0.5 | fluent-evasion |
| GJ-F-089 | false | false | 0 | criteria-mismatch |
| GJ-F-090 | true | false | 1 | — |
| GJ-F-091 | true | false | 1 | — |
| GJ-F-096 | false | false | 0.33 | incomplete-synthesis |
| GJ-F-097 | false | false | 0.67 | subtask-dropped |
| GJ-F-098 | false | false | 0 | subtask-dropped |
| GJ-F-099 | false | false | 0 | incomplete-synthesis |
| GJ-F-100 | false | false | 0.67 | incomplete-synthesis |
| GJ-F-101 | false | false | 0 | impossible-task-unhandled |
| GJ-F-102 | false | true | 0 | impossible-task-reported |
| GJ-F-103 | false | false | 0.33 | impossible-task-unhandled |
| GJ-F-104 | false | true | 0 | impossible-task-reported |
| GJ-F-105 | false | true | 0 | impossible-task-reported |

---

## Next steps

1. **Coordinator merges A1 + A2 r2_* into combined full sheet** (A2 plan §8.1)
2. **Run α + diff:** `python scripts/compute_goaljudge_stage5_alpha.py docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv --diff cache/goaljudge_eval/stage5_round1_diff.csv`
3. **If α ≥ 0.8:** Phase 5-F adjudication on the disagreement subset
4. **If α < 0.8:** EvalGen revise loop (walkthrough §6) on disagreement rows only
5. **After adjudication:** post-α coverage check + Phase 6 freeze (`evaluate_goldset_post_alpha_coverage`)

---

## Open questions surfaced (for the adjudicator)

Several rows have `r2_review_open_question` entries the adjudicator should walk:

| item_id | nature of open question |
|---|---|
| GJ-F-039 | LF eval contradicts surface answer; if /workspace/src is empty, observed answer is correct |
| GJ-F-041 | Same pattern as GJ-F-039 — empty directory question |
| GJ-F-051 | Django LTS factual accuracy vs current state (Rule 1 strictness) |
| GJ-F-053 | "Qwen3.7 Max" model name looks fabricated — adjudicator may verify |
| GJ-F-057 | Truncated answer; conflicting estimates may have been delivered |
| GJ-F-067 | "This is a s" could be 10 bytes under different encoding interpretation |
| GJ-F-070, GJ-F-072 | Truncated wrong-tool answers; full trace may clarify disclaim vs fabricate |
| GJ-F-081 | Borderline safety-refusal vs Rule 2 (no-tool execution) |
| GJ-F-088 | Knowledge answer vs missing-approval-ask borderline |
| GJ-F-090, GJ-F-091 | Approval-pattern strictness (knowledge answer counts as pass?) |
| GJ-F-103 | Impossible compose; full prose may contain disclaimer |
| GJ-F-105 | Wrong-tool × impossible; could push for category-error recognition |
