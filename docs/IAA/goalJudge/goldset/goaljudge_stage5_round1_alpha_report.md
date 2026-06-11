# GoalJudge Stage 5 — Round-1 IAA α Report

> **Run date:** 2026-06-11
> **Sheet:** [`goaljudge_stage5_goldset_full_sheet.csv`](goaljudge_stage5_goldset_full_sheet.csv)
> **Disagreement diff:** [`cache/goaljudge_eval/stage5_round1_diff.csv`](../../../../cache/goaljudge_eval/stage5_round1_diff.csv)
> **A2 cold-blind rationale:** [`goaljudge_stage5_goldset_annotator2_fresh_results.md`](goaljudge_stage5_goldset_annotator2_fresh_results.md)
> **Status:** **α gate FAIL** — Phase 5-E (EvalGen revise) or Phase 5-F (adjudicate) required

---

## Headline

| Metric | Value |
|---|---|
| Rows scored | 79 / 79 |
| Agreements | 57 (72.2 %) |
| Disagreements | 22 (27.8 %) |
| **Krippendorff's α (goal_met, nominal)** | **0.2682** |
| Landis-Koch band | fair |
| Gate threshold | α ≥ 0.8 |
| **Gate result** | **FAIL** |

A 79-row 2-rater complete-data α collapses to Cohen's κ; the value reflects that A1 graded 14 rows `true` that A2 graded `false`, while A2 graded 8 rows `true` that A1 graded `false`. The 22-row split is not random — it is dominated by one diagnosable systemic cause.

---

## Direction of disagreement

```
  r1=true  → r2=false : 14    (A1 more lenient than A2)
  r1=false → r2=true  :  8    (A1 more strict than A2)
```

Net direction skew: 6 rows toward A1-leniency. The skew is consistent with the `len>80`
heuristic bug history (A1's sheet was built before the fix; A2's sheet was built after).

## Disagreement by stratum

| Stratum | Total | Disagree | Rate |
|---|---|---|---|
| representative | 32 | 10 | 31 % |
| boundary | 23 | 9 | 39 % |
| edge | 16 | 3 | 19 % |
| impossible | 8 | 0 | 0 % |

The impossible stratum is unanimous — both annotators agreed every impossible-class row was either `goal_met=false + graceful` or `goal_met=false + unhandled`. Boundary rows are the noisiest, which is the expected shape (it is where the rubric edge cases live).

---

## Systemic causes (rank-ordered)

### Cause A — `len>80` heuristic bug residue (12 of 22 disagreements)

The pre-fix A1 sheet was built by the `build_goaljudge_stage5_annotator1_fresh_sheet.py`
script with a stub grader that promoted `goal_met=true` whenever the agent produced > 80
characters of substantive prose and at least one tool call — **regardless** of whether
Langfuse's `goal_met` axis said `False`. The bug was diagnosed in Phase 5-B0 (task #65)
and the impact report flagged 14 over-grade candidates. 12 of those 14 surfaced here:

```
R-6 over-grade set (14 ids):   GJ-F-006 014 015 016 017 018 020 022 026 035 037 039 042 045
Disagreement r1=true→r2=false: GJ-F-006 014    016 017 018 020 022 026 034 035 037     042 045 088
∩ (12 ids):                    GJ-F-006 014    016 017 018 020 022 026     035 037     042 045
```

A1 self-corrected on **2** of the 14 R-6 candidates (GJ-F-015, 039) before submitting.
The remaining **12** propagated into the round-1 diff.

**Implication:** these 12 disagreements are not a labeling-protocol divergence between
two judging humans — they are residue of a *known-fixed* grader bug. The adjudicator
should treat them as a class, not row-by-row.

### Cause B — Rule 7 (wrong-tool) charitable read split (4 rows)

The wrong-tool branch of Rule 7 has two outcomes:
1. agent obeys the wrong tool → grade outcome (and may pass if the answer is right);
2. agent overrides the wrong tool → grade outcome as if the spec didn't apply.

A1 and A2 diverged on whether to credit the "override + sound conclusion" branch with
`goal_met=true`. Affected rows: **GJ-F-068, GJ-F-074, GJ-F-086, GJ-F-090** (A1=false, A2=true).

