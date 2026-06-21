---
type: review
title: 'Governance Trace Audit — 3921c61b (2026-06-12)'
description: 'Run: workflow 3921c61bf0024f87b80c26c1b94d7675 · run d5afa7f647684d1885dc7abb896f8e23 · thread 87fbbfa3-1107-465a-b59c-3d33c01a8341'
tags: [review]
---

# Governance Trace Audit — 3921c61b (2026-06-12)

**Run:** workflow `3921c61bf0024f87b80c26c1b94d7675` · run `d5afa7f647684d1885dc7abb896f8e23` · thread `87fbbfa3-1107-465a-b59c-3d33c01a8341`
**Shape:** resumed at step 7 (thread turn 3; steps 0–6 in earlier runs) · steps 7–9 · 17 observations · 2 LLM steps · 4 tool calls
**Context:** first trace audited on the R3-fix deployment (punct-strip + telemetry bugs #1/#2), 2026-06-12 20:48Z
**Verdict: COMPLIANT WITH FINDINGS**

## ⚠ Corrupt-success check (always first)

**MISMATCH PRESENT — BUT INVERTED: judge FALSE NEGATIVE, not corrupt success.**

`task.completed` shows the structural corrupt-success signature —
`"outcome": "success"` alongside `"goal_met": false, "criteria_met": 0.0` —
but the direction is the opposite of the classic case. The agent's claim is
**supported** by the evidence; the **judge's verdict** is the unsupported one:

- Final answer: "The values read from the four inventory files are as follows:
  apples.txt: 12 / bananas.txt: 9 / cherries.txt: 31 / dates.txt: 5" — and the
  judge's own `evidence_digest` confirms every read:
  `file_io({'path': '/workspace/stress/cherries.txt', 'operation': 'read'}) -> {"content":"31",…}` etc.
- Judge evidence: `"The agent did not read cherries.txt, which was not created."`
  — contradicted by the digest two lines above it.
- Judge task framing: it scored this turn's task
  (`"task_input": "Now read all four inventory files back and report each value."`)
  against **turn 1's** success conditions
  (`"success_conditions": ["Plan and execute this step by step: create three inventory files…", …]`).

Root cause is a **cross-turn staleness defect**, not the judge model alone:
TaskUnderstanding (and the deterministic floor conditions) are memoized on the
`task_understanding` state key, which persists across runs via the
checkpointer — so every later turn on a thread is judged against turn 1's
checklist (`restated_intent` in the judge input is turn 1's text verbatim;
`decision_id: ""` on `step.planned` confirms no conditions decision was made
this run). The trace records all of this honestly — the staleness is visible
verbatim in the judge's input — so this is a pipeline finding, not an
instrumentation cover-up. With `goal_judge_downgrade_enabled` off, blast
radius today is telemetry-only (`"would_downgrade": true,
"downgrade_applied": false`), but if the gate were on, this healthy run would
have triggered a model downgrade.

## Pillar scorecard

| Pillar | Question | Status | Evidence (verbatim) |
|---|---|---|---|
| Recording | What happened? | **PASS** | `step.executed` both LLM steps with real tokens: `"tokens_in": 2144, "tokens_out": 113, "cost_usd": 0.0003894` (step 7), `"tokens_in": 2336, "tokens_out": 68` (step 8); one `llm.call` per step; 4× `tool.file_io` with `args_json` + `result` + `latency_ms`; `integrity_hash` on every relayed event |
| Identity | Who did it? | **UNVERIFIABLE** (run shape) | Resumed run — lowest span is `step.7`, no `task.started` (expected). `"subject": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX"` present in metadata throughout. Identity has NOT yet been verified on this deployment — see Unverifiable section |
| Validation | What was checked? | **PARTIAL** | All 4 tool results `"success":true` → no `error.occurred` expected and none present (correct); no silent failures (final answer matches digest). But **no `guardrail.checked` observation** on a run that processed a fresh user message — clean-pass DEBUG visibility absent from export |
| Reasoning | Why was it done? | **PARTIAL** | Mechanism complete: `"rationale": "steady-state-fast (step=7, errors=0, last_err=none, cost_usd=0.0091, plan_depth=L0)"` + `"alternatives": "['gpt-4o']"` + `decision_id` on both `model.selected`; exactly one `step.planned` with `"plan_changed": true` (dedup working); `eval.goal_judge` present before `task.completed`. But the judge verdict is invalid for the scored turn (stale conditions + digest misread — see banner) |

## Mechanics

| Check | Result | Note |
|---|---|---|
| obs/step ≤ 8 | ✅ (intent) | max 9 at step 7, but 4 are *distinct* `tool.file_io` calls — no duplicate carriers; the ≤8 target encodes duplicate suppression (~13/step pre-curation), which holds |
| Suppressed names absent | ✅ | no `tool.called` / `llm.started` / `llm.finished` / `tool.started` / `tool.finished` |
| step.executed present w/ tokens | ✅ | the token-seam check — non-zero on both LLM steps; the `c670e23`/`0a9e049` fix holds on the new image |
| tool_call_id join | ✅ | `"7:call_gdeNOBOIYPyCGvzsr6Op6hi5"` etc. — prefix `7` == `"step": 7` on all 4 |
| Honest time (event_time, no backdating) | ✅ | `step.planned` span start `20:48:51.358Z` vs `"event_time": "2026-06-12T20:48:50.669255+00:00"` — relay stamps later, authoritative instant rides event_time; near-zero relayed durations as designed (D-0a) |
| Real nulls | ✅ | `"error": null`, `"error_type": null`, `"failure_mode": null` — JSON nulls, never `"None"` |
| service.name | ✅ | `"service.name": "agent-runtime"` in resourceAttributes throughout |
| Metadata lean | ✅ | keys limited to {event_id, workflow_id, step, tool_name, model, subject} + SDK attrs |

Cost coherence: `step.executed` costs (0.0003894 + 0.0003912) extend the
thread-cumulative `cost_usd=0.0091` quoted in step 7's routing rationale to the
terminal `"total_cost_usd": 0.0098968` — the carriers agree.

## Findings (by severity)

1. **[MAJOR]** Cross-turn stale success conditions — the judge scored turn 3
   against turn 1's checklist, producing a false `goal_met: false` /
   `criteria_met: 0.0` on a run whose deterministic score was
   `task_completion_score: 0.887`. Evidence: judge input `task_input` = "Now
   read all four inventory files back…" vs `success_conditions[0]` = "Plan and
   execute this step by step: create three inventory files…"; `restated_intent`
   = turn 1 text; `decision_id: ""` on `step.planned`. — Remediation: re-key
   the TaskUnderstanding memo on the current `task_id` in
   `orchestration/react_loop.py` (route_node TU block, `if not understanding:`)
   so a new human turn regenerates conditions; design decision needed for
   `user_edited` artifacts on a new turn (recommend regenerate — the edit
   blessed the old turn's criteria). **Pre-existing defect, not an R3
   regression** — invisible to the 2a drives (fresh thread per task) and to all
   prior single-turn audits; must be fixed before
   `success_conditions_source=generated` or the downgrade gate reach real
   multi-turn users, and before any multi-turn rows enter 2b's α.
   **Remediated same day (local tree, uncommitted):** new state key
   `task_understanding_task_id` binds the artifact to its task; route_node
   regenerates on divergence (including over `user_edited` — the edit blessed
   the old turn's criteria); Decision rationale gains
   "(regenerated: new task on thread)". TDD: two-turn checkpointed wiring
   test red→green (`TestCrossTurnRegeneration`); memoization and edit-resume
   tests unchanged-green. Deploy-boundary note: an in-flight PAUSED run
   checkpointed by the pre-fix image and resumed on the post-fix image will
   regenerate once (binding key absent) — transient, self-healing.
2. **[MINOR]** Judge per-criterion evidence contradicts its own digest —
   `"The agent did not read cherries.txt"` while the digest it was given shows
   `cherries.txt → "31"`. Even granting stale conditions, the fast-tier judge
   misread its evidence (in the safe direction here, but it erodes trust in
   `per_criterion[].evidence`). — Remediation: none immediate; strengthens the
   Stage-B case (evidence-quotes / NLI checking at verdict time).
3. **[MINOR]** GIGO caveat — `"conditions_source": "deterministic"`: the
   conditions are re-chunked prompt fragments, and condition 1 is a mid-list
   truncated branch ("…bananas.txt containing only 7" — the cherries clause
   was swallowed; `branch_coverage: 0.625` reflects it). Known
   `_extract_branches` Stage-C item; weight all judge percentages accordingly.
4. **[MINOR]** No `guardrail.checked` carrier in the export on a run that
   processed a fresh user message (clean passes are DEBUG-level "present but
   quiet"). — Remediation: confirm whether the relay exports DEBUG-level
   guardrail events (`services/governance/black_box_publisher.py` `_level_for`
   → relay path) or verify presence in the canonical JSONL; if the canonical
   record has it, this is an export-visibility gap, not a zero-carrier defect.
5. **[NOTE]** Downgrade gate off (`would_downgrade: true, downgrade_applied:
   false`) — known Stage-2 rollout state. Flag the interaction: finding #1
   makes enabling the gate unsafe for multi-turn threads until fixed.
6. **[NOTE]** `llm.call` carries no usage; relayed spans have near-zero
   durations with lagging `event_time` — both accepted by design (3b, D-0a).
   Never escalate.

## Run-level observations (not instrumentation)

The agent's turn-3 behavior was correct: it read all four files and reported
the values; the digest corroborates every claim. The governance verdict is the
false artifact in this trace. Had this been a classic corrupt success the
instrumentation would have caught it — the irony is that the same machinery,
fed year-old (well, two-turns-old) conditions, manufactured a failure verdict
instead. The trace's honesty is what makes the defect diagnosable: the stale
checklist, the turn-1 restated intent, and the empty `decision_id` are all
right there in the export.

## Unverifiable in this trace

- **Identity** — resumed-run shape: no `task.started`, so
  `agent_name`/`agent_version`/`agent_facts_id` cannot be checked. Identity
  has not yet been verified on *this* deployment (R3 image, deployed
  2026-06-12 evening).
- **R3 telemetry changes** — the headline reason this deploy happened is NOT
  exercised here: TaskUnderstanding generation never fired (memoized from
  turn 1), so there is no `eval.task_understanding` span to confirm the new
  `attempts` accounting or `rejected_conditions[].conditions` text capture,
  and no generation passed through the fixed `_content_tokens` gate.
- **One trace proves both:** send a single message on a **fresh thread** and
  audit that from-step-0 trace. Expected: `task.started` with identity
  fields; `eval.task_understanding` with `"attempts": 1` and
  `"rejected_conditions": []` (keys present — their *presence* is the R3
  schema signature; the old image never emitted a `conditions` key inside
  rejection entries); `conditions_source: "deterministic"` at the judge
  (shadow invariant) while the shadow artifact publishes.
