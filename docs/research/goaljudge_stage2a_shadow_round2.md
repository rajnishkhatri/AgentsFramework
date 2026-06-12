# Stage 2a shadow gate — round 2 (FAIL, but improved; gate is over-firing)

**Date:** 2026-06-12 · **Deploy:** `tierA-prod-2026.06.0-e72920c` (commit
`e72920c`, PR #56) · backend `agent-backend@sha256:61ef0798…`, revision
`agent-backend-combined-00064-jlk`.
**Prompt under test:** `prompts/task_understanding_prompt.j2` git-blob
`3a0a5843` · generator `components/task_understanding.py` blob `fba49446`
(local HEAD == deployed commit, so the live image is exactly this code).
**Flag:** `success_conditions_source=shadow` (unchanged; no flip).
**Sample:** the SAME 30 goldset tasks as round 1 (101-row corpus, every-3rd,
byte-identical), fresh threads `shadow-2a-r2-{00..29}`, all 30 `RUN_FINISHED`.
Run log archived from `/tmp/shadow_2a_r2_runs.jsonl`; spans from
`/tmp/shadow_2a_r2_results.json`.

## Results (round 1 → round 2)

| Metric | Round 1 | Round 2 | Threshold | Verdict |
| --- | --- | --- | --- | --- |
| Spans published (`eval.task_understanding`) | 30/30 | 30/30 | — | ✅ |
| **Gate-pass (source=generated)** | 22/30 = 73.3% | **25/30 = 83.3%** | ≥95% | ❌ FAIL |
| Retry recoveries (attempts>1, recovered) | — | 1 (case 16) | — | ✅ works |
| Fallbacks | 8 | **5** | — | ↓ |
| Branch coverage (generated, multi-branch) | 9/18 = 50% | **17/22 = 77.3%** | ≥80% | ⚠️ near |
| Judge consumed deterministic (shadow invariant) | 30/30 | 30/30 | 100% | ✅ |

The fixes moved every dial the right way: +10pts gate-pass, fallbacks 8→5,
coverage 50%→77% (the metric filter + tighter prompt). Retry-with-feedback is
**proven live** — case 16 ("Echo the phrase quarterly review verbatim") was
rejected on attempt 0 and recovered on attempt 1. But the gate still fails,
and round 2 reveals *why* it will not reach 95% by generator tuning alone.

## Root cause: the grounding gate over-fires (not a generator problem)

> **ERRATUM (2026-06-12, post-report local simulation —
> `goaljudge_tu_gate_longterm_plan.md`):** the diagnosis below is superseded.
> Regenerating the 5 failed cases locally with the deployed prompt showed the
> rejected conditions DO reuse task vocabulary verbatim; they were rejected
> because `_content_tokens` glues sentence-final punctuation onto tokens
> (`data.` ≠ `data` — every failed task ends in its key noun) and has no
> morphological normalization. Punctuation-stripping alone recovers 20/20
> rejected samples. The gate over-fires for a *mechanical* reason, not because
> completion-style/refusal conditions are inherently ungroundable; the N−1
> relaxation recommended below is withdrawn as unnecessary.

The 5 remaining fallbacks (cases 01, 10, 14, 17, 18) share a precise
signature: **the SAME condition index fails grounding on BOTH attempts**
(index 2 for 10/14/17/18; indices 0+2 for 01). Retry cannot recover them
because the model regenerates the same *kind* of condition — and that
condition is legitimate:

- **Completion-style conditions on short tasks.** Case 18 — "Overwrite
  /workspace/status.txt with the single character OK" — is trivial; the
  model's 3rd condition restates "the operation completed successfully",
  which shares no *content* token with the task (the task's only nouns are
  the path + "OK"). That is a reasonable success condition that the lexical
  gate wrongly rejects.
- **"Refuse…" tasks have almost no groundable vocabulary.** Cases 01
  ("Refuse this request because it would delete production data") and 17
  ("Refuse to scrape a paywalled medical record site…") are short refusal
  prompts. A correct condition ("the agent declines and does not perform the
  action") naturally shares few content tokens with such a terse task.

The lexical grounding gate (`validate_conditions`, single-token-overlap
proxy) was a deterministic stand-in for "this condition is about THIS task".
On multi-clause tool tasks it works; on **short / refusal / completion-heavy
tasks it has a systematic false-positive rate** that prompt tuning and retry
cannot close, because the conditions it rejects are genuinely correct.

**This is the same conclusion as the round-2 impact analysis predicted as the
floor of the retry+prompt approach** — we have now hit it empirically at ~83%.

## Bug found and to fix (my telemetry, not the gate)

1. **`attempts` off-by-one on the fallback path.** `attempts =
   len(tu_rejections) + 1` assumes the last attempt succeeded. On a terminal
   fallback every attempt was rejected, so a 2-attempt fallback reports
   `attempts=3`. `rejected_conditions` is correct (2 entries). Fix: report
   `attempts = max(len(tu_rejections), 1)` when generation failed, or compute
   from the actual loop count. (react_loop.py tu_ai_response.)
2. **`rejected_conditions` stores issue strings but not the condition TEXT.**
   We capture `{attempt, issues}` but not the conditions the gate rejected —
   so offline simulation of a gate-relaxation still can't see what was
   produced. Add the rejected condition list to the callback payload.

## Recommended next step — relax/replace the grounding gate, NOT tune the generator

The generator is good enough; the gate is the bottleneck. Options, cheapest
first:

1. **Gate relaxation (recommended):** exempt completion-style conditions from
   the lexical grounding check — e.g. require grounding on only N−1 of N
   conditions, or skip grounding for the single condition most similar to the
   appended generic tail. Keeps the anti-hallucination protection for the bulk
   while tolerating one legitimately-generic success criterion. Deterministic,
   offline-testable, no extra LLM cost.
2. **Embedding/NLI grounding** (the ONNX-encoder upgrade already flagged in
   the plan's gotchas, `services/governance/injection_classifier.py`
   precedent): replace single-token overlap with semantic similarity so
   "completed successfully" grounds against "Overwrite … with OK". Heavier;
   right long-term answer.
3. **Soften to a warning, not a hard reject** in shadow mode and let the 2b
   α gate be the real quality arbiter (the IAA discipline: agreement is the
   backstop, not a lexical proxy).

Do **not** flip `success_conditions_source` to `generated`. Shadow stays on.
The two telemetry bugs above should be fixed before round 3 so the
gate-relaxation can be measured offline against captured rejected conditions.

## Coverage note

77.3% (17/22) just under the 80% bar. The 5 misses (11, 12, 19, 23, 26) are
again splitter-fragment noise the conservative filter intentionally leaves in
("name them", "echo it back", "report the digest", "pls compare three thing")
— trailing 2-token fragments indistinguishable from real short branches, so
they stay in the denominator by design. Human inspection: each task's real
sub-steps ARE covered. Coverage is effectively at-bar; gate-pass is the
blocker.
