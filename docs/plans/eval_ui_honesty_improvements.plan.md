---
type: plan
title: 'Eval UI — Honesty & Triage Improvements'
description: 'The trace-explainability plan made three things first-class in telemetry:'
tags: [plan]
---

# Eval UI — Honesty & Triage Improvements

> **Status:** PROPOSED (2026-06-12). Future workstream — not yet scheduled.
> **Origin:** Manual review of two production eval-UI screenshots during the
> trace-explainability GCP smoke (runs `5b1607f4…` "free disk space" and the
> audit-files run). The trace pipeline now exposes goal-judge verdicts, source
> tags, and token usage natively (see
> [trace_explainability_optimization.plan.md](trace_explainability_optimization.plan.md)),
> but the **eval UI does not surface them** — so the UI inherits the trace's most
> dangerous property: *looking successful while being judged a failure.*
> **One-line:** Make the eval UI tell the truth at a glance — surface the
> goal-judge verdict, distinguish generated vs deterministic understanding,
> de-emphasize recovered errors, and collapse repetition — so a skim conveys the
> same conclusion a full read would.
> **Owner:** frontend (me) + thin backend wire checks.
> **Constraint:** readability/honesty only. The canonical BlackBox JSONL +
> compliance bundle remain the audit record; this changes presentation, never
> the recorded truth (same boundary as the curated Langfuse view).

---

## 1. Why now

The trace-explainability plan made three things first-class in telemetry:
- trace-level scores (`task_completion_score`, `goal_met`, `criteria_met`,
  `unmet_conditions`) on `task.completed`,
- `conditions_source: generated | deterministic` on `eval.task_understanding` /
  `step.planned`,
- native token usage on `llm.call` (pending the `stream_options` smoke).

`grep` over `frontend/components` confirms **none of the verdict/score fields are
rendered anywhere** — the only file mentioning `goal_met` is `TaskList.tsx`
incidentally; there is no verdict component, and `run_view_reducer.ts` tracks
only `streaming | complete | error`, with no notion of a *judged* outcome,
`conditions_source`, or token usage. The value those telemetry fields were built
for (triage-without-opening) is stranded in Langfuse and never reaches the
product surface.

The review found the eval view rendering *"I have successfully created the three
configuration files"* in normal prose immediately above *"I cannot complete the
task as requested"* — at identical visual weight, with no outcome chrome. That is
the corrupt-success problem reproduced in the UI.

---

## 2. Findings → phases (priority order)

### Phase 1 — Verdict banner (E-V1) — **highest priority**
**Finding #1 + #5.** The run has no visible verdict. Surface the goal-judge
outcome as a header banner on the completed run, tinted by outcome:

- Fields: `task_completion_score`, `goal_met` (bool), `criteria_met` (fraction),
  `outcome`, `unmet_conditions` (list). All already on `task.completed` /
  `eval.goal_judge` in the wire payload.
- Tint: green when `goal_met && outcome==success`; **amber/"partial" when
  `outcome==success` but `goal_met==false`** (the corrupt-success case — this is
  the one the banner exists to catch); red on error/rejected.
- `unmet_conditions` shown as a short bullet list under the score.
- **Wire check first:** confirm `task.completed` / goal-judge fields reach the
  frontend wire types (`frontend/lib/wire-types.ts`) and the BFF SSE; if the
  domain→AG-UI translator drops them, that's the RED gap to close before any
  component work.

*Files:* new `frontend/components/chat/RunVerdictBanner.tsx`; extend
`run_view_reducer.ts` with a `verdict` slot folded from the terminal event;
render at the top of the run view.

### Phase 2 — Source-tagged understanding (E-V2)
**Finding #2.** `TaskUnderstandingCard.tsx` presents deterministic-fallback
conditions (prompt fragments re-chunked, e.g. *"Plan and execute this step by
step"*) with the same authority as LLM-generated ones.

- Render `conditions_source` as a visible chip: **"AI-understood"** (`generated`)
  vs **"literal fallback"** (`deterministic`).
- When `deterministic`, soften the card (muted styling + a "couldn't infer
  intent — using the prompt verbatim" note) so a weak fallback doesn't read as a
  confident understanding.
- Surface `confidence` if present.

*Files:* `frontend/components/chat/TaskUnderstandingCard.tsx`; ensure
`conditions_source` + `confidence` are on the understanding wire payload.

### Phase 3 — Recovered-error styling (E-V3)
**Finding #3.** `ThinkToolInput` / `ShellToolInput` validation errors render as
raw Pydantic-style cards, undifferentiated from successes (`think errored` with a
literal `Input should be 'hypothesis', 'risk', 'decision' or 'observation'`).

- Style tool-call cards whose result is an `Error:` as a **recoverable-error
  chip** (muted, collapsed by default), distinct from a run-fatal error.
- **Backend bug to fix in the same phase:** the `think` tool's `category` enum
  rejected the model's `"plan"` value. Either widen the enum or fix the prompt so
  the model isn't fighting the schema — the validation error in the trace is a
  real contract mismatch, not just a display issue.

*Files:* `frontend/components/tools/ToolCard.tsx`,
`frontend/lib/translators/tool_event_to_renderer_request.ts`; backend `think`
tool schema (locate via `grep -rn ThinkToolInput`).

### Phase 4 — Repetition collapsing (E-V4)
**Finding #4.** The "free disk space" run made ~6 near-identical
`find / -name analytics` shell calls; at one full-height card each, a real run is
an endless scroll of identical failures. The curated Langfuse view dedups
unchanged plans; the UI has no equivalent.

- Collapse consecutive runs of identical/near-identical tool calls into a single
  card with a count ("4 similar shell errors — expand"), mirroring the relay's
  plan-dedup intent.
- Keep every individual call available on expand (never hide the record — same
  rule as the curated view: collapse *volume*, not *truth*).

*Files:* `run_view_reducer.ts` (fold adjacent same-signature tool events),
`ToolCard.tsx` (grouped/count variant).

---

## 3. Cross-cutting principle

Every phase curates **presentation**, never the recorded record — identical to
the `LANGFUSE_RELAY_CURATED` boundary. The BlackBox JSONL, replay, and compliance
bundle stay complete; collapsing/softening is UI-only and always expandable. A
skim must convey the *same conclusion* a full read would — the banner's job is to
make a judged failure impossible to mistake for a success.

## 4. Sequencing

Phase 1 alone closes the highest-risk gap (corrupt-success invisible in the UI)
and should ship first even if 2–4 wait. Each phase is independent and
TDD RED-first (the eval-UI suite already has `understanding_edit_flow.test.tsx`,
`run_view_reducer.test.ts`, `ToolCard.stories.tsx` as patterns to extend). Verify
via the `agentsframework-playwright` skill (chromium smoke, never the full T1
tier).

## 5. Out of scope

Token-usage *rendering* in the UI is deferred until the `stream_options` fix is
confirmed in a production trace (tracked in the telemetry plan). Once usage lands
on `llm.call`, a per-generation token chip is a natural Phase 5 here.