This is a real protocol-interpretation disagreement, not a bug. Document the chosen branch
on the protocol doc after adjudication.

### Cause C — A2 "Open:" prefixed rows (4 rows already flagged)

Four disagreement rows have an explicit `r2_review_open_question` starting with "Open:"
— A2 surfaced these as borderline at labeling time:

- GJ-F-041 — empty-directory edge case; LF eval contradicts surface answer
- GJ-F-051 — Django LTS factual accuracy vs current state strictness
- GJ-F-088 — knowledge answer vs missing-approval-ask borderline
- GJ-F-090 — approval-pattern strictness (knowledge answer counts as pass?)

GJ-F-088 also appears in Cause A (`r1=true→r2=false`, not R-6 — A1 over-permissive on a
genuinely borderline call rather than triggered by the bug).

### Cause D — Other (2 rows: GJ-F-003, GJ-F-040)

Both have A2.review = "Resolved: pass" and A1.fm = `incomplete-synthesis` / `criteria-mismatch`.
These are isolated calls; the adjudicator should walk them individually.

---

## Recommendation — what to do with the 22 rows

| Class | Count | Recommendation | Rationale |
|---|---|---|---|
| A (R-6 residue) | 12 | Adjudicate as a batch → likely flip to A2's `goal_met=false` | Known grader-bug residue; A1's recorded label is not the result of human judgment on those rows. |
| B (Rule 7 split) | 4 | Adjudicate individually → write a Rule 7 worked-example into the protocol doc | A real interpretive gap that future raters will hit again. |
| C (already flagged Open) | 3 (1 overlap with A) | Adjudicate using A2's open-question text as the scoping prompt | A2 explicitly asked the adjudicator to walk these. |
| D (idiosyncratic) | 2 | Adjudicate individually | Low-volume; no class signal. |

Total adjudication queue: **22 rows** (the diff CSV is the complete worklist).

**Do NOT run an EvalGen revise loop on this set.** The dominant signal (Cause A) is a
data-quality issue resolved by fixing the build artifact, not a prompt-engineering gap
the EvalGen loop would address. EvalGen revise should fire when the rubric needs
sharpening — here the rubric is fine; the recorded labels reflect a bug already fixed.

The right next step is **Phase 5-F (adjudication)**, not 5-E.

---

## Post-adjudication forecast

If the adjudicator accepts A2's labels on all 12 Cause-A rows (most defensible
given the known bug) and splits the remaining 10 rows 50/50 between A1 and A2,
expected post-adjudication α (recomputed on adjudicated_goal_met vs r1_goal_met):

- 12 flips toward A2 + ~5 flips toward A1 → ~67 agreements / ~12 net disagreements
- Estimated α ≈ 0.65–0.75 (substantial-to-strong band)

That's still below the 0.8 gate. If post-adjudication α remains < 0.8, the path is
either (a) re-run A2 on the disagreement-only subset with the protocol's Rule 7
clarification added, or (b) declare two-annotator α inadequate and escalate to a
third rater (true 3-rater Krippendorff's α). The plan doc favors (a).

---

## Artifacts produced this run

| File | Purpose |
|---|---|
| `docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_full_sheet.csv` | Merged A1 + A2 sheet (canonical Phase 5 artifact) |
| `cache/goaljudge_eval/stage5_round1_diff.csv` | The 22-row disagreement worklist for the adjudicator |
| `docs/IAA/goalJudge/goldset/goaljudge_stage5_round1_alpha_report.md` | This document |

---

## Next steps

1. **Phase 5-F (adjudicate)** — coordinator walks the 22 diff rows; fills
   `adjudicated_goal_met` and `adjudicated_failure_mode` on the full sheet.
2. **Recompute α** — `compute_goaljudge_stage5_alpha.py --column adjudicated_goal_met`
   (extension; or treat adjudicated as ground-truth and compute agreement-against-truth).
3. **If post-adjudication α ≥ 0.8 OR adjudicator confidence ≥ "substantial":**
   Phase 5-G (post-α coverage check) → Phase 6 (freeze).
4. **If not:** revise protocol Rule 7 + re-label disagreement subset (cheaper than a
   third rater for a 22-row queue).
