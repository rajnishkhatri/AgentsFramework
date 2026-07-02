# Trace check catalog

Detailed checks for the governance trace audit. Each check states what to look
for, quotes a real production example (healthy and/or broken), and names the
incident that created it plus the repo files that own the behavior. Field
names are exact — quote them verbatim in scorecard evidence.

## Contents

1. [Observation inventory](#1-observation-inventory)
2. [Corrupt-success check](#2-corrupt-success-check)
3. [Recording pillar](#3-recording-pillar)
4. [Identity pillar](#4-identity-pillar)
5. [Validation pillar](#5-validation-pillar)
6. [Reasoning pillar](#6-reasoning-pillar)
7. [Mechanics](#7-mechanics)
8. [Severity guide](#8-severity-guide)

---

## 1. Observation inventory

Parse the trace into a table before judging anything: for each observation
record `name`, `type`, `depth`, the `step` (from metadata or the `step.N`
name), and which facts it carries. Expected observation vocabulary (post
trace-explainability plan, 2026-06):

| Name | Langfuse type | Carries |
|---|---|---|
| `run.started` / `run.finished` | AGENT / SPAN | run_id, thread_id, subject, terminal status |
| `task.started` | AGENT | task_input, **agent identity** (step-0 runs only) |
| `step.N` | SPAN | step container (no payload — children carry facts) |
| `step.planned` | CHAIN | planning_depth, plan_fingerprint, plan_changed, **plan_summary** |
| `model.selected` | CHAIN | model, reason, **rationale**, **alternatives**, decision_id |
| `llm.call` | GENERATION | input_text, output content, latency_ms (NOT usage — see §3) |
| `tool.{tool_name}` | TOOL | tool_call_id, args_json, result, latency_ms, step |
| `step.executed` | SPAN | model, **tokens_in, tokens_out, cost_usd**, latency_ms |
| `error.occurred` | SPAN | source, tool, error |
| `guardrail.checked` | (SPAN, DEBUG/WARNING level) | guardrail, verdict details |
| `eval.task_understanding` | EVALUATOR | restated_intent, success_conditions, **conditions_source**, confidence |
| `eval.goal_judge` | EVALUATOR | goal_met, criteria_met, per_criterion[], rationale, would_downgrade |
| `task.completed` | AGENT | outcome, scores, goal_met, unmet_conditions, total_cost_usd |

Names you must NOT see (curated suppressions / retired names): `tool.called`,
`llm.started`, `llm.finished`, `tool.started`, `tool.finished`. Seeing any of
these means the curated relay flag is off or regressed
(`middleware/sidecars/black_box_to_telemetry.py`, `LANGFUSE_RELAY_CURATED`).

---

## 2. Corrupt-success check

Compare these `task.completed.details` fields:

```json
{"outcome": "success", "goal_met": false, "criteria_met": 0.0,
 "unmet_conditions": "['Create inventory files with specified contents', ...]",
 "would_downgrade": true, "downgrade_applied": false,
 "task_completion_score": 0.887}
```

That fragment is from a real production run (workflow `6dd81c1d…`): the agent
reported "files created and verified successfully" but had only created two of
four files. **`outcome: success` + `goal_met: false` = corrupt success.**

Then read `eval.goal_judge.output.per_criterion[].evidence` and compare it
against the final answer's claims. Real example of the judge catching a silent
tool failure (workflow `bda76734…`, a security task):

> final answer: "No hidden private keys found in the /workspace directory."
> judge evidence: "the grep command outputs indicate it did not successfully
> search for private keys."

The grep had errored (`unrecognized option`) and the retries' `exit_code: 1`
was ambiguous; the agent answered confidently anyway. The judge caught it —
instrumentation PASS, run-level finding.

Severity routing:

- Judge caught the discrepancy (`goal_met: false`, evidence cites the gap) →
  instrumentation **PASS**, report a prominent **run-level finding**.
- Judge agreed with an unsupported claim, or `eval.goal_judge` absent on a
  completed run → Reasoning pillar **FAIL** → overall NON-COMPLIANT.
- `downgrade_applied: false` while `would_downgrade: true` is the known
  Stage-2 rollout state (downgrade gate off in `goal_judge_downgrade_enabled`)
  — note it, don't fail it.

GIGO caveat to include whenever it applies: `conditions_source:
"deterministic"` means the success conditions are re-chunked prompt fragments
(e.g. "Plan and execute this step by step" as a "condition"), not understood
intent. The judge's percentages inherit that weakness; say so.

---

## 3. Recording pillar

**What happened — answerable from the trace alone.**

### 3a. One `llm.call` GENERATION per LLM call

Each step that invoked the model has exactly one `llm.call` with `input_text`
(full prompt fold), `latency_ms`, and on final turns a `content` in output.
Multiple generations per call or zero generations for a step that clearly ran
the model → FAIL (merge regression in `middleware/telemetry_bridge.py`).

### 3b. `llm.call` has NO usage — and that is accepted

Do not flag missing `tokens_in/tokens_out/usage` on `llm.call`. Incident: the
runtime drives the graph via `astream_events`; under `streaming=True` the
`on_chat_model_end` callback the wire bridge observes carries no
`usage_metadata` (the `.ainvoke` **return value** does, which is why cost was
always right on the canonical record). Two fix attempts proved this is a
LangChain-callback boundary, not a bug to re-fix. Tokens live on
`step.executed` (3d).

### 3c. One `tool.{tool_name}` per tool call

Real healthy example:

```json
{"tool_call_id": "7:call_PQP3P98RKNMAWhzqgqYrBvmB", "tool_name": "file_io",
 "args_json": "{\"operation\": \"read\", \"path\": \"/workspace/stress/apples.txt\"}",
 "step": 7, "latency_ms": 0.096, "result": "{\"content\":\"12\",...}"}
```

Check: args AND result present (a tool span with args but no result is an
orphan), `step` equals the `tool_call_id` prefix, name is `tool.{tool_name}`
(generalizes: `tool.shell`, `tool.think`, `tool.file_io` all observed in prod).

### 3d. `step.executed` present with real tokens — THE seam check

```json
{"model": "gpt-4o-mini", "tokens_in": 2140, "tokens_out": 113,
 "cost_usd": 0.0003888, "latency_ms": 2060.9, "error": null}
```

Every step with an LLM call must have a `step.executed` span carrying
non-zero `tokens_in`/`tokens_out` (zero tokens with a non-empty prompt is a
broken extraction, not a real value). **Incident this check encodes:** Phase 4
suppressed `STEP_EXECUTED` from the curated view on the premise that the wire
`llm.call` carried its tokens; that premise was false (3b), so tokens had
ZERO carriers and vanished from the curated trace entirely. Fixed by
un-suppressing (`_CURATED_SUPPRESSED = {"tool_called"}` in
`middleware/sidecars/black_box_to_telemetry.py`). If `step.executed` is
missing or token-less: Recording **FAIL**, cite this incident.

### 3e. Integrity chain

Relayed observations (CHAIN/SPAN/AGENT from the BlackBox relay) carry
`event_id`, `workflow_id`, `integrity_hash`, `event_time` in their input.
Missing `integrity_hash` on a relayed observation breaks the audit-record
linkage → FAIL.

---

## 4. Identity pillar

**Who did it.**

From-step-0 runs only — `task.started` details:

```json
{"task_input": "...", "agent_name": "governance-agent",
 "agent_version": "0.0.0", "agent_facts_id": "user_01KQ0FRZ..."}
```

- All three identity fields present → PASS.
- `agent_facts_id` equals the subject/user id when no `registered_agent_id`
  was supplied (resolver fallback) — **note it, don't fail it**; a
  registry-backed run should show the registered agent id instead.
- Resumed run (lowest step > 0, no `task.started`) → **UNVERIFIABLE**, state
  why, and recommend a from-step-0 trace if Identity has never been verified
  on this deployment.
- `subject` should also appear in observation metadata throughout.

Owner: `orchestration/react_loop.py` `guard_input_node` (identity hoisted
before the first event); fields default from `AgentConfig.agent_name/version`.

---

## 5. Validation pillar

**What was checked.**

- Tool failures must surface: each failing tool call (result starting
  `Error:` / non-zero `exit_code`) should have a matching `error.occurred`
  span (`{"source": "tool_execution", "tool": "shell", "error": "exit code 1"}`).
  A failing tool with no error event = silent failure → FAIL.
- The **silent-failure cross-check**: scan tool results for errors the agent
  then ignored in its final answer. The private-keys run (§2) is the
  archetype — grep never succeeded, answer claimed a clean scan. The judge
  catching it is Reasoning's job; *recording* the error is Validation's.
- `guardrail.checked` observations: clean input passes are DEBUG level (quiet
  but present — the provable negative for compliance demos); blocked/redacted
  are WARNING. On guarded runs, absence of any guardrail observation →
  PARTIAL (owner: `services/governance/black_box_publisher.py` `_level_for`).
- Sandbox rejections (shell allowlist, metacharacter blocks) appearing as tool
  results are healthy Validation evidence — count them as checks performed.

---

## 6. Reasoning pillar

**Why was it done.**

### 6a. `model.selected` — every step

```json
{"model": "gpt-4o-mini", "reason": "steady-state-fast",
 "rationale": "steady-state-fast (step=8, errors=0, last_err=none, cost_usd=0.0095, plan_depth=L0)",
 "alternatives": "['gpt-4o']", "decision_id": "f9b8ef70-..."}
```

`rationale` + `alternatives` + `decision_id` all present, rationale contains
the reason token plus live context. Routing sanity: step 0 should show
`capable-for-planning`; steady state shows `steady-state-fast`; escalations
should correlate with visible errors.

### 6b. `step.planned` — once per distinct plan, with summary

`plan_changed: true` rows carry `plan_summary` (≤5 titles, ≤120 chars each),
`plan_fingerprint`. **Dedup is the check**: across a multi-step run with an
unchanged plan there must be exactly ONE `step.planned` (12-step prod run
`5b1607f4…` correctly showed one). Multiple identical-fingerprint
`step.planned` exports → dedup regression (`components/plan_builder.py`
fingerprint; relay suppression of `plan_changed: false`). The canonical JSONL
still records every iteration — only the export is deduped.

### 6c. Evaluators

- `eval.task_understanding` near step 0 with `restated_intent`,
  `success_conditions`, `conditions_source`, `confidence`, mode.
- `eval.goal_judge` before `task.completed` with per-criterion evidence (§2).
- Judge evidence must cite the `evidence_digest` (tool facts), not just the
  final answer's own claims.

---

## 7. Mechanics

| Check | Expected | Broken looks like |
|---|---|---|
| obs/step | ≤ 8 (typically 2–7) | ~13/step = curation off |
| Suppressed names | absent (§1 list) | `tool.called` present |
| `tool_call_id` join | `"{step}:call_…"`, prefix == `step` | bare `call_…` on relay events, prefix mismatch |
| Honest time | `event_time` in input, lags span `startTime` by ~0.5–1s; near-zero span durations | span start *before* event_time; plausible-looking fabricated durations |
| Real nulls | `"error_type": null` | `"error_type": "None"` (string) |
| service.name | `agent-runtime` | missing/default resource attrs |
| Metadata size | lean keys ({step, workflow_id, event_id, tool_name, model, subject}) | full details duplicated into metadata (allowlist regression, `middleware/adapters/observability/langfuse_cloud_exporter.py`) |

On honest time, the *why*: Langfuse SDK v4 cannot backdate span starts
(decision D-0a), so relayed observations are stamped at relay-export time and
the authoritative instant rides `event_time`. Near-zero durations and the lag
are the honest representation — flagging them as "broken timing" is the
audit error, not the trace's.

---

## 8. Severity guide

| Severity | Criteria | Examples from real incidents |
|---|---|---|
| **CRITICAL** (→ NON-COMPLIANT) | A fact with zero carriers; governance-missed corrupt success; missing `eval.goal_judge` on completed run | token-usage seam (suppressed carrier + empty substitute) |
| **MAJOR** (pillar FAIL) | Pillar question unanswerable from the trace; silent tool failure unrecorded; missing identity on a step-0 run | pre-fix traces: no tokens anywhere |
| **MINOR** (finding) | Fallback values where richer ones exist (`agent_facts_id`=subject; deterministic conditions); `downgrade_applied: false` while gate rollout pending | observed in every 2026-06 prod trace; expected states |
| **NOTE** | Honest-time lag, near-zero durations, `llm.call` without usage | accepted by design — never escalate |
