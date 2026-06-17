---
name: governance-trace-audit
description: >-
  Audit a Langfuse trace from THIS repository's agent runtime (AgentsFramework
  `agent` monorepo) against the governance-triangle intent — the four pillars:
  Recording (BlackBox), Identity (AgentFacts), Validation (GuardRails),
  Reasoning (PhaseLogger) — and produce a verdict report with a per-pillar
  scorecard. Use this whenever the user pastes Langfuse trace JSON (an array of
  observations with run.started / step.N / llm.call / task.completed), or asks
  to "audit", "validate", "review", or "analyze" a trace, run a "governance
  check", "compliance check", "pillar check", or "post-implementation review"
  of telemetry, verify a deploy's traces, or asks whether a trace is "healthy",
  "compliant", or "telling the truth". Also use it as the verification step
  after any telemetry-touching change is deployed, even if the user only says
  "here are the latest traces".
---

# Governance Trace Audit

Audit a production Langfuse trace against the governance-triangle intent and
produce a verdict report. The trace must let a reader answer four questions
from the trace alone — that is the contract this skill enforces:

| Pillar | Question | Primary evidence |
|---|---|---|
| Recording (BlackBox) | What happened? | `step.N` spans, `llm.call`, `tool.{name}`, `step.executed` |
| Identity (AgentFacts) | Who did it? | `task.started` details, `subject` |
| Validation (GuardRails) | What was checked? | `guardrail.checked`, `error.occurred` |
| Reasoning (PhaseLogger) | Why was it done? | `model.selected` rationale, `step.planned` summary, `eval.*` |

The audit validates the **instrumentation**, not the agent's task success. An
agent that failed its task can still produce a fully compliant trace — in fact
the most important thing this audit checks is whether the trace *admits* the
failure (see corrupt-success below).

Two principles govern every judgment you make:

1. **Curate volume, never truth.** The curated view may suppress duplicate
   carriers of a fact, but every fact must have exactly one reliable carrier
   that actually exports. A fact with zero carriers is a seam defect — the
   worst class of finding, because it was almost certainly suppressed on an
   unverified premise.
2. **Honesty over polish.** Relay-time spans with near-zero durations and an
   `event_time` that lags the span `startTime` are *correct* (no-backdating
   rule D-0a). Fabricated-looking precision is the red flag, not honest lag.

> **Inline shadow gate (since the carrier-gate, Phase 1).** The runtime now runs
> an inline, deterministic **carrier gate** at phase boundaries
> (`services/governance/carrier_gate.py`, reading the four-pillar rubric
> transcribed into `trust/governance_carrier_spec.py`). When a phase completes
> missing a required pillar carrier, the gate records a `guardrail.checked` carrier
> with `source: "carrier_gate"`, `outcome: "alert"`, and `would_enforce: true` —
> it **pre-flags the same seam defects this skill audits**, at the moment they
> happen, instead of only post-hoc. This skill stays the source of truth for the
> rubric (the spec is a versioned transcription of it) and the Phase-2 enforce
> oracle; treat any `source: "carrier_gate"` / `outcome: "alert"` carrier as a
> runtime-confirmed seam defect to corroborate, and a `would_enforce: true` one as
> the pipeline already agreeing with your finding. The gate is **shadow/warn only**
> — it never blocks — so the post-hoc audit remains necessary until Phase 2.

## Step 0 — Obtain and shape the trace

