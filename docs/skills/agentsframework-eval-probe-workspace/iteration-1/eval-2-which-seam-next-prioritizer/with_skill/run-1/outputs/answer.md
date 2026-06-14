# Which LLM call to instrument first — and how to decide

Short answer: **don't pick by gut.** With a dozen seams and limited time, the wrong move is to instrument the call that *feels* riskiest. The right move is to let the phase log tell you where failures actually originate, using the **transition failure matrix** (the seam prioritizer). It's a one-shot offline aggregation over data the runtime already writes — no new instrumentation — and it pays for itself by stopping you from spending your scarce eval budget on a seam that isn't the bottleneck.

This is Phase 0 of the eval-probe workflow, and it's the one phase you must not skip when time is tight, because it decides where the other 60–80% of your effort lands.

---

## The method: build the transition failure matrix

The repo logs every `WorkflowPhase` transition to `phases.jsonl` (one JSON object per line, under `cache/phase_logs/<workflow_id>/`). Each `phase_end` event carries `phase`, `outcome`, and `workflow_id`. That is all you need.

- **Rows** = "From State": the last phase that completed cleanly.
- **Columns** = "In State": the phase where the **first** failure occurred.
- **Cell (i, j)** = count of failed runs whose first failure happened in state *j* right after state *i* completed.
- **The highest-count cell is the seam to instrument first** — that's where a probe catches the most real failures per unit of effort.

States are the real enum (`services/governance/phase_logger.py`), in graph-execution order:

```
INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION
→ TOOL_EXECUTION → OUTPUT_VALIDATION → EVALUATION → COMPLETION
```

(Use graph order, not the enum *declaration* order — the enum declares `OUTPUT_VALIDATION` after `EVALUATION`, but output validation actually runs around the model call.)

### Decision rule

1. Aggregate the matrix.
2. Take the single highest-count first-failure cell.
3. That column names the phase; the seam at that phase (the goal judge at `EVALUATION`, `task_understanding`/condition-gen, `plan_builder` at routing, a tool call at `TOOL_EXECUTION`, the guardrail at `INPUT_VALIDATION`/`OUTPUT_VALIDATION`, the summarizer in compaction) is what you instrument first.
4. Tie-break by **blast radius**, not count: a wrong goal-judge downgrade *corrupts a real success* (high harm), so a near-tie in that column wins over a low-harm cosmetic failure elsewhere.

I ran this against the local `cache/phase_logs/` to make the method concrete.

---

## What the repo's own data shows right now (and the trap in it)

Across 72 workflows in the local phase log:

- 23 ran fully clean.
- 49 failed — and **the first non-ok outcome lands on `completion` in all 49 cases**. Upstream phases (input_validation, routing, model_invocation, tool_execution, evaluation) show essentially zero first-failures (one lone `input_validation` rejection in the full event stream).

Taken naively, the matrix says "instrument completion." **That is the trap, and it's the single most important caveat in this whole exercise.**

`completion` is an **attribution sink**: a run records its failure where it *terminates*, not where quality *first broke*. A fabricated-progress answer, a wrong plan, or a hallucinated tool result all surface as a bad `completion` outcome even though the real first-failure was upstream. So the raw `outcome` field alone gives you a useless matrix — every failure piles into the last column.

**The fix (and it uses only things that already exist):** re-attribute the `completion`/`evaluation` bucket to its true origin using the first-failure signals the repo already computes:

- `services/governance/guardrail_validator.py` → input/output policy first-failures (PII, key leak, injection, over-length).
- `components/synthesis_validator.py` → the pre-judge deterministic gate that flips success→failure *before* the judge.
- `components/goal_judge.py` `goal_met=false` → outcome-judge first-failures.

Join these back onto each failing `workflow_id`, label the **earliest** firing signal as that run's first-failure phase, and *then* build the matrix. Now the 49 `completion` failures redistribute across `evaluation` / condition-gen / tool-execution, and the highest cell becomes meaningful.

---

## Concrete steps (a few hours, no production code)

1. **Confirm sample size.** The local cache has 72 workflows; the method wants **≥100** failing-or-representative traces for a stable matrix. Pull more from production telemetry first, or treat this local pass as directional only. Don't commit your scarce budget off 72 rows.

2. **Aggregate by hand / throwaway script.** The dedicated aggregator (`meta/analysis.py`) does **not** yet have a transition-matrix function (it has `compute_metrics`, `build_optimizer_input`, `_task_error_counts`, etc., but no prioritizer). Until that lands, aggregate directly from `phases.jsonl` with a short script — but still do it. The inputs are all present.

3. **Re-attribute, don't trust raw `outcome`.** Fold in `guardrail_validator` / `synthesis_validator` / `goal_judge` first-failure signals to move failures out of the `completion` sink to their true origin phase. This step is what turns the matrix from noise into a decision.

4. **Read the top cell + apply the harm tie-break.** Highest-count first-failure cell = the seam. If two cells are close, the higher-blast-radius seam (e.g. the goal judge, where a false downgrade destroys a genuine success) wins.

5. **Then start Phase 1 on exactly one seam.** Name it, pick its altitude (span for a single guardrail/summarizer call; **trace** for the goal judge or `plan_builder`, where quality depends on the whole trajectory, not one call), verify `eval_capture.record(target=…)` is firing for it, and proceed to open coding. Do **not** widen to a second seam until the first ships a Tier-A probe (an L1 deterministic check on 100% of traffic + one frozen offline CI regression row).

---

## Why this is the right call under time pressure

- It's **cheap**: zero new instrumentation, one offline aggregation over data you already have.
- It **prevents the expensive mistake**: instrumenting by vibes is the most common way an eval effort burns its 60–80% analysis budget on the wrong seam.
- It's **honest about its own limits**: the raw matrix points at `completion` because that's an attribution artifact, not because completion is broken — and the method has a built-in fix for that using existing validators.
- It **scopes you to one seam**: with limited time, shipping one real Tier-A probe on the true bottleneck beats half-instrumenting three seams chosen by intuition.

So: build the re-attributed transition failure matrix, pick the highest first-failure cell (tie-broken by harm), and instrument that one seam to Tier-A before touching any other. Based on this repo's structure and the harm profile, the **goal judge at the EVALUATION seam** is the strong prior for where that top cell will land once the `completion` sink is correctly re-attributed — but confirm it with the matrix on ≥100 traces rather than assuming it.

### Key files
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/governance/phase_logger.py` — `WorkflowPhase` enum, the matrix's states.
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/cache/phase_logs/<workflow_id>/phases.jsonl` — the input data (`phase`/`outcome`/`workflow_id` per `phase_end`).
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/meta/analysis.py` — where the prioritizer aggregation function belongs (not yet present).
- `/Users/rajnishkhatri/Documents/AgentsFramework/agent/services/governance/guardrail_validator.py`, `/Users/rajnishkhatri/Documents/AgentsFramework/agent/components/synthesis_validator.py`, `/Users/rajnishkhatri/Documents/AgentsFramework/agent/components/goal_judge.py` — the first-failure attribution sources that de-sink the `completion` bucket.
