# Subject-Coach — Gold-set Double-Labeling Protocol (α ≥ 0.80 instrument)

> **What this is.** The double-labeling instrument that produces **Krippendorff's
> α ≥ 0.80** on the binary `answer_leakage` axis before `coach_goldset_v1` is
> trusted for the Phase-3 enable cert (`evaluate_coach_enable_gates`). Two
> annotators label gold-set items **blind**; agreement on `answer_leakage` is
> scored with α. This is the *gold-set-trust* instrument — distinct from the
> Stage-4 rubric-validity work (the axial κ over `coach_axial_v1`).
>
> **Status (2026-07-04): SCAFFOLD — awaiting human labels.** Sheets exported from
> the provisional `coach_goldset_v1` (21 scorable rows, all `dev`, `test:0`,
> `provisional=true`, `human_alpha_answer_leakage=null`). The cert is **fail-closed
> `REFUSE_PROVISIONAL`** until this instrument clears α ≥ 0.80 **and** the freeze
> populates a non-empty `test` split.
>
> Mirrors the GoalJudge Stage-5 house-style
> ([`../../goalJudge/goldset/README.md`](../../goalJudge/goldset/README.md)):
> blind annotators, unit-of-agreement fixed up front, **recomputable from the CSV**.

---

## The one unit of agreement

| Instrument | Unit | Coefficient | Bar |
|---|---|---|---|
| **Gold-set-trust** (here) | binary **`answer_leakage`** per item | Krippendorff's **α** | ≥ 0.80 |

`answer_leakage` is the operational leak test validated over 200 traces
(`docs/evals/eng-coach/coach_axial_coding.md` §3): **after the coach reply, is
more than one answer option still live?** If the reply collapses the item to one
option (directly *or* through an indirect channel — rule-naming, socratic-clothing,
strong-implication, criterion-then-verdict, cross-question), that is a leak →
`answer_leakage = true`. Calibration carry-overs from the axial pass:
- **Post-reveal verdict naming is sub-threshold** — after the learner has already
  submitted/seen feedback (`mode = post_feedback`), naming the right answer is not
  a leak.
- **Underline / locus-designation is not elimination** — pointing at *where* the
  error is does not by itself kill the other options.

Do **not** label the six pedagogy pass-axes here (`mistake_identification_pass`,
…). Those are rubric-scored by the judge, not the α instrument. This sheet is
`answer_leakage` only.

---

## Files

| File | Role | Show to annotators? |
|---|---|---|
| [`coach_goldset_annotator1_sheet.csv`](coach_goldset_annotator1_sheet.csv) | Rater 1 blind sheet; fill `r1_answer_leakage` (+ optional `r1_note`) | **Yes** |
| [`coach_goldset_annotator2_sheet.csv`](coach_goldset_annotator2_sheet.csv) | Rater 2 blind sheet; fill `r2_answer_leakage` (+ optional `r2_note`) | **Yes** |
| `coach_goldset_combined_sheet.csv` | Merged `r1_*`+`r2_*`+`adjudicated_answer_leakage`; the freeze input | No (adjudicator) |
| `coach_goldset_alpha_results.md` | α report (filled after labeling) | No (results doc) |

The two annotator sheets are **byte-identical except the `rN_*` columns** — they
carry the item context (`learner_utterance`, `coach_reply`, `question`, `mode`)
but **not** the provisional `answer_leakage` guess, so labeling is blind.

---

> **Read before labeling:**
> [`coach_labeling_walkthrough.md`](coach_labeling_walkthrough.md) — the labeler
> runbook: the operational leak test, the `mode` rule, the 5 indirect-leak
> channels, the 2 carve-outs, and worked examples from real sheet rows.

## Runbook

1. **Label blind.** Each annotator fills only their own sheet's
   `rN_answer_leakage` ∈ {`true`,`false`} for every `item_id`, applying the
   options-still-live test above. `rN_note` is optional free text (the *why*, for
   adjudication).
2. **Score α.**
   ```
   .venv/bin/python scripts/compute_coach_goldset_alpha.py \
     docs/IAA/coach/goldset/coach_goldset_combined_sheet.csv \
     --diff cache/coach_eval/coach_goldset_alpha_disagreements.csv
   ```
   (Build the combined sheet by joining the two annotator sheets on `item_id`.)
   The α math reuses `services.governance.iaa.krippendorff_alpha_nominal`
   (NaN→None on under-defined input — never 0.0). Landis–Koch band via
   `landis_koch_band`.
3. **Adjudicate.** For every `item_id` where `r1 != r2`, the adjudicator sets
   `adjudicated_answer_leakage`. The adjudicated column is the gold label.
4. **Re-freeze.** Feed the adjudicated labels back through
   `scripts/assemble_coach_goldset.py` to produce a **non-provisional**
   `coach_goldset_v1` with `human_alpha_answer_leakage ≥ 0.80` and a populated
   60/40 `test` split. Only then does `evaluate_coach_enable_gates` read metrics.

---

## Two open blockers this scaffold surfaces (honest)

1. **α needs human labels** — cannot be fabricated. This dir is empty of results
   until a human labels both sheets.
2. **The 21-row provisional set has `test: 0`.** A cert on an empty test split is
   meaningless. Closing 3.9 for real needs **more labeled rows** (the spec targets
   200–300, oversampling the leak class) so the frozen 60/40 split has a non-empty
   `test` partition. The 21-row set proves the *plumbing* (`REFUSE_PROVISIONAL`),
   not a real ENABLE/REFUSE.

See the parent bundle [`coach-goldset-enable-policy.plan.md`](../../../plan/coach-goldset-enable-policy.plan.md)
(tasks 3.7c / 3.9).
