# Governance Trace Audit — 4b8c3f68 (2026-06-13)

**Run:** workflow `4b8c3f68714444b9a937645cea47e43b` · run `4c666268ae3d41828eeecff4a10d8c1f` · thread `753f2f2a-913b-465b-93fe-d8ec67ccb155`
**Shape:** resumed at step 4 (thread turn ~2; follow-up "what about pakistan?" to a prior "us iran war" turn) · steps 4–6 · 15 observations · 2 LLM steps · 1 tool call (web_search)
**Verdict: COMPLIANT WITH FINDINGS** (instrumentation sound; surfaces a real TaskUnderstanding gate defect on short follow-up tasks)

## ⚠ Verdict-integrity check (always first)

**CLEAN.** `outcome: "success"` + `goal_met: true` + `criteria_met: 1.0`,
and the judge evidence genuinely supports the answer ("provides a detailed
analysis of Pakistan's geopolitical position…"). `branch_coverage: 1.0`,
`unmet_conditions: []`, `would_downgrade: false`. This is the first
fully-clean verdict in the recent series — the agent answered a vague
follow-up well by reusing prior conversation context, and the judge agreed
correctly.

GIGO note unchanged: `conditions_source: "deterministic"` — the judge scored
the raw prompt fragment "what about pakistan?" as condition 1. It worked here
only because the answer is on-topic; the deterministic floor remains weak.

## ⭐ Headline finding: the R3 grounding gate REJECTED a correct shadow artifact

This trace is the first to show the fixed `_content_tokens` gate **firing in
the wrong direction on a real task** — and it is NOT a regression of the
trailing-punctuation bug (that is fixed; verified independently below).

`eval.task_understanding` shows shadow generation exhausting both attempts:

- `attempts: 2`, `consumed: false`, `fallback_reason:
  "TaskUnderstandingValidationError: grounding gate: condition 1 shares no
  content token with the task input"` (×2).
- Both attempts' rejected condition TEXT is captured (R3 bug-#2 fix working):
  - attempt 0 cond 1: `"The answer does not exceed 200 words."`
  - attempt 1 cond 1: `"The answer does not exceed 200 words."`

Reproduced locally against the deployed tokenizer:

```
task "what about pakistan?" → content tokens {what, about, pakistan}
attempt 0:
  cond[0] "...relevant information about Pakistan."     grounds ✅ (pakistan)
  cond[1] "The answer does not exceed 200 words."       grounds ❌ {exceed, words, 200}
  cond[2] "...at least one aspect of Pakistan..."       grounds ✅ (pakistan)
attempt 1 (model quoted 'Pakistan' literally in 0 & 2): cond[1] STILL ❌
```

**Root cause — two compounding properties, neither is the punctuation bug:**

1. **All-or-nothing per-condition grounding.** One ungrounded condition
   discards the ENTIRE artifact. Conditions 0 and 2 grounded perfectly; the
   gate threw all three away because of condition 1.
2. **The model emits a generic length/format condition** ("does not exceed
   200 words") that, by design, shares no vocabulary with the task. On a
   normal multi-clause task there is enough other overlap that this still
   isn't the failure; on a **3-word follow-up** ("what about pakistan?")
   there is almost no groundable vocabulary, so the one generic condition
   sinks the whole checklist.

Retry cannot converge: attempt 1 "fixed" the already-passing conditions
(quoting `'Pakistan'`) while condition 1 — the actual offender — stayed a
generic length constraint. The feedback string ("condition 1 shares no
content token") was TRUE this time (unlike the round-2 punctuation case where
it was false), but the model can't satisfy it without inventing fake task
vocabulary for what is legitimately a generic format rule.

**This is the same class as longterm-plan finding #3.4** ("a lexical gate is a
topicality filter, not an anti-fabrication gate") seen from the opposite
side: here the lexical gate produces a FALSE POSITIVE (rejecting a legitimate
generic condition) on a low-vocabulary task. R3 was scoped to one variable
(punctuation) and explicitly did not touch the all-or-nothing rule; this
trace is the first production evidence that the rule itself over-fires on
short tasks.

**Severity context:** shadow mode, so blast radius is telemetry-only today —
the judge consumed the deterministic floor (`conditions_source: deterministic`)
and scored the run correctly (`goal_met: true`). But under
`success_conditions_source=generated`, this task would have fallen back to the
floor on EVERY attempt, and the shadow gate-pass metric counts this as a
failure — it will drag the 101-row drive's gate-pass rate down for any short
/ low-vocabulary prompt in the goldset.

## R3 punctuation fix — still confirmed working (not implicated here)

To be unambiguous that this is a new finding and not a R3 regression: the
trailing-punctuation defect is fixed. `pakistan` (not `pakistan?`) is in the
task tokens, and conditions 0/2 ground on it cleanly. The rejection is purely
the generic-condition-on-short-task mechanism above. The R3 telemetry schema
is also working perfectly — this trace is the first to exercise the
`rejected_conditions[].conditions` text capture on a REAL double-rejection,
and it carried both attempts' full condition lists (exactly the offline
re-simulation capability bug-#2 was meant to restore).

## Pillar scorecard

| Pillar | Question | Status | Evidence (verbatim) |
|---|---|---|---|
| Recording | What happened? | **PASS** | `step.executed` both LLM steps with real tokens: `"tokens_in": 2892, "tokens_out": 21` (step 4), `"tokens_in": 3436, "tokens_out": 294` (step 5); one `llm.call` per step; `tool.web_search` with `args_json` + `result` + `latency_ms`; `integrity_hash` on every relayed event |
| Identity | Who did it? | **UNVERIFIABLE** (run shape) | Resumed at step 4 — no `task.started`. `"subject": "user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX"` throughout. Still no from-step-0 trace on this deployment |
| Validation | What was checked? | **PASS** | TU grounding gate ran and fired (2 GUARDRAIL rejections captured in the eval span with full text); web_search succeeded (`success`-shaped result, no `error.occurred` expected/present); no silent failures |
| Reasoning | Why was it done? | **PASS** | `rationale`/`alternatives`/`decision_id` on all `model.selected`; one `step.planned` (`plan_changed: true`, `decision_id` populated); BOTH evaluators present; judge verdict provenance-correct and evidence-grounded |

## Mechanics

| Check | Result | Note |
|---|---|---|
| obs/step ≤ 8 | ✅ | step 4 has eval + planned + selected + executed + 1 tool = 5 |
| Suppressed names absent | ✅ | no `tool.called` / `llm.*ed` / `tool.*ed` |
| step.executed present w/ tokens | ✅ | non-zero both LLM steps |
| tool_call_id join | ✅ | `"4:call_pRlqSq9OT0dThdQRyOU2JnOP"` — prefix `4` == `"step": 4` |
| Honest time | ✅ | event_time lags span start; near-zero relayed durations (D-0a) |
| Real nulls | ✅ | `"error": null`, `"error_type": null`, `"failure_mode": null` |
| service.name | ✅ | `agent-runtime` throughout |
| Cost coherence | ✅ | step.executed (0.0004464 + 0.0006918) + prior turn → `total_cost_usd: 0.0090619` |

## Findings (by severity)

1. **[MAJOR]** TaskUnderstanding grounding gate over-fires on short /
   low-vocabulary tasks via the all-or-nothing rule + a generic
   length/format condition. "what about pakistan?" → both shadow attempts
   rejected on condition 1 ("does not exceed 200 words"), artifact discarded,
   fallback to deterministic floor. Evidence:
   `eval.task_understanding.rejected_conditions` (both attempts, full text).
   — Remediation options (one variable at a time, per the plan's discipline):
   (a) **exempt one generic/format condition from grounding** — the cleanest:
   the gate already special-cases provenance (`user_edited` skips grounding);
   a "≤1 condition may be generic" budget mirrors the Stage-B evidence-quote
   null budget and is the same idea applied to the lexical gate;
   (b) tolerate N−1 grounding on short tasks (the round-2 N−1 idea, withdrawn
   then as unnecessary for the punctuation cohort — this trace is the cohort
   where it WOULD help); (c) prompt the generator to ground every condition
   including format ones in the task (fragile — fights the model's sensible
   default). Recommend (a). Add this task to the gate meta-benchmark
   (`gate_benchmark_v1.json`) as a must-accept-after-fix / known-reject-now
   case so the fix is TDD-gated like R3 was.
2. **[MINOR]** Stale-conditions guard works but is invisible on this trace.
   The judge scored "what about pakistan?" against its own conditions (not
   the prior "us iran war" turn's), and `decision_id` is populated —
   consistent with the deployed staleness fix. No defect; noting the fix
   holds on a SECOND distinct multi-turn thread.
3. **[MINOR]** GIGO — `conditions_source: "deterministic"`: judge scored the
   raw prompt fragment. Worked here (on-topic answer); the shadow gate's
   richer checklist was discarded by finding #1, so even the shadow data is
   lost for this task. — Remediation: finding #1's fix recovers the shadow
   artifact, which then feeds 2b.
4. **[NOTE]** Cross-turn context reuse worked well: the agent answered a
   vague 3-word follow-up by carrying the prior turn's US-Iran-war context
   into a Pakistan-focused web_search and synthesis. Healthy multi-turn
   behavior; the judge correctly rewarded it.

## Run-level observations (not instrumentation)

A clean, correct run that nonetheless exposes the next real gate defect. The
ordering matters: R3 fixed the punctuation false-positive; the staleness fix
removed the cross-turn false-negative; this trace surfaces the THIRD
independent way the TaskUnderstanding pipeline mishandles a real task —
the all-or-nothing grounding rule rejecting a legitimate generic condition on
a short prompt. All three are distinct; this one is squarely the
"lexical-gate-is-only-topicality" bound the longterm plan predicted, now with
production evidence and a concrete fix path (generic-condition budget).

Per-turn shadow generation (from the staleness fix) is what made this visible
this fast: every follow-up turn now generates and gates, so low-vocabulary
follow-ups exercise the gate far more often than the old per-thread-once
behavior did.

## Unverifiable in this trace

- **Identity** — still resumed-run only; no from-step-0 trace yet on this
  image. A fresh-thread turn-1 run remains the outstanding smoke step.
- **`generated`-mode consumption** — shadow only (`consumed: false`); the 2b
  consume path is unexercised. Note finding #1 must be fixed BEFORE the flip,
  or short tasks will fall back to the floor in production.
