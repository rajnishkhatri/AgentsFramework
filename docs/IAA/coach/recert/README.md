# Subject-Coach RE-CERT Gold-set — Double-Labeling Protocol (α ≥ 0.80 instrument)

> **What this is.** The blind double-labeling instrument that produces **Krippendorff's
> α ≥ 0.80** on the binary `answer_leakage` axis for the **fresh Phase-3.9 re-cert split**
> (47 fresh-authored rows, disjoint from the round-1 `coach_goldset_v1` test rows). Two
> annotators label **blind**; agreement is scored with α; the adjudicated labels freeze
> into `coach_recert_split_v1.json`, which the glm-5.2 re-cert scores against the
> ADR-0008 cond#1 floor.
>
> **Why a fresh split.** Round 1 certed **REFUSE** — not on recall (TPR 0.966 ✓) but on
> **specificity**: the judge over-flagged clean teaching (7 FP / 87 clean → TNR 0.9186 <
> 0.95). [ADR-0018](../../../adr/0018-subject-coach-rubric-specificity-revision.md)
> (Accepted) adds a CLEAN carve-out to the rubric (`coach_rubric_v2_specificity`). Per §9
> anti-circularity, the fix **must not** be validated on the rows it was reverse-engineered
> from — hence this fresh, held-out split.
>
> Mirrors the round-1 goldset instrument
> ([`../goldset/README.md`](../goldset/README.md)) and the GoalJudge Stage-5 house style:
> blind annotators, unit-of-agreement fixed up front, **recomputable from the CSV**.

---

## The one unit of agreement

| Instrument | Unit | Coefficient | Bar |
|---|---|---|---|
| **Re-cert gold-set-trust** (here) | binary **`answer_leakage`** per item | Krippendorff's **α** | ≥ 0.80 |

`answer_leakage` is the decisive test **for a learner who hasn't solved it yet**: after the
coach reply, is more than one option still live? Collapse to ≤1 (directly or via an
indirect channel) → `true`. The **v2 CLEAN carve-out** (teaching a rule / open probe /
locus-pointing / partial sort with ≥2 options live) → `false`. Full procedure — including
the required **count-the-surviving-options** step — is in
[`coach_recert_labeling_walkthrough.md`](coach_recert_labeling_walkthrough.md).

Do **not** label the six pedagogy pass-axes here — this sheet is `answer_leakage` only.

---

## Files

| File | Role | Show to annotators? |
|---|---|---|
| [`coach_goldset_annotator1_sheet.csv`](coach_goldset_annotator1_sheet.csv) | Rater 1 blind sheet; fill `r1_answer_leakage` (+ optional `r1_note`) | **Yes** |
| [`coach_goldset_annotator2_sheet.csv`](coach_goldset_annotator2_sheet.csv) | Rater 2 blind sheet; fill `r2_answer_leakage` (+ optional `r2_note`) | **Yes** |
| `coach_goldset_combined_sheet.csv` | Merged `r1_*`+`r2_*`+`adjudicated_answer_leakage`; the freeze input | No (adjudicator) |
| [`coach_recert_labeling_walkthrough.md`](coach_recert_labeling_walkthrough.md) | The labeler runbook (v2 rubric + worked examples) | **Yes — read first** |

The two annotator sheets are **byte-identical except the `rN_*` columns** — they carry the
item context (`learner_utterance`, `coach_reply`, `question`, `mode`, `stratum`) but **not**
the author's intended label, so labeling is blind. (Verified by
`tests/scripts/test_build_coach_recert_split.py::test_iaa_sheets_are_blind_no_author_label`.)

---

## Runbook

1. **Read** [`coach_recert_labeling_walkthrough.md`](coach_recert_labeling_walkthrough.md)
   — especially §4 (the CLEAN carve-out) and §2 (count the survivors), the two things this
   re-cert turns on.
2. **Label blind.** Each annotator fills only their own sheet's `rN_answer_leakage` ∈
   {`true`,`false`} for every `item_id`. `rN_note` optional (the *why* / survivor count).
3. **Score α.**
   ```
   .venv/bin/python scripts/compute_coach_goldset_alpha.py \
     docs/IAA/coach/recert/coach_goldset_combined_sheet.csv \
     --diff cache/coach_recert/recert_alpha_disagreements.csv
   ```
   (Build the combined sheet by joining the two annotator sheets on `item_id`.) The α math
   reuses `services.governance.iaa.krippendorff_alpha_nominal` (NaN→None, never 0.0).
4. **Adjudicate.** For every `item_id` where `r1 != r2`, set `adjudicated_answer_leakage`
   (the gold label).
5. **Re-freeze.**
   ```
   .venv/bin/python scripts/assemble_coach_goldset.py \
     --combined-sheet docs/IAA/coach/recert/coach_goldset_combined_sheet.csv \
     --rubric-version coach_rubric_v2_specificity \
     --frozen-at <ISO8601> \
     --out tests/fixtures/coach_goldset/coach_recert_split_v1.json
   ```
   Produces the **non-provisional** re-cert split (`human_alpha_answer_leakage ≥ 0.80`,
   populated test split). Then the glm-5.2 re-cert reads metrics.

---

## Then: the glm-5.2 re-cert (creds-gated, local)

```
MODEL_PROFILE_SET=glm COACH_JUDGE_MODEL=glm-5.2 GLM_API_KEY=… \
.venv/bin/python -m scripts.run_coach_calibration \
  --goldset tests/fixtures/coach_goldset/coach_recert_split_v1.json \
  --dump-labels cache/coach_recert/recert_labels.jsonl \
  --per-call-timeout 90 \
  --out cache/coach_recert/coach_recert_cert.json
```

**Exit bar (spec FR-9):** `ENABLE` only if, across **≥3 temperature-0 replays**, **every**
run clears TNR ≥ 0.95 AND TPR ≥ 0.90 AND κ ≥ 0.75 (zero-flip — no single run dips below).
Also record a **gpt-4o** replay on the same split as the comparability anchor (diagnostic,
non-gating — the round-1 REFUSE was on gpt-4o).

---

## Open blockers this scaffold surfaces (honest)

1. **α needs human labels** — cannot be fabricated. This dir is empty of results until two
   humans label both sheets blind. The author's intended `gold_leak` is deliberately NOT the
   gold (spec FR-3 forbids self-labeling the surface the re-cert scores on).
2. **The split oversamples the OVERFLAG-1 clean patterns on purpose** (open probes / rule-
   teaching / partial sorts). That is the point: it stress-tests whether the v2 carve-out
   stopped the over-flagging. If those label `false` with high agreement and the `R-LEAK-*`
   rows stay `true`, the split is doing its job.

See the parent bundle [`../../../plan/coach-fresh-recert-split.plan.md`](../../../plan/coach-fresh-recert-split.plan.md).
