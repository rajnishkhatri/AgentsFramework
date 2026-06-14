# Which LLM seam should we instrument for eval first?

Short version: **don't pick by gut.** The skill's Phase 0 has one job — *let the data
name the seam* — and the data is already on disk. Build the **transition failure
matrix** over `phases.jsonl`, re-attribute the terminal sink to the true first-failure
origin, and instrument the **highest-count counted cell**. "We have a dozen LLM calls"
is a harm story; a counted cell is a decision. The rule that governs this whole step:

> **Picking the seam by gut feel is the most common way an eval effort wastes its
> 60–80%.** Plausible harm ≠ the highest-count first-failure cell.

I ran the actual aggregation against this repo while writing this — results below.

---

## The method (transition failure matrix — PDF §8.3 error-propagation index)

This is a **pure offline aggregation**, no new instrumentation. Inputs already exist.

1. **Rows = "From State"** — the last `WorkflowPhase` that completed cleanly.
2. **Columns = "In State"** — the state where the *first* failure occurred.
3. **Cell (i, j)** = count of failed traces whose first failure happened in state *j*
   right after state *i* completed.
4. **The highest-count cell is where the next probe earns the most.**

States are the repo's real `WorkflowPhase` enum (`services/governance/phase_logger.py`),
already logged per-workflow to `cache/phase_logs/<wf>/phases.jsonl`. Use the **graph
execution order**, not the enum declaration order — the enum declares `OUTPUT_VALIDATION`
after `EVALUATION`, but the graph runs output validation around the model call:

```
initialization → input_validation → routing → model_invocation
→ output_validation → tool_execution → evaluation → continuation → completion
```

First-failure attribution reuses checks that already exist — `synthesis_validator`
(`components/synthesis_validator.py`), `guardrail_validator`
(`services/governance/guardrail_validator.py`), and `goal_judge goal_met=false`
(`components/goal_judge.py`) — so no new signal is invented.

### Two caveats the matrix throws at you (both bit me on this repo's data)

- **(a) Thin data is directional, not gospel.** You want ≥100 traces for a stable read.
  This repo currently has **72 workflows** in `cache/phase_logs/`. A 2-hour
  hand-aggregation over 72 is still worth it — treat it as directional and pull more
  traffic before promoting anything past Tier-A.
- **(b) The attribution sink.** Failures pile into a terminal `completion`/`evaluation`
  cell. You **must re-attribute** them to their true origin using the first-failure
  signals *before* reading the top cell, or the matrix points everywhere at once.

---

## What the real aggregation showed (ran it on the 72 workflows here)

**Raw matrix (before re-attribution):**

| From State | In State (first failure) | Count |
|---|---|---|
| tool_execution | **completion** | 32 |
| output_validation | **completion** | 16 |
| initialization | **completion** | 1 |

72 workflows; 49 had a failure, 23 were clean. End-event outcome distribution:
`ok`=1427, `failed`=33, `partial`=21, `rejected`=2.

**This is the trap.** Every one of the 49 first-failures attributes to `completion`,
because in this log the per-step phases all end `ok` and the verdict
(`failed`/`partial`/`rejected`) is only ever **stamped at the terminal `completion`
phase** (the one exception: a single `rejected` on `input_validation`). The matrix is
pointing at `completion` — a sink — which tells you *nothing* about which seam to fix.

**The honest finding from the dig:** in this repo today, **`phases.jsonl` alone cannot
re-attribute the sink, and neither can `decisions.jsonl`.** `decisions.jsonl` carries
`phase` (only `routing` / `evaluation`), `description`, `rationale`, `confidence` — it's
the Reasoning-pillar log, with **no validator pass/fail outcome and no first-failure
origin**. So before this matrix can name a seam, you have to do the re-attribution join:

> For each failed `workflow_id`, look up the first-failure signal that actually fired —
> `guardrail_validator` reject (→ input/output guardrail seam), `synthesis_validator`
> flip (→ pre-judge gate), `goal_judge goal_met=false` (→ goal-judge seam) — keyed by
> `trace_id`/`workflow_id` from `eval_capture`/`eval_telemetry` and
> `cache/goaljudge_eval/` + `cache/black_box_recordings/`. *That* origin is the In-State,
> not `completion`.

