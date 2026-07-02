# Verdict report template

Save to `docs/reviews/governance_audit_<workflow_id8>_<YYYY-MM-DD>.md`
(workflow_id8 = first 8 chars of the workflow id). Show the verdict, one-line
summary, and scorecard inline in your chat reply — the file is the record, the
reply is the briefing.

**Pick the form by outcome.** Clean trace (corrupt-success CLEAN, no pillar
FAIL, nothing above MINOR) → SHORT FORM. Anything else → FULL FORM. The
report's length is itself a signal: a long report about a clean trace tells
the reader something is wrong when it isn't.

## The one-line summary (both forms, mandatory)

One sentence directly under the verdict, Slack-pasteable, in this shape:

> **Instrumentation <PASS|FAIL> · run honesty <clean|failed-but-caught|MISSED> · <single next action | nothing actionable>.**

Examples from real audits:
- `Instrumentation PASS (token seam verified: 2140/113, 2332/67) · run failed its goal but governance caught it · next: flip the downgrade gate.`
- `Instrumentation FAIL (tokens have zero carriers — step.executed suppressed) · corrupt success caught by judge · next: un-suppress STEP_EXECUTED in the relay.`
- `Instrumentation PASS · run honest · nothing actionable.`

## SHORT FORM (clean trace)

```markdown
# Governance Trace Audit — <workflow_id8> (<YYYY-MM-DD>)

**Run:** workflow `<workflow_id>` · run `<run_id>` · <shape> · <N> obs
**Verdict: COMPLIANT<or WITH FINDINGS>**
> <one-line summary>

| Pillar | Status | Evidence (one quote each) |
|---|---|---|
| Recording | PASS | `"tokens_in": 2140…` on step.executed |
| Identity | UNVERIFIABLE | resumed at step N — no task.started by shape |
| Validation | PASS | all tool results success; real nulls |
| Reasoning | PASS | rationale + one step.planned (dedup ✅) |

Mechanics: all checks pass (obs/step ≤8, joins, honest time, service.name).
Nothing actionable. <One sentence on what this trace cannot prove and what
trace would prove it. One line folding any NOTE-level accepted limitations.>
```

Brevity never silences a contradiction: if anything in the trace LOOKS
contradictory to a reader (e.g. a prior-turn spec says 7 but the read returns
9, or two traces share a workflow id), name it and scope it in ONE clause —
"prior-turn bananas spec (7) vs content (9) is out of scope for this resumed
read window" — even in the short form. A reviewer who trips over it later
will trust the audit less for having omitted it.

## FULL FORM (any finding above MINOR, any FAIL, any corrupt success)

```markdown
# Governance Trace Audit — <workflow_id8> (<YYYY-MM-DD>)

**Run:** workflow `<workflow_id>` · run `<run_id>` · thread `<thread_id>`
**Shape:** <from-step-0 | resumed at step N> · <N> steps · <N> observations
**Verdict: <COMPLIANT | COMPLIANT WITH FINDINGS | NON-COMPLIANT>**
> <one-line summary>

Every evidence cell quotes the trace verbatim (trimmed with `…` as needed) —
a cell without a quote must be UNVERIFIABLE.

## ⚠ Corrupt-success check (always first)

<One of:>
- **CLEAN** — `outcome` and `goal_met` agree; judge evidence supports the final answer.
- **CORRUPT SUCCESS — CAUGHT BY GOVERNANCE** — `outcome: "success"` but `goal_met: false`.
  Instrumentation worked; the run's claim is unsupported. Quote: judge evidence vs answer claim.
- **CORRUPT SUCCESS — MISSED** — discrepancy present and the judge agreed with it,
  or no `eval.goal_judge` on a completed run. NON-COMPLIANT.

## Pillar scorecard

| Pillar | Question | Status | Evidence (verbatim) |
|---|---|---|---|
| Recording | What happened? | PASS/PARTIAL/FAIL | `"tokens_in": 2140, "tokens_out": 113` on step.executed (step 7) |
| Identity | Who did it? | PASS/UNVERIFIABLE/FAIL | `"agent_name": "governance-agent", "agent_version": "0.0.0"` |
| Validation | What was checked? | PASS/PARTIAL/FAIL | `error.occurred` for shell exit 2 (step 1) |
| Reasoning | Why was it done? | PASS/PARTIAL/FAIL | rationale `"steady-state-fast (step=8, …)"`; one step.planned, plan_changed=true |

## Mechanics

| Check | Result | Note |
|---|---|---|
| obs/step ≤ 8 | ✅/❌ | max <N> (step <K>) |
| Suppressed names absent | ✅/❌ | |
| step.executed present w/ tokens | ✅/❌ | the token-seam check |
| tool_call_id join | ✅/❌ | `"7:call_…"` prefix == step |
| Honest time (event_time, no backdating) | ✅/❌ | |
| Real nulls | ✅/❌ | |
| service.name | ✅/❌ | |

## Findings (by severity)

1. **[CRITICAL|MAJOR|MINOR]** <finding> — evidence: <quote> —
   remediation: <file/flag to change>

<NOTE-level accepted limitations are NOT numbered findings — fold them into a
single closing line ("Accepted by design: llm.call w/o usage; near-zero relay
durations; …"). One home per fact: if something already lives in the
corrupt-success banner or run-level observations (the GIGO/conditions_source
caveat is the usual offender), do NOT also number it as a finding.>

## Run-level observations (not instrumentation)

<Corrupt-success details, judge GIGO caveat when conditions_source=deterministic,
downgrade gate state, silent tool failures the agent talked past.>

## Unverifiable in this trace

<What this run's shape cannot prove (e.g. Identity on a resumed run) and what
trace would prove it.>
```

Verdict rules:

- **COMPLIANT** — all pillars PASS; UNVERIFIABLE only where the run shape
  makes evidence impossible AND the capability was verified on this
  deployment before.
- **COMPLIANT WITH FINDINGS** — pillars sound; MINOR findings and/or
  run-level findings (caught corrupt success, deterministic conditions,
  fallback identity).
- **NON-COMPLIANT** — any pillar FAIL, any CRITICAL finding (zero-carrier
  fact, missed corrupt success, missing judge on a completed run).
