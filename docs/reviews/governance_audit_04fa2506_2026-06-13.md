# Governance Trace Audit — 04fa2506 (2026-06-13)

**Run:** workflow (trace) `04fa25065c63459cbc9aa186ecbdff83` · subject `user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX`
**Shape:** **from-step-0** · 1 step (step 0) · 14 observations · 1 LLM step · 0 tool calls
**Context:** representative row (case 000) from the `shadow-2a-r3` 101-row drive — the first **from-step-0** trace audited on the R3 deployment, selected specifically to close the Identity-UNVERIFIABLE gap that the three prior (all resumed) audits could not.
**Verdict: COMPLIANT WITH FINDINGS**

## ⭐ Identity pillar — now VERIFIED (gap closed)

Every prior audit (`3921c61b`, `0b54f4e1`, `4b8c3f68`) was a resumed run with
no `task.started`, leaving Identity UNVERIFIABLE on this deployment. This
from-step-0 run carries it:

```
task.started.details:
  agent_name:     "governance-agent"
  agent_version:  "0.0.0"
  agent_facts_id: "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX"
  task_input:     "Echo back the user name verbatim."
```

All three identity fields present → **Identity PASS**. `agent_facts_id` equals
the subject (the no-`registered_agent_id` resolver fallback —
`registered_agent_id: None`); note, not fail. The R3 deployment's identity
instrumentation is confirmed sound.

## ⚠ Verdict-integrity check (always first)

**FALSE NEGATIVE — judge-quality, same class as the series.** `outcome:
"success"` + `goal_met: false` + `criteria_met: 0.0` on a trivially-correct
echo task. The agent echoed the user name (step_count 1, clean termination,
`task_completion_score: 0.82`), but the judge scored both deterministic
conditions unmet. With `conditions_source: "deterministic"`, the judge scored
the raw fragment "Echo back the user name verbatim" + the generic tail and
still returned 0 — on a one-line echo. This is the fast-tier gpt-4o-mini
judge-quality defect now seen in **four consecutive traces** (the dominant
false-verdict source), not an instrumentation or conditions-provenance
problem. `would_downgrade` follows from goal_met=false — another correct run
that would trip a downgrade if the gate were enabled.

Note the contrast that makes this a judge defect, not a gate/conditions
defect: the **shadow** `eval.task_understanding` produced excellent conditions
for this exact task — "The agent echoed back the user name exactly as
provided" / "no additional text or modifications" — but shadow mode means the
judge consumed the deterministic floor instead. The generated checklist (had
it been consumed) was materially better than what the judge scored.

## R3 schema confirmed on a clean first-attempt generation

`eval.task_understanding.output`: `source: generated`, `mode: shadow`,
`consumed: false`, `attempts: 1`, `rejected_conditions: []` — the R3 telemetry
schema present and correct on a clean generation. Combined with the
double-rejection capture verified in audit `4b8c3f68`, both R3 telemetry paths
(clean + rejected-with-text) are now confirmed live.

## Pillar scorecard

| Pillar | Question | Status | Evidence (verbatim) |
|---|---|---|---|
| Recording | What happened? | **PASS** | `step.executed` with real tokens `"tokens_in": 1258, "tokens_out": 30, "cost_usd": 0.00674`; one `llm.call`; `integrity_hash` on relayed events; full step.0 span tree |
| Identity | Who did it? | **PASS** ✅ | `"agent_name": "governance-agent", "agent_version": "0.0.0", "agent_facts_id": "user_01KQ0FRZ…"` on `task.started` — **first verified Identity on this deployment** |
| Validation | What was checked? | **PASS** | 3× `guardrail.checked` present (input + TU gate + output); TU gate passed (`attempts: 1`); no tool calls so no `error.occurred` expected |
| Reasoning | Why was it done? | **PASS** (instrumentation) | `model.selected` with rationale/alternatives/decision_id; one `step.planned` (`plan_changed: true`); BOTH evaluators present. Judge VERDICT is a false negative (finding #1) but the instrumentation recorded it faithfully — Reasoning-pillar *instrumentation* is sound |

All four pillars PASS at the instrumentation level — the first all-PASS
scorecard in the series, enabled by the from-step-0 shape. The judge's wrong
verdict is a run-level finding, not a pillar instrumentation failure (it is
recorded honestly and completely).

## Mechanics

| Check | Result | Note |
|---|---|---|
| obs/step ≤ 8 | ✅ | step 0 carries the full lifecycle; no duplicate carriers |
| Suppressed names absent | ✅ | no `tool.called` / `llm.*ed` / `tool.*ed` |
| step.executed present w/ tokens | ✅ | `1258 / 30` non-zero |
| Honest time | ✅ | event_time first-class; near-zero relayed durations (D-0a) |
| Real nulls | ✅ | `registered_agent_id: null` (real null, resolver fallback), `error: null` |
| service.name | ✅ | `agent-runtime` |

## Findings (by severity)

1. **[MAJOR]** Fast-tier judge false-negatives a trivial echo task. `goal_met:
   false, criteria_met: 0.0` on "Echo back the user name verbatim" with a
   clean echo answer. Fourth consecutive trace showing the gpt-4o-mini judge
   producing verdicts unsupported by the evidence. — Remediation: NOT
   instrumentation. This is the strongest case yet for Stage B
   condition-vs-answer entailment reused judge-side; near-term, the generic
   tail + deterministic-fragment conditions give the fast judge too little to
   anchor on (the shadow generator's conditions were far better — argues for
   the 2b consume flip *after* the grounding exemption lands). Do not enable
   the downgrade gate until the judge stops false-negativing correct runs.
2. **[MINOR]** GIGO — `conditions_source: "deterministic"`: judge scored the
   raw prompt fragment + generic tail. The shadow generator produced a clearly
   better checklist for this task; it was not consumed (shadow mode). This is
   the 2b argument, with a clean illustrative example.
3. **[NOTE]** `branch_coverage: 0.4` on a single-clause echo task is a
   deterministic-floor `_extract_branches` artifact (Stage-C), not meaningful
   here.

## Run-level observations (not instrumentation)

The headline value of this trace is structural: it is the from-step-0 run the
series needed, and it upgrades Identity from UNVERIFIABLE to PASS while
confirming the R3 telemetry schema on a clean generation. The judge
false-negative it also exposes is consistent with the now-established
four-trace pattern and reinforces the Stage-B priority — the conditions
pipeline (R3 + staleness fix) is healthy; the residual false verdicts are the
fast-tier judge.

## Unverifiable in this trace

- **`generated`-mode consumption** — shadow (`consumed: false`); the 2b
  consume path remains unexercised by design until the flip.
