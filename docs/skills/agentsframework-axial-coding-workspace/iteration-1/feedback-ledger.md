# Iteration 1 feedback → action ledger

> **Iteration-2 status (applied 2026-07-04):** A1 ✅ fixed (matrix emits
> `category_trace_counts` + `category_occurrence_counts`; TDD red→green; verified
> on real data 21 traces vs 25 occ). A2 ✅ fixed (checker rejects invalid
> polarity; TDD red→green). A3 ✅ SKILL.md note added. B1–B4 ✅ folded into
> SKILL.md (straddle-governs-denominator worked example; gradient-rung rule;
> graded-split reporting; gate=counted-set traceability). C1–C5 ⏳ deferred to
> the next eval run (harness/fixture changes). 26/26 tests green; mirror parity
> green after `make skills-sync`.

The reviewer verified every output against the raw fixture. Findings sorted by
fix location (the reviewer's own diagnosis: fix at script/checker level, not
prose, since clean baselines got count-labeling right WITHOUT the skill).

## A. Tooling bugs — fix in code NOW (iteration 2 scripts)

| # | Bug | Evidence | Fix |
|---|---|---|---|
| A1 | `axial_matrix.py` emits **occurrence** counts but names them `category_counts` + pairs with a trace-level `agent_denominator` → invites "97% vs 77%" mislabel (with_skill eval-0 made exactly this error) | verified: scaffold-ish = 26 occ vs 21 traces on the fixture | emit BOTH `category_trace_counts` and `category_occurrence_counts`; rename/disambiguate |
| A2 | `axial_checker.py` never validates the `polarity` column → "positive" category containing `no-teach-back`/`empty-praise` passes silently (recurred in eval-0, eval-1, eval-2) | verified: polarity only in docstring | add a polarity sanity check (a category's polarity must be consistent with its member codes' poles), OR drop the column |
| A3 | inventory `short_definition` empty on all 21 rows every run — it's a tooling default, not an agent choice | all 6 runs | either populate from memos, or drop the column from the axial subset |

## B. SKILL.md prose improvements (iteration 2)

| # | Gap | Source |
|---|---|---|
| B1 | The **straddle rule** is the sharp differentiator (eval-1) but underspecified: it resolved the *numerator* per-case but the skill should make explicit it also governs the **denominator** (a truncated no-leak trace is *unscorable*, drop it) — that's the exact marginal lift the skill provides | eval-1 both arms |
| B2 | **Gradient membership**: a gradient category may hold more codes than the dimension orders (hint-leak had 6 codes, 3 ranked). Every code in a gradient category needs a rung or an explicit "off-gradient" marker | eval-2 with_skill |
| B3 | **Report the graded split, not just a collapsed rate**: eval-1 headline weighted rule-naming (mildest) == hands-over. Severity split (strong-implication/hand-over only = 6/29 ≈ 21%) is strictly more informative | eval-1 with_skill |
| B4 | **Gate→count traceability**: eval-1 put `overshoots-the-ask` in the answer-leak category but excluded it from LEAK_CODES — the counted set diverged from the gated category | eval-1 with_skill |

## C. Eval-harness / checklist fixes (iteration 2 method)

| # | Fix |
|---|---|
| C1 | **Baseline contamination (eval-0):** fixture path is INSIDE the skill bundle, so baselines find SKILL.md + scripts. Move the fixture to a neutral path (or worktree with bundle removed) for baseline runs. Rerun eval-0. |
| C2 | Add checklist criterion: **"counts quoted with correct unit (traces vs occurrences)"** — eval-0 with_skill would have failed it; catches A1 regressions. |
| C3 | Correct the eval-1 baseline grader note: real failure is "no per-trace scorability call on the truncated non-leak" (denominator), NOT "gave a range" — it committed to 0.40. |
| C4 | Sharpen eval-1 fixture: add more truncated non-leak traces so the denominator decision moves the headline by several points, not ~1.4. |
| C5 | Candidate 4th eval behavior: "resolves flagged ambiguity by reading the trace memo, not guessing" (baseline misfiled `declines-to-confirm-answer` as failure; one memo read would have fixed it; both skill runs got it right). |

## D. Arithmetic slips the reviewer caught (not bugs, worth noting)

- with_skill eval-0 NOTES said "19 agent + 1 confound" but inventory has 21 codes
  (20 agent + 1 confound). Baseline got 20+1 right. Agent slip, not tooling.

## Skill-value verdict (reviewer, on the CLEAN evals)

> "The deltas are the skill's actual content, not noise." The skill's marginal
> contribution, precisely isolated: (a) axis partition keeping confounds out of
> failure buckets, (b) ratification framing keeping the LLM from owning the
> taxonomy, (c) the binary-check requirement making categories rubric-ready.
> Baselines *approached and stopped short of* all three.
