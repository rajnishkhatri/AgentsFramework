# Which LLM seam to instrument for eval first

Short version: **do not pick by gut, and do not pick by "this call is obviously the most important."**
Let the production data name the seam. The single best tool for this is a **transition failure
matrix** (an error-propagation index): count where workflows actually break, and instrument the
highest-count cell first. With a dozen calls and limited time, the whole point is to spend the
limited time on the call that is *empirically* the biggest source of downstream failure, not the one
that feels scariest.

## The method I'd use to decide

### 1. Build a transition failure matrix from data you already log

The repo already records every phase boundary to `phases.jsonl` (written by
`services/governance/phase_logger.py`), keyed on the `WorkflowPhase` enum:

```
INITIALIZATION → INPUT_VALIDATION → ROUTING → MODEL_INVOCATION →
TOOL_EXECUTION → EVALUATION → CONTINUATION → OUTPUT_VALIDATION → COMPLETION
```

That means we can build the matrix with **zero new instrumentation** — the data is already on disk.

Construct it as:

- **Rows** = the last phase/state that completed *cleanly*.
- **Columns** = the phase/state where the *first* failure occurred.
- **Cell** = count of workflows that took that last-clean → first-failure transition.

The **highest-count cell is the seam to instrument first** — that is where a probe buys the most
error reduction per hour spent. A cell that fires 30 times across the corpus is worth far more
attention than one that fires twice, regardless of how important either call "feels."

This is deliberately a *first-failure* attribution, not "any failure anywhere." We care about where
things first go wrong, because that is the call whose output poisons everything downstream. Fixing a
later call that is merely propagating an earlier bad input is wasted effort.

### 2. Reuse the existing first-failure attribution signals — don't invent new ones

We don't need to re-label traces by hand to know where the first failure was. The pipeline already
emits the signals that attribute a failure to a specific seam:

- `synthesis_validator` — output-validation failures.
- `guardrail_validator` (`services/governance/guardrail_validator.py`) — guardrail rejections.
- `goal_judge` with `goal_met=false` (`components/goal_judge.py`) — evaluation/goal failures.

Use those to stamp the first-failure column. This keeps the matrix cheap and consistent with how the
rest of the eval stack already reasons about failures.

### 3. Re-attribute the "attribution sink" before reading the top cell

One trap: failures tend to *pile up* in a terminal state like `EVALUATION` or `COMPLETION` simply
because that's where they surface, even though they originated earlier (a bad `ROUTING` decision or a
weak `MODEL_INVOCATION` output that only the goal judge later catches). Before you read off the
winning cell, **re-attribute those sink failures back to their true origin** using the first-failure
signals above. Skip this and the matrix will point at "evaluation" for everything, which tells you
nothing.

### 4. Caveats on reading the result

- **Sample size:** you ideally want ~100+ workflows for a stable read. With limited data, a 1–2 hour
  hand-aggregation over whatever traces exist (e.g. 70–80 workflows) is still *directional and worth
  doing*. A thin, real count beats a confident guess.
- **Plausible harm is a hypothesis, not a count.** "The summarizer output feeds the reasoning trace,
  so it's clearly the highest-stakes call" is a story you should *test* against the matrix, not a
  reason to skip it. The matrix frequently surprises you — the scary call is often robust, and a
  boring router or validator is quietly eating the corpus.

## What to actually do (concrete steps, this week)

1. **Aggregate `phases.jsonl` into the matrix.** Heads-up: the intended aggregator helper in
   `meta/analysis.py` is **not built yet** — that module currently only has `load_eval_records`,
   `compute_metrics`, `compute_sensitivity`, and `build_optimizer_input`, with no transition-matrix
   function. So for now, hand-aggregate from `phases.jsonl` (a short throwaway script over the
   per-workflow phase logs). Don't let the missing helper become an excuse to pick by gut — running
   it by hand is the whole job here.
2. **Re-attribute sink failures** using `synthesis_validator` / `guardrail_validator` /
   `goal_judge goal_met=false`.
3. **Read the highest-count first-failure cell.** That seam wins.
4. **Instrument that one seam first** with a cheap Tier-A probe — a deterministic 100%-coverage check
   plus one offline CI regression row — rather than front-loading a full judge/gold-set build. Earn
   the heavier judge track only if the Tier-A data shows it's warranted.

## Why this answers "limited time" specifically

The constraint isn't "which call matters most in the abstract" — it's "where does one unit of eval
effort remove the most real failures." The transition failure matrix is exactly that ranking. It is
computable today from data we already have, it's resistant to the bias of instrumenting the
component we're emotionally attached to, and it hands you a single defensible cell to point at when
someone asks "why this seam and not the other eleven?"

**Done when:** you've run the aggregation (however thin), re-attributed the sink, and can point at a
*counted* cell — not a harm story — as the reason for the seam you chose.
