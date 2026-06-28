---
type: decision-record
title: 'ADR-0003: GoalJudge L2/L3 residual re-adjudication — exclude truncated item + apply verifier cascade'
status: accepted
created: 2026-06-28
updated: 2026-06-28
owner: Rajnish Khatri
related: harness_adoption_v2_practical_adoption.plan.md, model_ab_l2l3_blind_adjudication.plan.md, goaljudge-correctness-cascade-fix
tags: [decision-record, eval, goaljudge]
---

# ADR-0003: GoalJudge L2/L3 residual re-adjudication — exclude truncated item + apply verifier cascade

**Status:** Accepted — 2026-06-28.
**Related:** `docs/plan/harness_adoption_v2_practical_adoption.plan.md` (Wave 1, items 1.1/1.2);
`docs/plans/model_ab_l2l3_blind_adjudication.plan.md` (the blind gold-set process);
`components/answer_verifiers.py` (the cascade, commit `463ac59`).
**Audience:** anyone re-opening the GoalJudge calibration / the L2/L3 seed gold set, or
who reads the v2 plan's claim that `70ff3369` is a judge false-positive.

---

## Context

The harness-adoption v2 plan (Wave 1) names a residual GoalJudge false-positive — item
`70ff3369` (case `GEN-L3-iterative-refine-15`, arm `deepseek-v4-pro`) — and asks to "fix
the rubric" so the judge passes it. The plan's own reframe flagged that the evidence was
weaker than stated and required **re-adjudicating the case before any fix** (its honesty
rule: "don't ship a fix that teaches the judge to pass incoherent answers").

Re-adjudication this session overturned the premise on two fronts:

1. **`70ff3369` is not a judge false-positive.** The model answer is **truncated at
   source** — it ends mid-sentence at "`office: up`", before ever stating the proposed
   cuts (rubric must-have #2) or the zero-balance verification (must-have #3). Confirmed
   in `cache/model_ab_answer/l2l3_raw_answers.json` (the original), not just the blind
   copy. GoalJudge's `goal_met=false` was the **correct** call against the truncated
   text. The blind gold label `correct` was the error: rater-1's own note says
   "proceeds to cut proposal" — the answer never does (it was cut off), and the rater
   inferred the unwritten cut from the visible slack.

2. **The real residual TNR failure is on a different case.** Running `judge_validation`
   against the harvested verdicts showed the TNR-floor breach is driven by **two false
   positives on `GEN-L2-dependency-resolve-12`** (claude-haiku, claude-opus): both
   produced a **reversed** topological order (`A→B→C→D` instead of the correct
   `D,B,C,A`) and the LLM judge rubber-stamped it as met because the answer *claimed*
   validity. A third item on that case (deepseek-v4-flash) was a judge false-negative
   (correct order, failed for not echoing it in the final answer). This is the known
   "GoalJudge grades process, not correctness" weakness.

Crucially, the **deterministic correctness cascade** (`components/answer_verifiers.py`,
commit `463ac59`) is already on this branch and handles the topological-sort shape. The
harvested verdicts file (`l2l3_goaljudge_verdicts.json`) simply predates it — it was
captured from each arm's `evals.log` before the cascade existed.

---

## Decision

1. **Exclude `70ff3369` from the L2/L3 seed gold set** as a truncated-at-source data
   defect (not relabel it). The freeze script gains an audited `EXCLUDED_ITEMS` map
   applied *after* blinding verification, dropping the seed to **52 rows**. Manifest note
   bumped v0.0 → v0.1 with an `excluded_items` provenance field.
2. **Apply the existing verifier cascade to the L2/L3 verdicts offline**
   (`scripts/apply_verifier_cascade_l2l3.py`), reproducing `GoalJudge.evaluate`'s cascade
   contract with **zero live-LLM cost**: the deterministic verifier owns `goal_met` on a
   checkable shape; the harvested LLM verdict is kept verbatim where the verifier
   abstains. Output: `l2l3_goaljudge_verdicts_cascade.json`.

The cascade flips exactly the three divergent `dependency-resolve-12` items toward gold
(2 FP→correct, 1 FN→correct). `judge_validation` then **PASSES** on the 52-row seed:
TPR=1.0000, TNR=0.9375 (both ≥ 0.90 floor), across strict-clean, strict-full, and
exclude-partial mappings.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| Edit the rubric so the judge passes `70ff3369` (the v2 plan as written) | The answer is truncated and never completes the verification; teaching the judge to pass it would reward incoherent output. The plan's own honesty rule forbids it. |
| Relabel `70ff3369` gold → `wrong` | The item was never gradable (truncated at source). Relabeling implies a judgment about a complete answer that does not exist; excluding the corrupted data point is the honest call. |
| Re-run the deepseek arm live to get an untruncated answer | Spends live-LLM budget for one data point that may still differ; the cascade already closes the gate deterministically without it. |
| Add `70ff3369` to the `_is_harness_bug` exclusion list (drop only at validation time) | Keeps a known-corrupt row physically in the "gold" set. Physical exclusion via the freeze script is cleaner and matches the user-confirmed intent (52 rows). |
| Re-run the full GoalJudge LLM over all 52 items | Live-LLM cost on the abstained (non-checkable) items, for no gain — the only verdicts that change are the deterministic ones, which the offline overlay reproduces exactly. |

---

## Rationale

The verifier cascade is *reference-free and deterministic*: it recomputes the expected
topological order from the dependency edges and checks direction, so it cannot be fooled
by a confident-but-reversed answer the way the LLM rubric was. Applying it offline is
faithful to the runtime contract (verifier bool wins; abstain → LLM verdict, never an
average) and costs nothing. Excluding the truncated item removes a data defect from the
gold set without inventing a label for an answer that was never produced.

---

## Consequences

- The L2/L3 seed is now **52 rows** (v0.1), still `provisional: true`. The blind α stays
  "almost perfect" (3-class α 0.910, above the 0.80 gate); blinding provenance is
  preserved because the exclusion runs after the rater-1 hash check.
- The **validated** judge artifact for L2/L3 is `l2l3_goaljudge_verdicts_cascade.json`
  (cascade-applied), not the raw harvested file. Anyone validating the judge must use the
  cascade output or re-run `scripts/apply_verifier_cascade_l2l3.py` first.
- One residual FP remains in the failure-detection framing (`df252d51`), already
  confirmed a **correct** judge call (answer states the paper title, never its claim) by
  `residual_fp_revalidation.json`. It is not a defect.
- The seed is still a v0.0/v0.1 bootstrap — it cannot pass the repo's v1 floor gate and
  must not be presented as a calibrated gold set. Growing it toward ≥100 rows (plan items
  1.3/1.4) remains open and requires new live-LLM A/B answers + blind re-adjudication.
- Reproduce end-to-end: `python -m scripts.freeze_l2l3_goldset_seed` →
  `python -m scripts.harvest_l2l3_goaljudge` →
  `python -m scripts.apply_verifier_cascade_l2l3` →
  `python -m meta.judge_validation --judge cache/model_ab_answer/l2l3_goaljudge_verdicts_cascade.json --clean`.

---

## Supersedes / related

- Corrects `docs/plan/harness_adoption_v2_practical_adoption.plan.md` items 1.1/1.2: the
  named residual is a data + gold-label defect, not a rubric bug; the TNR breach is a
  topological-order correctness gap already closed by the cascade.
- Builds on the cascade introduced in commit `463ac59` (`components/answer_verifiers.py`).
- Feeds `docs/plans/model_ab_l2l3_blind_adjudication.plan.md` Phase 5 (measure the judge
  against the seed before trusting it).
