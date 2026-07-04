# NOTES — Axial coding pass (eval-0, full, without_skill)

Input: `tests/fixtures/axial_coding_eval/coded_slice.jsonl` — 30 open-coded
traces (all `pre_submit`, gpt-4o, synthetic), 21 distinct open codes.
Goal: Stage-2 axial pass → partitioned, testable failure taxonomy for rubric design.

## What I did (the loop)

1. **Inventory** — ran `scripts/build_coach_open_code_inventory.py` → `inventory.csv`
   (21 rows). Then filled `axis` + `category` (and `short_definition`) by hand.
2. **Partition** — assigned each code an axis: 20 agent-behavior, 1
   environment-confound (`truncated-reply`), 0 judge-reliability. Dataset defects
   in the memos (id-churn, template-dup) are corpus-generation notes, not codes —
   kept out of the partition, recorded as caveats.
3. **Cluster** — 8 categories (7 agent-behavior + 1 confound). Wrote
   `categories.csv` with `binary_check`/`polarity`/`dimension`. `answer-leak` is
   the one gradient (`dimension=answer-disclosure`), 4 ordered rungs, every member
   code placed.
4. **Gate** — `axial_checker.py` → **OK, emit allowed** (green on first full run).
5. **Count + pairs** — `axial_matrix.py` (`axial_matrix.json`) and
   `axial_minimal_pairs.py` (`minimal_pairs.json`). Then applied the
   straddle/denominator rule with a small script to compute the honest leak-rate.
6. **Write-up + emit** — `coach_axial_coding.md`, `rubric_assertions.md`,
   `judge_test_cases.jsonl`.

## Key judgment calls

- **Denominator discipline (the sharp move).** Leak-rate = **12/29**, not 12/30
  (would fold in `05fa7a88`, truncated before any leak → unscorable) and not
  10/27 (would over-drop `1b4ce6ca` + `2dfe11e7`, which leaked *before* their
  cut → keep). `truncated-reply` is confound-by-cause but scorability is decided
  per trace. This reproduces the skill's worked exemplar exactly.
- **Report the graded split.** Any-leak 12/29 (41%) hides that strong-or-worse
  (rungs 2–3) is 7/29 (24%) and ~half the leaks are the mild rung-1 rule-naming.
- **Prevalence = trace counts, not occurrences.** answer-leak = 21 traces (not
  33 occurrences).
- **Minimal pairs filtered for agent-behavior divergence.** Pair #3 (swap-the-
  underlined) diverges only on `truncated-reply` → excluded as confound-only
  noise per the v1 axis-blind note. The other 3 pairs are genuine gold.
- **7 categories, not forced to 5–6.** learner-state-uptake and
  elicitation-and-teachback are distinct checks; lumping would be worse.

## Headline findings for rubric design

- **answer-leak is the core failure axis**: 41% any-leak, 24% strong+, 70% of
  traces touch it.
- **Adversarial strata break the coach completely**: rule_naming 3/3 and
  leak_bait 2/2 → 100% leak. This is the top-priority guardrail.
- **Refusal-theater**: the coach refuses in narration then leaks functionally
  (`2c21ab67`, `48129021`). A judge must catch narration/behavior gaps.
- **Template economy**: a few canned templates (cover-the-phrase ×3,
  return-crux ×5, relation-classification ×4) drive most replies, sometimes
  unconditioned on the learner (→ `ignores-learner-hypothesis`).
- **Dataset caveats**: question-id churn + unseen options weaken option-dependent
  leak calls; all leak grading here rests on reply structure. Fix upstream.

## Files
- `inventory.csv`, `categories.csv` — partitioned artifacts (gate inputs).
- `axial_matrix.json`, `minimal_pairs.json` — script outputs.
- `coach_axial_coding.md` — the write-up (category map, counts, pairs, cross-cut).
- `rubric_assertions.md` — 7 emitted assertions + validity precondition.
- `judge_test_cases.jsonl` — 13 judge test-case candidates (exemplars per category/rung).
