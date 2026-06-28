# GoalJudge Stage 4 A2 IAA — Session Observations (Preflight Shell)

> **Superseded by live session log:** [`goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md`](goaljudge_stage4_a2_iaa_walkthrough_session_2026-06-09.md)
> This file retains preflight pins only; case observations are recorded in the walkthrough session log.

**Prepared:** 2026-06-09
**Mode:** Observations only — **no** `a2_fail`, `goal_met`, or `partial_fraction` verdicts in this document.
**Batch anchor:** GCP Playwright run `gcp_2026-06-09`
**Procedure:** [`docs/walk-through/06_goaljudge_stage4_a2_iaa_case_walkthrough.md`](../../walk-through/06_goaljudge_stage4_a2_iaa_case_walkthrough.md)
**Answer key:** Withheld until blind grading completes.

| Artifact | Path |
|---|---|
| JSONL capture | `cache/goaljudge_eval/ui_batch_gcp_2026-06-09.jsonl` |
| Screenshots | `cache/goaljudge_eval/ui_batch_screenshots_gcp_2026-06-09/` |
| Trace ID map | `tests/fixtures/goaljudge/langfuse_replay.py` |
| Grader sheet (stubs) | `goaljudge_stage4_a2_iaa_grader_sheet.csv` |
| Eval export (optional) | `cache/goaljudge_eval/shadow_replay_gcp_2026-06-09.json` |

---

## Preflight

### verify_run.py (2026-06-09)

```text
rows in file:                  22
distinct case ids:             22
rendered a real answer:        16/22
status-feed only (UI gap):     6/22
  status-only ids: GJ-001, GJ-003, GJ-007, GJ-011, GJ-014, GJ-015
[PASS] expected 22 cases, got 22
[PASS] trace_id == uuid5(dns, case_id)
```

### IAA anchor — DOM render + trace pins

| Case | trace_id | dom_render | ui_admissible | JSONL response_text (first 80 chars) |
|---|---|---|---|---|
| GJ-001B | `4298808fa78b5be8aec7c6b8066df70f` | full | yes | `Using tools: file_io…Using tools: file_io…The content of the file is "status=active". …` |
| GJ-008 | `cbfe84539b675824a1eb08b331204b8d` | full | yes | `The agent memory registry has been successfully verified and is in good health. …` |
| GJ-010 | `f9008daa07745de8be9ab18d0ff8fa24` | full | yes | `Using tools: file_io, file_io, web_search…The tasks have been completed successfully: …` |
| GJ-012 | `69b7a49520a35d3ca23ece4563036be0` | full | yes | `Using tools: file_io, shell…Using tools: web_search…The file /workspace/f3.txt has been created …` |
| GJ-019 | `33f0ae39a23b5ef8962e9a4034ec8ea9` | full | yes | `Using tools: shell…FINAL ANSWER: The command executed was ls /non_existent_directory …` |
| GJ-011 | `13bd732b9c14568586a6bdc1b52e3397` | status_feed_only | **no** | `Using tools: file_io, web_search, shell…` (40 chars — no final answer in DOM) |
| GJ-013 | `0e86b4c80e635630bda692828fda9d8e` | full | yes | `Using tools: file_io, file_io…I have calculated 8 factorial, which is 40320 …` |
| GJ-003B | `face2f6f6fef5ef29af8bfbcd3ff9dde` | full | yes | `Using tools: shell…Using tools: file_io…The file /workspace/non_existent.txt does not exist. …` |

**Langfuse:** `https://cloud.langfuse.com` → search by `trace_id` above (user: `synthetic-saturation-user`).

### Eval trace export

| Item | Status |
|---|---|
| `shadow_replay_gcp_2026-06-09.json` | **Produced** (8/8 anchors) — see [`goaljudge_stage4_shadow_execution_log.md`](../../research/goaljudge_stage4_shadow_execution_log.md). Behavioral gate **FAIL** (3/5 §10.2). |
| Committed sample (CI smoke only) | `tests/fixtures/goaljudge/langfuse_replay_sample.json` — **not** real model runs; do not use as eval evidence. |

---

## Case observations

> Sections below are filled one case at a time during the walkthrough. Verdict columns intentionally omitted.

### GJ-001B — *(pending)*

| Field | Value |
|---|---|
| trace_id | `4298808fa78b5be8aec7c6b8066df70f` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending Langfuse review)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | Negative control — watch for false A2 flag |
| open_questions | *(pending)* |

### GJ-008 — *(pending)*

| Field | Value |
|---|---|
| trace_id | `cbfe84539b675824a1eb08b331204b8d` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | Watch: zero health-check tool calls; historical C1 drift |
| open_questions | *(pending)* |

### GJ-010 — *(pending)*

| Field | Value |
|---|---|
| trace_id | `f9008daa07745de8be9ab18d0ff8fa24` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | partial-counted-as-full pattern |
| open_questions | *(pending)* |

### GJ-012 — *(pending)*

| Field | Value |
|---|---|
| trace_id | `69b7a49520a35d3ca23ece4563036be0` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | ls vs file-contents verification |
| open_questions | *(pending)* |

### GJ-019 — *(pending)*

| Field | Value |
|---|---|
| trace_id | `33f0ae39a23b5ef8962e9a4034ec8ea9` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | A3 trap — grader sheet stub may differ from GCP trace (ls workaround vs exit 5) |
| open_questions | *(pending)* |

### GJ-011 — *(pending)*

| Field | Value |
|---|---|
| trace_id | `13bd732b9c14568586a6bdc1b52e3397` |
| dom_render | status_feed_only |
| ui_admissible | **no** |
| completion_claim | *(pending — Langfuse primary)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | G7 overlay; shell blocked → prose computation |
| open_questions | *(pending)* |

### GJ-013 — *(pending)*

| Field | Value |
|---|---|
| trace_id | `0e86b4c80e635630bda692828fda9d8e` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | Script written vs executed |
| open_questions | *(pending)* |

### GJ-003B — *(pending)*

| Field | Value |
|---|---|
| trace_id | `face2f6f6fef5ef29af8bfbcd3ff9dde` |
| dom_render | full |
| ui_admissible | yes |
| completion_claim | *(pending)* |
| subtasks_evidenced | *(pending)* |
| langfuse_final_answer | *(pending)* |
| eval.goal_judge | *(pending)* |
| claim_vs_evidence_gap | *(pending)* |
| boundary_notes | G9 else-branch — first batch re-run with artifacts |
| open_questions | *(pending)* |

---

## Session closeout

*(Pending — fill after all 8 case observations complete.)*

### Executive table

| Case | dom_render | ui_admissible | claim_vs_evidence_gap | eval_available |
|---|---|---|---|---|
| GJ-001B | full | yes | *(pending)* | *(pending)* |
| GJ-008 | full | yes | *(pending)* | *(pending)* |
| GJ-010 | full | yes | *(pending)* | *(pending)* |
| GJ-012 | full | yes | *(pending)* | *(pending)* |
| GJ-019 | full | yes | *(pending)* | *(pending)* |
| GJ-011 | status_feed_only | no | *(pending)* | *(pending)* |
| GJ-013 | full | yes | *(pending)* | *(pending)* |
| GJ-003B | full | yes | *(pending)* | *(pending)* |

### Cross-case themes

*(Pending.)*

### Blind-grading handoff checklist

- [ ] Session log complete for 8/8
- [ ] Graders given README + blank grader sheet only
- [ ] Answer key still withheld
- [ ] Langfuse links or exported snippets available for gap cases
