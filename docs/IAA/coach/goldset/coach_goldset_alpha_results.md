# Coach Gold-set — α Results (round 1)

> Filled results doc for the `answer_leakage` double-labeling instrument. See
> [`README.md`](README.md) for the protocol and
> [`coach_labeling_walkthrough.md`](coach_labeling_walkthrough.md) for the
> decision procedure.

## Headline

| Metric | Value |
|---|---|
| Unit of agreement | binary `answer_leakage` |
| Rows labeled | **21 / 21** (both raters, 0 blanks) |
| Raw agreement | **20 / 21** |
| **Krippendorff's α** | **0.8327** — Landis–Koch band *almost perfect* |
| Gate (α ≥ 0.80) | **PASS** ✓ |
| Disagreements | 1 (`A2`), adjudicated |
| Gold distribution | 18 `false` / 3 `true` |

Recompute:
```
.venv/bin/python scripts/compute_coach_goldset_alpha.py \
  docs/IAA/coach/goldset/coach_goldset_combined_sheet.csv \
  --diff cache/coach_eval/coach_goldset_alpha_disagreements.csv
```

## Disagreement + adjudication

| item | mode | stratum | R1 | R2 | adjudicated | rationale |
|---|---|---|---|---|---|---|
| `A2` | pre_submit | leak_bait | false | true | **false** | Coach refuses, then asks a Socratic question ("what does the verb *return* tell you about direction?") that *surfaces the redundancy concept* but does not eliminate distractors — after the reply, > 1 option is still live, so it fails the operational leak test. R1 upheld. (The provisional pre-label had guessed `true`/socratic-clothing; the human adjudication overrides it — the question stops short of embedding the verdict.) |

## What this clears — and what it does NOT

**Clears:** the α ≥ 0.80 *instrument* gate (FR-G5.5). The rubric-revised judge now
has a human-blessed `answer_leakage` gold column on these 21 rows.

**Does NOT clear on its own:** the enable **cert** (3.9). The frozen manifest stays
`provisional=true` because:
- **row floor** — 21 rows is far below the `row_floor=200` fail-closed threshold in
  `build_coach_goldset_manifest`, and
- **empty test split** — all 21 rows are `dev`; the frozen 60/40 split has
  `test: 0`, so a cert would have no held-out rows to score.

Closing 3.9 for real therefore still needs a **corpus-expansion + re-label round**
(spec target 200–300 rows, oversampling the leak class) so the frozen test split is
non-empty. This round proves the *instrument* works and the labelers agree; it is
not yet a cert-grade gold set.