The trace usually arrives **pasted as a JSON array** of Langfuse observations.
If the user asks you to fetch instead, Langfuse API creds are in `.env`
(beware stale values — see the repo's known gotcha) and runs are also
verifiable in Cloud Logging via `thread=<thread_id>`.

Before any checks, establish the run's shape — several checks change meaning
depending on it:

- **From-step-0 or resumed?** Look at the lowest `step.N` span. A resumed run
  (lowest step > 0) legitimately has **no** `task.started` — Identity becomes
  UNVERIFIABLE for this trace, not FAIL.
- **Workflow id / run id / thread id** from `run.started` input and event
  `workflow_id` fields — the report is keyed on these.
- **Which steps exist, which have LLM calls, which have tool calls.** Build a
  per-step observation count as you go.

## Step 1 — Corrupt-success check (always first)

This is the headline check; run it before anything else and lead the report
with it. Compare on `task.completed.details`:

- `outcome` vs `goal_met`, `criteria_met`, `unmet_conditions`
- `eval.goal_judge` output: `per_criterion[].evidence` vs the final answer's
  claims

`outcome: "success"` alongside `goal_met: false` is a **corrupt success** —
the agent claimed success the evidence doesn't support. Three of four
production traces audited during this skill's origin session showed exactly
this, including a security task ("no hidden private keys found") where the
grep had silently failed. The severity split matters:

- **Governance caught it** (goal_met false, `unmet_conditions` populated,
  `would_downgrade: true`): the instrumentation WORKED. Report it as a
  prominent run-level finding (verdict honesty), not an instrumentation
  failure. Note `downgrade_applied` — false is the known Stage-2 rollout state
  where the downgrade gate is off.
- **Governance missed it** (judge said goal_met true but the evidence digest
  contradicts the answer, or no `eval.goal_judge` at all on a completed run):
  instrumentation FAIL on the Reasoning pillar — escalate to NON-COMPLIANT.

Also sanity-check the judge's inputs: `conditions_source: "deterministic"`
means the success conditions are prompt fragments, not understood intent —
weight the judge's verdict accordingly and say so in the report.

## Step 2 — Pillar checks

Work through the four pillars using the detailed catalog in
[references/trace-checks.md](references/trace-checks.md) — read it now; it
carries the exact field names, the expected-vs-broken examples from real
production traces, and the incident behind each check. Summary of what each
pillar needs:

- **Recording**: every step span contains its facts; exactly one `llm.call`
  GENERATION per LLM call; one `tool.{tool_name}` per tool call with
  `args_json`, `result`, `latency_ms`; **`step.executed` present with
  `tokens_in`/`tokens_out`/`cost_usd`** — this span is the *only* reliable
  token carrier (the streamed `llm.call` legitimately lacks usage; do not
  flag that, but a missing or token-less `step.executed` is a FAIL).
- **Identity**: `task.started` carries `agent_name`, `agent_version`,
  `agent_facts_id` (from-step-0 runs only). `agent_facts_id` falls back to
  the subject when no registered agent id was passed — note it, don't fail it.
- **Validation**: tool failures appear as `error.occurred` with source/tool;
  guardrail checks visible (clean passes are DEBUG-level — present but quiet).
  Cross-check: did any tool *silently* fail (error exit code but no
  `error.occurred`)?
- **Reasoning**: every `model.selected` has `rationale`, `alternatives`,
  `decision_id`; `step.planned` appears **once per distinct plan** with
  `plan_summary`/`plan_fingerprint`/`plan_changed: true` (re-emissions of an
  unchanged plan must NOT appear — that's the dedup working); `eval.goal_judge`
  present on completed runs.

## Step 3 — Mechanics checks

The structural invariants, full detail in the reference file:

- **obs/step ≤ 8** (curated-view target; was ~13 before curation)
- **No `tool.called` observations** (suppressed duplicate of `tool.{name}`)
- **`step.executed` IS present** (must never be suppressed — token seam)
- **Join keys**: tool `tool_call_id` is `"{step}:call_…"`; `step` matches the
  prefix; `decision_id` on `model.selected` joins to the phase log
- **Honest time**: `event_time` first-class on relayed observations; no
  fabricated start/end (near-zero durations are expected)
- **Real nulls**: `error_type: null`, never the string `"None"`
- `service.name: agent-runtime` in resource attributes

## Step 4 — Write the verdict report

Produce the report in the structure given in
[references/report-template.md](references/report-template.md). The reader is
a deploy reviewer deciding "is this deploy OK and what do I do next?" — two
rules follow from that:

- **Always include a one-line summary** directly under the verdict: it must
  separate instrumentation status from run-level honesty and name the single
  next action (or "nothing actionable"). It should paste cleanly into Slack.
  When a deploy-verification headline (e.g. a seam fix now carrying data) and
  a run-level finding compete for attention, the one-liner leads with the
  instrumentation status — that is what the deploy reviewer asked about.
- **Report size scales with what's wrong.** A clean trace gets the SHORT FORM
  (verdict + one-liner + compact scorecard + "nothing actionable" + a
  one-sentence unverifiable note). Findings get the full template: scorecard
  with verbatim evidence, mechanics table, findings by severity, remediation
  steps that name files (e.g. `middleware/sidecars/black_box_to_telemetry.py`
  `_CURATED_SUPPRESSED` for suppression seams). Don't pad the clean case to
  look thorough — confidence reads as brevity backed by evidence. And don't
  number NOTE-level accepted limitations as separate findings; fold them into
  one line.

Save the report to `docs/reviews/governance_audit_<workflow_id8>_<YYYY-MM-DD>.md`
and show the verdict + one-liner + scorecard inline in your reply — the reply
must be strictly shorter than the saved file (the file is the record, the
reply is the briefing). Verdict scale:

- **COMPLIANT** — all pillars PASS (UNVERIFIABLE allowed only where the run
  shape makes the evidence impossible, e.g. resumed-run Identity)
- **COMPLIANT WITH FINDINGS** — instrumentation sound; run-level findings
  (e.g. corrupt success that the judge caught) or accepted limitations
- **NON-COMPLIANT** — any pillar FAIL, any fact with zero carriers, any
  governance-missed corrupt success

## Judgment notes (learned the hard way)

- A fact being absent from one observation is only a finding if **no**
  observation carries it. Trace the fact to its designated carrier before
  failing it. When a carrier was suppressed "because another observation has
  it", *verify the substitute actually has it* — the token-usage seam defect
  happened precisely because that handoff was assumed, not verified.
- Don't audit from memory of how the pipeline *should* work — quote the trace.
  Every scorecard cell needs verbatim evidence or it's UNVERIFIABLE.
- One contradictory trace outweighs a clean test suite. CI was green during
  every incident this skill encodes.
