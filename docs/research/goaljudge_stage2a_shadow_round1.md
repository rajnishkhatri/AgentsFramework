# Stage 2a shadow gate — round 1 (FAIL, iterate generator)

**Date:** 2026-06-12 · **Flag:** `success_conditions_source=shadow` (flipped via
`gs://agent-prod-gcp-dev-agent-facts/ops/goal_judge_config.json`, no redeploy)
· **Sample:** 30 goldset tasks (same deterministic every-k-th selection as
`tests/components/test_task_understanding_quality.py`), driven live through the
BFF (`thread_id=shadow-2a-{00..29}`). Run log: archived from
`/tmp/shadow_2a_runs.jsonl`; per-case spans from `/tmp/shadow_2a_results.json`.

## Results

| Metric | Result | Threshold | Verdict |
| --- | --- | --- | --- |
| Spans published (`eval.task_understanding`, mode=shadow) | 30/30 | — | ✅ pipeline |
| Gate-pass (source=generated, no fallback) | **22/30 = 73.3%** | ≥95% | ❌ FAIL |
| Branch coverage (generated, multi-branch) | **9/18 = 50%** | ≥80% | ⚠️ see note |
| Judge consumed deterministic (shadow invariant) | 30/30 | 100% | ✅ |
| Confidence | p50=1.0, min=0.9 | — | ⚠️ no signal |

## Failure analysis

**All 8 fallbacks are lexical grounding-gate rejections** (`grounding gate:
condition N shares no content token with the task input`) — the generator
(gpt-4o-mini) paraphrases instead of reusing task vocabulary, despite the
prompt's "task vocabulary verbatim" instruction. Cases: 02, 03, 14, 16, 17,
21, 22, 26. The fallback cascade worked exactly as designed: every rejection
degraded to the deterministic floor and the judge consumed it.

**The 50% coverage number is mostly metric noise, not bad checklists.** The
uncovered "branches" are `_extract_branches` artifacts — enumeration headers
("Compare two inputs:", "pls compare three thing") and trailing fragments
("name them", "give one answer") whose content tokens ("compare"/"name") don't
appear in otherwise-complete checklists. Human inspection of the misses (05,
07, 08, 11, 15, 23) shows each enumerated sub-step IS covered by a condition.
The L3 metric should drop enumeration-header/fragment branches before checking.

**Span-query gotcha:** traces with ≥100 observations (10-step runs) silently
truncate at the Langfuse `limit=100` default — query
`?name=eval.task_understanding` directly, never filter client-side.

## Recommended fixes before round 2

1. **One bounded retry on gate rejection** in the orchestration wrapper:
   re-invoke the generator with the rejected conditions + gate reasons appended
   to the prompt. Expected to recover most paraphrase rejections (the model
   knows the content; it ignored the vocabulary constraint once).
2. **Prompt tightening:** make the vocabulary rule concrete — "every condition
   MUST quote at least one exact word/path/command from the task text".
3. **Coverage-metric fix** in `test_task_understanding_quality.py`: filter
   branches that are enumeration headers (ending in `:`) or < 2 content tokens.
4. Confidence is uninformative (p50 = 1.0) — exclude from gating; revisit at
   distillation time.

Do **not** flip to `generated` until round 2 passes ≥95%. Shadow can stay on —
it costs one extra fast-tier call per run and publishes the evaluation corpus.
