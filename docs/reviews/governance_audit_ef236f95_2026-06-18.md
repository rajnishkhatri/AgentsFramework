# Governance Trace Audit — ef236f95 (2026-06-18)

**Run:** workflow `ef236f957b6c4e64a723bee71d857d5b` · run `a37cf5e5659a4efba01b7ebd281f0a73` · thread `c5f62baf-d2b1-410c-9d61-17544739ac88`
**Shape:** resumed at step 3 · 2 step spans (3–4) · 20 observations
**Deploy:** `agent-backend-combined` rev `00085-dam` (`mem` tag, `MEMORY_ENABLED=true`, image `ce577d0`)
**Verdict: COMPLIANT WITH FINDINGS**
> **Instrumentation PASS (memory.recalled + memory.stored carriers verified on authed mem tag) · run failed its goal but governance caught it (`goal_met: false`, `would_downgrade: true`) · next: nothing actionable for Piece C deploy — memory wiring is live; promote `mem` tag when ready.**

## ⚠ Corrupt-success check (always first)

**CORRUPT SUCCESS — CAUGHT BY GOVERNANCE.** `task.completed` reports `outcome: "success"` while `goal_met: false` and `unmet_conditions: "['my son name is garvit']"`. The `eval.goal_judge` agrees: `goal_met: false`, evidence `"The final answer does not acknowledge or respond to the name 'Garvit' directly."` with `would_downgrade: true` / `downgrade_applied: false` (Stage-2 gate off). Instrumentation worked — the trace admits the failure. This is a run-level honesty finding, not an instrumentation defect.

## Memory deploy gate (Piece C §3d — primary verification)

| Carrier | Status | Evidence (verbatim) |
|---|---|---|
| `memory.recalled` | **PASS** | step 3: `"user_id": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX", "count": "3", "query_len": "21"` |
| `memory.stored` (live) | **PASS** | step 4: `"user_id": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX", "key": "a37cf5e5659a4efba01b7ebd281f0a73"` |
| `memory.stored` (shadow autocapture) | **PASS** | `"proposed_only": "True", "key": "profile", "type": "semantic", "salience": "0.8"` |
| Recall content in prompt | **PASS** | `llm.call` input includes `"Relevant context you remember about this user:\n- Task: Remember that I prefer all measurements in metric units.\nAnswer: Got it!…\n- Task: What measurement units do I prefer?\nAnswer: You prefer all measurements in metric units."` |

The stale-image trap (rev `00083-wal`, zero carriers) is **resolved** on rev `00085-dam`.

## Pillar scorecard

| Pillar | Question | Status | Evidence (verbatim) |
|---|---|---|---|
| Recording | What happened? | **PASS** | `"tokens_in": 1456, "tokens_out": 34, "cost_usd": 0.0002388` on `step.executed` (step 3); `memory.recalled` + `memory.stored` present; one `llm.call` GENERATION |
| Identity | Who did it? | **UNVERIFIABLE** | Resumed at step 3 — no `task.started` by shape. `run.started` carries `"subject": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX"`; memory carriers carry matching `user_id` |
| Validation | What was checked? | **PASS** | `guardrail.checked` ×6: `carrier_gate` pass (`"missing_carriers": "[]"`); `output_scan` pass (`"blocked": false`); `task_understanding_gates` failed attempts (shadow, not enforced) |
| Reasoning | Why was it done? | **PASS** | `model.selected`: `"rationale": "steady-state-fast (step=3, errors=0, …)"`, `"alternatives": "['gpt-4o']"`; `step.planned`: `"plan_changed": true`; `eval.goal_judge` present |

## Mechanics

| Check | Result | Note |
|---|---|---|
| obs/step ≤ 8 | ⚠️ | ~11 obs under `step.3` (6 guardrails + recall + plan + model + llm + executed) — above curated target; not a seam defect |
| Suppressed names absent | ✅ | No `tool.called` |
| step.executed present w/ tokens | ✅ | `tokens_in: 1456, tokens_out: 34` |
| tool_call_id join | N/A | No tool calls this turn |
| Honest time (event_time) | ✅ | Relay spans carry `event_time` lagging `startTime` (expected) |
| Real nulls | ✅ | `"error_type": null` on `task.completed` (not string `"None"`) |
| service.name | ✅ | `"service.name": "agent-runtime"` |

## Findings (by severity)

1. **[MINOR] obs/step above curated target** — evidence: 11 child observations under `step.3` vs ≤8 target — remediation: none required; guardrail DEBUG carriers inflate count by design.

## Run-level observations (not instrumentation)

- Task input was `"my son name is garvit"` (a remember turn, not the scripted metric-units recall test). Recall still fired (`count: 3`) and prior metric-units memories appeared in the LLM prompt — cross-turn memory is working.
- `conditions_source: "deterministic"` on `step.planned` / `eval.goal_judge` — success conditions are prompt fragments, not understood intent; weight the judge accordingly.
- `eval.task_understanding` in shadow mode (`"consumed": false`) — grounding gate rejected proposed conditions; fell back to deterministic conditions.
- `downgrade_applied: false` despite `would_downgrade: true` — known Stage-2 rollout state.

## Unverifiable in this trace

- **Identity (`task.started` / `agent_facts_id`)** — resumed at step 3; no `task.started` carrier by shape. A from-step-0 run on the same `mem` tag would prove full Identity pillar.
- **Earlier steps (0–2)** — not in this curated window; metric-units remember/recall turns likely ran in prior traces on the same thread (evidence: recalled context in prompt).

Accepted by design: `llm.call` GENERATION carries usage (not a seam defect); near-zero relay span durations; shadow autocapture `proposed_only` carriers.
