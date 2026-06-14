# Which LLM seam to instrument for eval first

Short answer: **don't pick by gut, and don't instrument all twelve.** Let the *data you already have* tell you where failures actually originate, then instrument the single seam where the most first-failures land. In this repo that decision is essentially free to make, because the trace data needed already exists.

## The decision method: a first-failure / transition failure matrix

The wrong way to prioritize is "which call feels riskiest" or "which one is biggest." The right way is **error analysis on real traces**: count where things *first* go wrong, and instrument the hotspot.

Concretely, build a small offline aggregation over existing run logs:

1. **Pull a sample of real runs** (aim for ~100 traces — the practitioner floor for a meaningful taxonomy; spot-check 10–20 outliers).
2. **For each failed run, attribute the *first* failure** — the first phase/component where the trajectory deviated, not the place where the symptom finally surfaced. (First-failure discipline matters: a bad summary three steps downstream is often really a bad routing decision upstream. Counting the symptom instead of the cause sends you to instrument the wrong seam.)
3. **Tally first-failures into a matrix**: rows = last phase that completed cleanly, columns = phase where the first failure occurred; each cell = count of runs. This is the "transition failure matrix" / error-propagation heatmap.
4. **The highest-count cell is your first seam.** That is where a probe earns the most signal per unit of effort.

This is exactly the "analyze → measure → improve" loop: error analysis first, instrumentation second. Instrumenting before you've done the analysis is how teams build expensive evaluators for problems that turn out to be rare.

## Why this is cheap in *this* repo (no new instrumentation needed)

You don't have to add tracing to run this analysis — the substrate is already here:

- **`services/governance/phase_logger.py`** defines `WorkflowPhase` with the exact pipeline stages: `INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION → TOOL_EXECUTION → OUTPUT_VALIDATION → EVALUATION`. These are your matrix's rows and columns.
- **`cache/phase_logs/<run>/phases.jsonl`** already contains per-run phase transitions for real runs (there are dozens of these on disk today), plus `logs/phases.log` (~7 MB).
- **First-failure labels are already computable** from existing component checks: `services/governance/guardrail_validator.py` (input/output policy), `components/goal_judge.py` (`goal_met=false`), and the synthesis validator. You join these to the phase transitions.

So the prioritizer is a **pure offline aggregation** — a new function in `meta/analysis.py` over `phases.jsonl` + first-failure labels. No production code, no live LLM calls. Half a day of analysis, not a sprint of instrumentation across twelve seams.

The twelve LLM calls map onto a much smaller set of seam *types* worth distinguishing in the matrix:

| Seam | File | Phase |
|---|---|---|
| Routing / planning | `components/plan_builder.py`, router | `ROUTING` |
| Main model invocation | `orchestration/react_loop.py` | `MODEL_INVOCATION` |
| Condition generation | `components/task_understanding.py` | (early) |
| Tool calling | `services/tools/delegation_dispatcher.py` | `TOOL_EXECUTION` |
| Input/output guardrails | `services/guardrails.py`, `guardrail_validator.py` | `INPUT_VALIDATION` / `OUTPUT_VALIDATION` |
| Summarization / compaction | `services/summarizer.py` | — |
| Goal judge | `components/goal_judge.py` | `EVALUATION` |

## What to do once the matrix names the seam

Ship the **cheapest possible probe first**, then escalate only if the data justifies it. Reserve LLM-as-judge for persistent failure modes you'll iterate on repeatedly — it's the expensive tier, not the default.

1. **Open-code the hotspot seam's failures** (~100 traces, human-first, stop coding when ~20 consecutive traces add no new failure category). This produces a small testable taxonomy — *specific* failure modes for that seam, not generic "quality" metrics. (Generic metrics like "helpfulness" are worse than useless here; they create false confidence.)
2. **Ship a Tier-A probe immediately**: a 100%-coverage *deterministic* L1 check (the cheap heuristic that catches the dominant failure mode — e.g. "plan non-empty and depth in range," "summary within length bound and non-empty," "tool selected from the allowed set") plus one offline CI regression row seeded from the failures you found. This is most of the value for almost none of the cost, and it runs on every request.
3. **Only then, if the seam shows a persistent generalization failure**, build the expensive tier: a stratified, double-labeled gold set (~200–300 items, dev/test split, freeze and hash the test split) and a sampled LLM-judge (5–10% of traffic), validated to **high TPR/TNR on the held-out test set** before it's allowed to gate anything. Default-off / shadow until it clears its gate — this repo already has that precedent in `services/governance/goaljudge_calibration.py` (precision ≥ 0.90, recall ≥ 0.70, false-downgrade ≤ 0.02).
4. **Drift watch** rides on `meta/drift.py` (`run_full_drift_check`, `compute_cohens_kappa`, `detect_calibration_drift`) once a probe is live.

## What I'd tell you to do this week

1. Write the offline aggregation over `cache/phase_logs/**/phases.jsonl` + existing first-failure labels → produce the transition failure matrix. (~half a day, pure analysis, zero new instrumentation.)
2. Read the top cell. Open-code ~30–50 traces from that seam to confirm the dominant failure mode is real and codable.
3. Ship one deterministic L1 check + one CI regression row for that seam. Done — that's your first instrumented component, chosen by evidence.
4. Re-run the matrix after the fix lands. The hotspot will move; instrument the next-highest cell. Re-run error analysis on fresh traces every 2–4 weeks regardless.

**Net:** the component to instrument first is *whichever seam the first-failure matrix says owns the most real failures* — and you can compute that today from `phases.jsonl` without touching production. With limited time, that one number is worth more than instrumenting all twelve.
