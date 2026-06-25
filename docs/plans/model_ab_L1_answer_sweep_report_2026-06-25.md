# Model A/B — L1 Answer-Quality Sweep (A3b)

**Date:** 2026-06-25
**Corpus:** `cache/model_ab_answer/l1_full.jsonl` — 10 deterministic GEN-L1 rows
(converted from `frontend/e2e/fixtures/model_ab_corpus.json` general family;
multi-turn/memory deferred to Phase B).
**Instrument:** answer-correctness scorer (`scripts/model_ab_answer_score.py`),
NOT the planning `score_run` (which is the wrong instrument — design doc §6).
**Fixtures:** deterministic, seeded by `scripts/seed_model_ab_workspace.py`
(`EXPECTED_BY_CASE` = the one source of truth for each case's known answer).

## Results

| arm (model) | accuracy | correct | cost/task | run |
|---|---|---|---|---|
| `gpt-4o-mini` (baseline) | **0.80** | 8/10 | $0.00103 | l1_haiku |
| `claude-haiku-4-5` | **1.00** | 10/10 | $0.01106 | l1_haiku |
| `gpt-4o-mini` (baseline) | **0.60** | 6/10 | $0.00112 | l1_flash |
| `deepseek-v4-flash` | **0.90** | 9/10 | $0.00187 | l1_flash |

Both arms PROMOTE (candidate beats baseline on accuracy; integrity clean).

## Honest reading (the caveats matter more than the headline)

1. **Baseline is NON-DETERMINISTIC across runs: gpt-4o-mini scored 0.80 then 0.60
   on the SAME 10 rows.** Its failures are file-read give-ups ("I attempted to
   read the files but encountered errors" / "I was unable to access the file") —
   and *which* tasks it abandons varies run-to-run. This is a real reliability
   finding (gpt-4o-mini is flaky on multi-file-read tasks), but it also means
   **single-run accuracy is noisy ±0.2 here**. A real verdict needs N≥3 runs per
   arm and a mean, or a larger corpus. These two runs are a SMOKE-grade signal,
   not a final ranking.

2. **The scorer had false-negatives that understated accuracy — FIXED mid-sweep.**
   Initial scoring flattened claude-haiku-4-5 to a fake 0.80 because (a) the
   numeric grader's "last number" heuristic grabbed a trailing conversion factor,
   and (b) a correctly-sorted list reformatted as a numbered list failed a
   contiguous-substring match. Hardened to: scan ALL numbers (pass if any within
   tol) + token-set membership for list answers. After the fix haiku is genuinely
   10/10. **Lesson: a scorer false-negative is indistinguishable from a model
   failure in the aggregate — always eyeball per-case misses before trusting a
   number.** (19 scorer tests green.)

3. **deepseek-v4-flash's one miss is GENUINE** (not a scorer artifact): on
   convert-unit it read the value 5 correctly but misread the task — it treated
   the units as ambiguous and never applied the `1 mile = 1.60934 km` conversion
   (expected 8.0). A real instruction-following miss.

4. **Cost is real and discriminating:** per-task cost
   gpt-4o-mini $0.001 < deepseek-flash $0.0019 < claude-haiku-4-5 $0.011
   (~11× the baseline). On THIS L1 slice, deepseek-flash is the standout
   quality-per-dollar: +0.3 accuracy over baseline at <2× the cost, vs haiku's
   +0.2 at ~11× — though see caveat 1 (baseline noise inflates both deltas).

## What this establishes
- The A3b answer instrument WORKS: deterministic fixtures + answer grading +
  per-arm cost, producing a discriminating, interpretable signal (unlike the
  hollow planning-corpus PROMOTE in A3a).
- A genuine capability gap surfaced: **gpt-4o-mini is unreliable on file-read
  tasks**; both Anthropic-Haiku and DeepSeek-Flash are more reliable.

## Open / next
- **N≥3 runs per arm** to convert the noisy single-run accuracies into a stable
  mean (cheap — L1 is ~$0.001-0.011/task).
- **Reasoning arms** (opus-4-8 / gpt-5 / gpt-5-mini / deepseek-v4-pro) on the
  reasoning-eligible rows.
- **L2/L3 grading (9 rows)** — prose `want_answer`, needs GoalJudge or
  hand-authored expecteds (decision pending, #16).
