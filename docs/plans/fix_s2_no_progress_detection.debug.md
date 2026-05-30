# Debug Session: S2 No-Progress Detection Failure

Debug session `3f33d4`. Pins down the exact runtime mechanism behind register
issue **I1** (`docs/plans/session_issues_register.plan.md`) and implements a fix.
Captured here so subsequent sessions have the runtime evidence, not just code guesses.

## Symptom

Running Synthetic Scenario **S2** ("Search the web for the current weather in
Austin, Texas and summarize the result in one paragraph.") against the local
middleware, the agent issued **20 consecutive `web_search` calls**, never produced
a final answer, and terminated with `outcome=partial` / `termination_reason=max_steps`.
The graduated no-progress wrap-up (warn at threshold → hard-stop) never fired.

- Reproduce: restart middleware, then `python scripts/_dbg_d9c823_send.py --port 8000`.
- Scenario payload: `tests/synthetic/blackbox/dataset.py` (S2).

## Hypotheses

- **H1** — Output uniqueness defeats `count_trailing_repeats` (stub echoes the query into `tool_output`).
- **H2** — Input variation defeats it (LLM varies `query` each step → `(tool_name, tool_input)` key never matches).
- **H3** — `tool_results` adjacency reshaped by the `_append_list_by_record_id` reducer / history limit.
- **H4** — Threshold / `_should_continue` wiring is wrong, so a high repeat count wouldn't trip.
- **H5** — Wrap-up fired but was ineffective (tools not stripped / `no_progress_directive_sent` mishandled).

## Instrumentation

NDJSON logs (session `3f33d4`) written to `.cursor/debug-3f33d4.log` via the
`_dbg_3f33d4` helper in `components/evaluator.py`. Three log points:

- `evaluator.count_trailing_repeats` → `count`, `n_results`, `match_input`, `match_output`, `match_sig`, `tail`.
- `react_loop.call_llm_node` → `repeats`, `threshold`, `inject_wrapup`, `directive_sent`.
- `react_loop._should_continue` → `branch`, `repeated_tool_calls`, thresholds, `step_count`.

## Runtime evidence (pre-fix run, 20 steps)

Every `count_trailing_repeats` log showed `count: 1`, `match_input: false`,
`match_output: false`. The `tail` confirmed each step used a distinct query
("current weather in Austin, Texas" → "Austin Texas current weather" →
"Austin Texas weather today" → …) and each `tool_output` began with
`"Search result for: <that step's query>"`. `_should_continue` reported
`repeated_tool_calls: 1` on every step, only flipping to `"branch":"done"` at
`step_count: 20`. `inject_wrapup` was `false` on all 20 steps.

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1 | **CONFIRMED** | `match_output: false` every step; stub bakes query into output. |
| H2 | **CONFIRMED** | `match_input: false` every step; queries vary each step (see `tail`). |
| H3 | REJECTED | `n_results` grows cleanly 2→20, no gaps; adjacency is true call order. |
| H4 | REJECTED | Thresholds correct (`threshold:3, hard_limit:5, max_steps:20`); branch logic fine — it just received `repeated_tool_calls:1`. |
| H5 | REJECTED | `inject_wrapup:false` always because `repeats` (max 1) never reached threshold 3; wrap-up never got a chance to fire. |

## Root cause

`count_trailing_repeats()` (`components/evaluator.py`) matched a repeat only when
consecutive calls shared the same `(tool_name, tool_input)` key **or** the same
**raw** `tool_output`. Two facts combine to defeat both:

1. The search stub (`services/tools/search/stub.py`) echoes the unique query into
   the result title (and `web_search.py` echoes it into the `query` field), so
   every `tool_output` is unique.
2. The LLM varies the query string each step, so every input key is unique.

Result: `count` stays at `1` forever → never reaches `no_progress_repeat_threshold`
(3) → wrap-up directive never injects → loop burns all `max_steps` (20) → `partial`.

The existing test `test_identical_output_different_input_counted`
(`tests/orchestration/test_no_progress.py`) encodes the *intended* contract: a
non-advancing provider returning the **same output** despite different inputs
should be caught. The real stub breaks that intent by echoing the query.

## Fix

Make output comparison **echo-normalized**: strip each call's own input values
from its output before comparing. Two calls that return the same template
differing only by an echoed query then compare equal (catching the thrash),
while genuinely different results (real SearXNG hits, distinct file contents)
stay distinct (preserving legitimate multi-call progress).

- New helper `_echo_normalized_output(entry)` in `components/evaluator.py`
  (skips tokens shorter than 3 chars to avoid over-stripping).
- `count_trailing_repeats` now matches on `entry_key == last_key` **or**
  raw-output-equal **or** echo-normalized-output-equal.

Verified: all 8 `TestCountTrailingRepeats` cases and 58 tests across
`test_no_progress.py` + `test_evaluator.py` pass.

## Expected post-fix behavior

`count_trailing_repeats` climbs to 3 by ~step 3 (`match_sig: true`) →
`inject_wrapup: true` → tools stripped, `no_progress` STEP_PLANNED recorded,
`no_progress_directive_sent=True` → synthesis pass produces a final answer →
loop terminates ~step 4–5 with `termination_reason=no_progress` and
`outcome=partial` (clean wrap-up with a synthesized answer), instead of 20 steps
of thrash.

## Status / follow-ups

- Fix implemented in `components/evaluator.py`. Pending live verification run
  (post-fix logs tagged `runId: "post-fix"`).
- Debug instrumentation (`_dbg_3f33d4` + the two `react_loop` log points) is
  **still in place** pending post-fix verification; remove once logs confirm success.
- Related: the underlying "stub thrash" is also addressed end-to-end by the
  SearXNG real-search work (`docs/plans/searxng_real_web_search.plan.md`); this
  fix is the orchestration-layer safety net independent of the search provider.
- Register issue **I2** (outcome=success for unaccomplished task) is a separate
  fix already covered by `evaluate_task_outcome` (`no_progress` → `partial`).