That join is the planned `meta/analysis.py` aggregation deliverable. Until it lands, do
it by hand for the 49 failed workflows — it is exactly the 2-hour pass the skill tells
you to run even on thin data.

---

## So, concretely, what to do first

1. **Don't instrument anything yet.** The top raw cell (`tool_execution → completion`,
   32) is an artifact of the sink, not a real signal. Instrumenting tool-execution off
   this number would be the "instrument by vibes" mistake in disguise — it just *looks*
   data-driven.

2. **Do the re-attribution join (≈2 hours) first.** For each of the 49 failed
   `workflow_id`s, attribute the first failure to the validator that actually fired,
   using the existing signals above. This converts a sink-dominated matrix into a real
   From×In matrix. This is the single highest-leverage action right now.

3. **Instrument the seam under the highest *re-attributed* cell** — and only that one.
   Given the outcome mix (33 hard `failed` + 21 `partial`), the live candidates are the
   goal/evaluation seam and the output-validation/synthesis gate; the join will decide
   between them. Whichever wins, take it through the spine:
   - **Phase 1** — name the *real* seam (the model decision may be upstream of the named
     component) and defend its altitude in one sentence (span for a single call; **trace**
     for routing/planning where quality is trajectory-dependent). Confirm Recording is
     wired with a scoring-complete payload.
   - **Phase 2–3** — open-code ≥100 traces (pull more real traffic past today's 72),
     label first-failures, cluster into 5–6 **binary** categories.
   - **Phase 4 — ship Tier-A and stop:** an L1 deterministic per-category check in
     `services/` (no framework imports) on 100% of that seam's traffic + one frozen
     `<seam>_benchmark_v1.json` CI regression row. **Most seams should stop here.** Reach
     for the judge track (Phases 5–7) only if Tier-A shadow data proves persistent
     failures worth a gating judge — the way GoalJudge earned it and Guardrails never did.

4. **Backfill the gap so next time is cheap.** Land the `meta/analysis.py` matrix
   function *and* ensure first-failure origin is captured at the failing phase (not only
   stamped at `completion`), so the prioritizer is a one-command read instead of a manual
   join. That's what makes "which seam next?" a 5-minute question on the next pass.

---

## The one-paragraph answer to give the team

We have a dozen LLM calls and limited time, so we will not choose by which one *feels*
riskiest. We will build the transition failure matrix from the `phases.jsonl` logs we
already have (72 workflows — directional, we'll pull more), find the highest-count
*first-failure* cell, and instrument that seam first with the cheapest thing that catches
its failures: a 100%-coverage deterministic check plus one frozen CI regression row.
There's a catch I already verified in our data: every failure currently attributes to the
terminal `completion` phase, so the raw top cell is a sink artifact, not a signal. The
real first job — about two hours — is the re-attribution join that maps each of our 49
failed runs to the validator that actually fired (`guardrail_validator`,
`synthesis_validator`, `goal_judge goal_met=false`). Only after that join names a counted
cell do we instrument — and we save the expensive LLM-judge track for after Tier-A shadow
data proves a seam needs it.

---

### Repo anchors used

- `services/governance/phase_logger.py` — `WorkflowPhase` enum (confirmed members:
  initialization, input_validation, routing, model_invocation, tool_execution,
  evaluation, continuation, output_validation, completion).
- `cache/phase_logs/<wf>/phases.jsonl` — 72 workflows; per-step `phase`+`outcome`, verdict
  stamped at `completion`.
- `cache/phase_logs/<wf>/decisions.jsonl` — 125 files; Reasoning-pillar (`phase`,
  `description`, `rationale`, `confidence`); **no first-failure origin** → cannot
  re-attribute alone.
- First-failure signals: `components/synthesis_validator.py`,
  `services/governance/guardrail_validator.py`, `components/goal_judge.py`.
- `cache/goaljudge_eval/`, `cache/black_box_recordings/` — eval/Recording substrate for
  the `trace_id` join.
- `meta/analysis.py` — exists; the matrix aggregation is the planned function to land.
