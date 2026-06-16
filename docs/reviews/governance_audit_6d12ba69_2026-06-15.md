# Governance Trace Audit — 6d12ba69 (2026-06-15)

**Run:** workflow `6d12ba69cff159f69c3c1d5cfe84388c` · session `session-gj-stress-45-032332ec` · user `synthetic-saturation-user` · from-step-0 · 13 obs · case `FANOUT-independent-gift-shortlist-03` (T3 fan-out, stress revision)

**Verdict: NON-COMPLIANT**

> **Instrumentation FAIL (tokens have zero carriers — no `step.executed` on a completed run) · run honesty CLEAN (outcome=success, goal_met=true, no corrupt-success) · next: confirm whether the T3 fan-out path emits STEP_EXECUTED, then re-audit a single-run trace post-redeploy.**

This trace was selected as the *cleanest available* T3 fan-out trace (the only
independent row whose carriers did not trip the fan_out+decline superposition
guard). It is audited here with an explicit caveat: see Finding 1 — even this
trace is **not provably single-run**, so several cells are UNVERIFIABLE by the
skill's own "one trace == one run" contract.

## Pillar scorecard

| Pillar | Status | Evidence (verbatim) |
|---|---|---|
| Recording | **FAIL** | `step.executed present: False`; only `step.0` span. No token carrier → `tokens_in`/`tokens_out`/`cost_usd` have **zero carriers** on a completed run. |
| Identity | **PASS (with note)** | `agent_name: "governance-agent"`, `agent_version: "0.0.0"`, `agent_facts_id: "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX"`. `registered_agent_id: null` → facts_id fell back to subject (skill §Identity: note, don't fail). `agent_version 0.0.0` is a placeholder worth noting. |
| Validation | **PASS** | 2× `guardrail.checked` present (clean passes, quiet). No `error.occurred`; no silent tool failure detected. Real nulls (no `"None"` strings in error fields). |
| Reasoning | **UNVERIFIABLE** | `model.selected` is well-formed: `rationale: "capable-for-planning (step=0, errors=0, …plan_depth=L1)"`, `alternatives: ['gpt-4o-mini']`, `decision_id: 6b990461…`. Supervisor carrier present: `supervisor_decision: fan_out`, `supervisor_branch_count: 3`. BUT **3× `step.planned`** on a run with one supervisor decision (see Finding 1) — the dedup/one-plan-per-distinct-plan invariant cannot be confirmed. |

## Corrupt-success check (Step 1) — CLEAN

`task.completed`: `outcome: success`, `goal_met: True`, `criteria_met: 1`,
`unmet_conditions: []`, `termination_reason: success`. No corrupt success: the
verdict and the goal signal agree. `would_downgrade: False` (correct — nothing
to downgrade). **Caveat:** `eval.goal_judge.conditions_source: None` — the judge
ran without an explicit conditions source, so weight `goal_met: true`
accordingly (the skill's "deterministic conditions = prompt fragments" warning
applies in spirit; here the source is absent entirely).

## Findings by severity

### Finding 1 — CRITICAL (audit-integrity): trace is not provably single-run
3× `step.planned` and 1× `model.selected` on a trace whose supervisor fired
once. The companion analysis proved the harness reused a **static per-case
`trace_id`**, so Langfuse superimposes reruns under one trace id
(`session-gj-stress-45-…` is also deterministic per case). Even traces that pass
the fan_out+decline guard can be **same-decision superposition** (N runs that
all fanned out). This violates the skill's load-bearing premise — *one
contradictory trace outweighs a clean test suite; one trace must equal one run*.
**Remediation (already implemented, uncommitted):** per-run `freshTraceId()` in
`frontend/e2e/full-stack/planning-stress.spec.ts` + artifact rotation; the
report's `superposition_smell` guard only catches the mixed-decision case and
must be extended to flag **>1 `model.selected` / >1 distinct plan fingerprint**
as same-decision superposition too.

### Finding 2 — FAIL (Recording pillar): no `step.executed` token carrier — ROOT-CAUSED
The skill names `step.executed` (with `tokens_in`/`tokens_out`/`cost_usd`) as
the *only* reliable token carrier; "a missing or token-less `step.executed` is
a FAIL." **Traced to source (2026-06-15), confirmed (a) — the fan-out path emits
no STEP_EXECUTED, not a suppression:**

- The sole `STEP_EXECUTED` emission is in `call_llm_node`
  (`orchestration/react_loop.py:1372`). The T3 fan-out path routes
  `route → supervisor → worker → join → evaluate`, **bypassing `call_llm`
  entirely**, so none of its LLM calls reach that carrier.
- `supervisor_node` (`react_loop.py:2178`, LLM call via `plan_delegations`) and
  `join_node` (`:2399`, LLM call via `llm_service.invoke`) record **no token
  usage at all** — fully invisible in governance telemetry.
- `worker_node` (`:2287`) records only `ERROR_OCCURRED` (`:2289`). Its
  dispatcher `_dispatch_core` (`services/tools/delegation_dispatcher.py:83-94`)
  DOES read `usage_metadata` and compute `cost_usd`, but routes it to
  **`eval_capture`** — a separate eval-dataset sink, NOT the governance
  `step.executed` carrier — and then **drops the counts from its return value**
  (`:95-100`), so the worker node couldn't emit them even if it tried.

**Impact:** a fanned-out run burns **N+2 LLM calls** (1 supervisor + N workers +
1 join) whose tokens/cost are **absent from the governance trace**. This is the
exact class the skill warns about — a fact with zero carriers on its designated
seam, the worst finding class.

**Remediation — IMPLEMENTED 2026-06-15 (uncommitted), tests green:**
1. ✅ `_dispatch_core` returns a `usage` dict (`model/tokens_in/tokens_out/
   cost_usd/latency_ms`) — additive; eval_capture unchanged; sync `task_tool`
   caller unaffected (it ignores the field).
2. ✅ `worker_node` emits one `STEP_EXECUTED` per branch from `result["usage"]`
   (`source: fanout_worker`).
3. ✅ `supervisor_node` (`source: fanout_supervisor`) + `join_node`
   (`source: fanout_join`) capture `usage_metadata` at their LLM call sites and
   emit `STEP_EXECUTED` — only when the LLM was actually consulted (the decline /
   floor paths make no call, so correctly no carrier).
4. ✅ L1 guard `test_fanout_path_emits_step_executed_token_carriers` asserts 1
   supervisor + 3 worker + 1 join STEP_EXECUTED carriers, each with non-null
   token fields. RED→GREEN. Dispatcher contract test extended
   (`test_dispatch_surfaces_token_usage_for_step_executed`). Full T3 CI suite
   143 pass / 1 skip; all 7 fan-out sims pass.

**Status: Finding 2 RESOLVED in code.** Re-audit a single-run fan-out trace
post-redeploy to confirm `step.executed` carriers appear in the live Langfuse
trace (the offline test proves emission; the live trace proves export through
the relay).

### Finding 3 — Reasoning pillar (PhaseLogger) — audited 2026-06-15
The Reasoning pillar was re-audited against PhaseLogger specifically. Three
sub-findings:

- **3a (was the alarm) — `3× step.planned` is NOT a dedup regression. RESOLVED
  by the harness fix.** The catalog (§6b) reads multiple identical-fingerprint
  `step.planned` as a dedup-regression FAIL. Here the multiplicity came from the
  **trace_id superposition** (3 runs blended under one trace_id), not a dedup
  bug — a genuine single run emits the supervisor `step.planned` once. The
  per-run `freshTraceId()` harness fix clears this false alarm.

- **3b — fan-out nodes wrap NO `phase_logger.phase()` span. ACCEPTED NOTE.**
  Every standard node opens a `WorkflowPhase` span; `supervisor/worker/join` open
  none, and there is no `WorkflowPhase` enum value for fan-out. This is a
  named-phase-timing coverage gap, NOT a broken carrier — the path is still
  located by `step.planned` + `STEP_EXECUTED` + the `evaluate` step-meter.
  Deferred: a `WorkflowPhase.FANOUT` enum + relay mapping is more surface than
  the marginal timing benefit warrants. Recorded as an accepted limitation.

- **3c — supervisor decision was logged to only ONE sink. RESOLVED in code.**
  The canonical Reasoning idiom is `log_decision(Decision(...))` → PhaseLogger
  `decisions.jsonl` MIRRORED by a black_box carrier, joined by `decision_id`
  (the MODEL_SELECTED pattern, `react_loop.py:1196-1224`). The supervisor emitted
  only the black_box `step.planned` half — no `decisions.jsonl` row. **Fix:**
  `supervisor_node` now calls `phase_logger.log_decision(Decision(phase=ROUTING,
  description="supervisor: <decision>", rationale=plan.reason,
  alternatives=["fan_out","decline"]))` and reuses its `decision_id` on
  `step.planned`, so the fan-out "why" is answerable from both sinks and
  joinable. Guard: `test_fanout_supervisor_logs_phaselogger_decision`
  (asserts the decisions.jsonl row + matching decision_id across sinks). RED→GREEN.

### NOTE (accepted limitations, folded)
`agent_version 0.0.0` placeholder; `registered_agent_id` null (facts_id
fallback) — both expected for the synthetic stress principal, neither a finding.
Finding 3b (no named fan-out phase span) accepted as above.

## Why this audit is itself caveated

Per the skill, every scorecard cell needs verbatim trace evidence; cells that
depend on the trace being one run are marked UNVERIFIABLE rather than asserted.
A trustworthy T3 governance verdict requires a **single-run trace from the
fixed harness** — which only exists *after* the redeploy with `freshTraceId()`.
This report is therefore the pre-redeploy baseline + the audit-integrity
finding that gates it.
