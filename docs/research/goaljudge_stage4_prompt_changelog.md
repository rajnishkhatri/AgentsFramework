# GoalJudge Stage 4 — Prompt Changelog

> **Scope:** A2 · corrupt-success rubric hardening in `prompts/goal_judge_system_prompt.j2`.
> **Status:** PROVISIONAL — ships while validity gates G1–G5 remain open;
> `goal_judge_downgrade_enabled` stays `false`.
> **Spec:** [`goaljudge_stage4_a2_rubric_spec.md`](goaljudge_stage4_a2_rubric_spec.md)
> **Plan:** [`goaljudge_stage4_a2_rubric.plan.md`](../plans/goaljudge_stage4_a2_rubric.plan.md)

---

## A2-corrupt-success (2026-06-08)

**Tag:** `A2-corrupt-success`

**Motivation:** Step 4 binary check for A2 · Decomposition / corrupt-success — *"Is every
required subtask verified by observable tool evidence (not narration), AND does the final
answer's success claim match that evidence?"* ([`goaljudge_step4_axisA_testable_checks.md`](goaljudge_step4_axisA_testable_checks.md),
lines 57–67). GCP synthesis shows C1 drift on GJ-008/012/013 pre-rubric.

**File:** [`prompts/goal_judge_system_prompt.j2`](../../prompts/goal_judge_system_prompt.j2)

### Added

- New step **3 · CORRUPT-SUCCESS / SUBTASK-EVIDENCE (A2 — primary criterion)** after step 2,
  before EVIDENCE-GROUNDING:
  - Subtask decomposition from `task_input` / `success_conditions`
  - Per-subtask observable tool evidence requirement
  - Fail modes (a) unverified subtask + completion claim, (b) partial-as-full, (c) narrated
    progress with no confirming tool result (including prose-after-block — G7)
  - `goal_met=false` + `partial_fraction = verified / total` on fail
  - Explicit ban on `goal_met=true` from completion claim alone

### Modified

| Step | Section | Change |
|---|---|---|
| 4 | EVIDENCE-GROUNDING | Cross-ref step 3: claim-without-evidence = CORRUPT-SUCCESS |
| 6 | PARTIAL COMPLETION | `partial_fraction = verified subtasks / total required subtasks` |
| 7 | Final binarization | Never `goal_met=true` when step 3 CORRUPT-SUCCESS check failed |

### Unchanged

- JSON output shape (`goal_met`, `criteria_met`, `per_criterion`, `rationale`,
  `graceful_failure`, `partial_fraction`)
- IMPOSSIBLE TASKS dual-axis (`graceful_failure` separate from `goal_met`)
- No `failure_mode` field (Stage 5)
- No orchestration / schema changes

### Offline pins

- [`tests/components/test_goal_judge_redteam_offline.py`](../../tests/components/test_goal_judge_redteam_offline.py)
  — `_A2_CORRUPT_SUCCESS_MARKERS` on rendered prompt
- [`tests/fixtures/goaljudge/a2_session_fixtures.py`](../../tests/fixtures/goaljudge/a2_session_fixtures.py)
  — GJ-010/012-shaped fixtures; `target_axes` echoed from registry (F7)
- [`tests/components/test_goal_judge.py`](../../tests/components/test_goal_judge.py)
  — canned A2 partial verdict parse (`partial_fraction=0.67`)
- [`tests/components/test_goal_judge_shadow_offline.py`](../../tests/components/test_goal_judge_shadow_offline.py)
  + [`tests/fixtures/goaljudge/shadow_traces.py`](../../tests/fixtures/goaljudge/shadow_traces.py)
  — offline §8.3 shadow-validation scaffold (recorded verdicts; F7 registry-echo).
  Swap recorded → Langfuse verdicts when G3 + batch land (see spec §10.2).

### Not in this change

- Full A1/A3/A4/A5 criterion sections (Stage 4 v2+)
- Enabling `goal_judge_downgrade_enabled` (Stage 6)
