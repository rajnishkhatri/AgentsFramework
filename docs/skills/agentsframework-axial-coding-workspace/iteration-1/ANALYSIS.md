# Iteration 1 — eval analysis

**Skill:** agentsframework-axial-coding · **Runs:** 3 prompts × (with-skill + baseline) = 6

## Scoreboard (assertion pass rate)

| eval | with-skill | baseline | baseline status |
|---|---|---|---|
| 0 · full axial pass | 5/5 | 5/5 | **CONTAMINATED** — baseline read SKILL.md + used bundled scripts |
| 1 · confound partition | 3/3 | 2/3 | clean |
| 2 · resist authoring | 3/3 | 0/3 | clean |
| **Total (clean evals only)** | **6/6 (100%)** | **2/6 (33%)** | |

## The contamination finding (methodology, not the skill)

The eval-0 baseline was told nothing about the skill, but it explored the repo,
found `docs/skills/agentsframework-axial-coding/scripts/`, read the SKILL.md, and
ran the whole pipeline — its NOTES.md literally says "Method (agentsframework-
axial-coding skill, the how)". So eval-0 is a with-skill-vs-with-skill pair and
its +0.00 delta is meaningless. **The skill's scripts living in the repo tree
means a "no-skill" baseline can discover them.** For a clean future comparison,
run baselines in a worktree with the bundle removed, or point them at a copy of
just the fixture.

eval-1 and eval-2 baselines were **clean** (no skill references; they wrote their
own code) — those two are the trustworthy signal.

## What the clean evals show

**eval-2 (resist-authoring) — largest, clearest gap (3/3 vs 0/3).**
- Baseline: shipped 4 vibe-named buckets as the deliverable, mixed the
  `truncated-reply` confound with `empty-praise` in one "Mechanical Defects"
  bucket, no testable checks, named the categories as the answer.
- With-skill: partitioned every code onto an axis before counting, isolated the
  confound, gave each of 6 categories a binary check, ran the gate, and
  explicitly said "names are mine, not ratified — the skill forbids LLM
  authoring." This is the skill working as designed.

**eval-1 (confound-trap) — real but narrow gain (3/3 vs 2/3).**
- The baseline was *much* stronger than predicted: it did not naively fold the
  truncated traces — it read the memos, confirmed the leaks stood on visible
  text, and gave a range [0.37, 0.40].
- With-skill went one better: the **straddle rule** ("assign by cause, decide
  scorability per case") let it resolve each truncated trace individually —
  drop only the 1 that cut *before* any leak, keep the 2 that leaked *before*
  the cut → a defensible point estimate **0.414 (12/29)** instead of a range.
- Verdict: the skill sharpened a good-but-blunt baseline. The single failed
  baseline assertion is "gave a resolved number" — it gave a range instead.

## Cost (the skill is not free)

| eval | with-skill tokens | baseline tokens | Δ |
|---|---|---|---|
| 0 | 82k / 213s | 91k / 269s | (both used skill) |
| 1 | 77k / 165s | 47k / 102s | **+64% tokens** |
| 2 | 58k / 130s | 45k / 73s | **+29% tokens** |

The discipline (partition, gate, categories CSV) costs 30–65% more tokens on the
clean evals. For eval-1 that bought a sharper number; the buyer decides if it's
worth it for a leak-rate query vs a full taxonomy pass.

## Signal for the skill itself (candidate improvements)

1. **The straddle rule is the sharpest differentiator** — eval-1 shows it. It's
   currently one paragraph in Step 1; consider a worked micro-example (the
   truncated-leak case) so it fires reliably.
2. **"Quick and dirty" still triggered the full pipeline** (eval-2 with-skill) —
   good (discipline held under pressure to skip it), but the run stopped before
   the write-up. The skill could say explicitly what the minimum viable output
   is for a "quick cluster" ask (partition + gate + counts, defer the .md).
3. **Every run independently flagged the same corpus smell** (id-churn /
   redundancy-conflation across question_ids). That's a Stage-1 data-quality
   signal the skill could name as an expected finding, so coders route it to a
   corpus ticket rather than the taxonomy (all 6 runs did this by instinct).
4. **All runs rediscovered refusal-theater** as the headline must-catch — strong
   evidence the skill (and the codes) lead to the real gold.
