# GoalJudge Stage 5 — Golden-Set Double-Labeling Protocol (the α ≥ 0.8 instrument)

> **What this is.** The double-labeling instrument that produces the **Krippendorff's α ≥ 0.8** number
> on `goal_met` required before `goaljudge_goldset_v1` is trusted (Stage 5
> [plan §3.2](../../plans/goaljudge_stage5_goldset.plan.md) / [spec §7](../goaljudge_stage5_goldset_spec.md#7-iaa--the-α-gate)).
> Two or more annotators label the gold-set items **blind**; their agreement on the binary `goal_met`
> axis is scored with α. This is the gold-set-trust instrument — distinct from the Stage 4 *rubric-
> validity* κ.
>
> **Status: instrument authored, labeling not yet run.** Running it needs (a) Stage 4 **Confirmation**
> (κ ≥ 0.8 + verdict swap — the gold set labels against the *confirmed* A2 rubric) and (b) ≥2 human
> annotators on the batch traces. This directory commits the **protocol + blank template**, not results.
> See the [G3 batch runbook](../goaljudge_stage4_a2_g3_batch_runbook.md) for the trace source.

Mirrors the established Stage-4 IAA method ([`goaljudge_stage4_iaa/README.md`](../goaljudge_stage4_iaa/README.md)):
blind annotators, unit-of-agreement fixed up front, **recomputable from the CSV**. The bar and the
coefficient differ — see [§ Why α, not κ](#why-α-not-κ).

---

## Two IAA numbers — do not conflate

| Instrument | File | Unit | Coefficient | Bar | What it gates |
|---|---|---|---|---|---|
| **Rubric-validity** (Stage 4) | [`../goaljudge_stage4_iaa/`](../goaljudge_stage4_iaa/README.md) | Axis-A **category** (is this A2?) | Cohen's/Fleiss' **κ** | ≥ 0.8 | whether you may **build** the gold set |
| **Gold-set-trust** (Stage 5, here) | this dir | binary **`goal_met`** per item | Krippendorff's **α** | ≥ 0.8 | whether the **built set** is trustworthy |

The Stage-4 κ confirms the *definition*; the Stage-5 α confirms the *labeled data*. You need the first
before you run the second.

---

## Files

| File | Role | Show to annotators? |
|---|---|---|
| [`goaljudge_stage5_goldset_label_sheet_template.csv`](goaljudge_stage5_goldset_label_sheet_template.csv) | One row per item; `task` / `claim` / `evidence_summary` given; **blank** `r1_*` / `r2_*` / `adjudicated_*` columns | **Yes** (each annotator gets their own copy / column set) |

Dataset CRUD + firewall (Langfuse seam): [`services/governance/goaljudge_goldset_dataset.py`](../../services/governance/goaljudge_goldset_dataset.py).

There is **no committed answer key** here (unlike Stage 4, whose 8 anchors had registry truth). The Stage 5
gold label is **produced by adjudication**, not read from the registry — the items are ~250 real batch
traces, not the 8 registry anchors. The adjudicated column *becomes* the truth once α ≥ 0.8 is met.

---

## Unit of agreement

Each item is labeled on the multi-axis schema ([spec §2](../goaljudge_stage5_goldset_spec.md#2-the-multi-axis-label-schema)).
**Primary agreement is on `goal_met`** — the binary α is computed on it alone.

1. **`goal_met`** (true/false) — *the primary unit, the α axis.* Did the agent actually achieve the goal,
   evidence-wise? This is the class that triggers the downgrade.
2. **`graceful_failure`** (true/false) — impossible-correctly-reported (separate axis; never counts as
   goal achievement).
3. **`partial_fraction`** (0.0–1.0) — verified subtasks ÷ total required (telemetry).
4. **`failure_mode`** (a `GOAL_FAILURE_MODES` code or blank) — the Axis-A member code for the
   `goal_met=false` rows. **Member-code disagreement *within* an agreed `goal_met=false` is NOT an α
   disagreement** (same convention as Stage 4 — agreement is at the gate signal, not the finer label).

---

## Why α, not κ

Krippendorff's α (not Cohen's κ) because the gold set's labeling is the setting α was designed for
(foundation doc §C.4): **≥2 annotators**, who may **rotate** across the ~250 items, with **missing data**
(not every annotator labels every item). Cohen's κ assumes exactly two fixed raters labeling every item —
true for the Stage-4 8-anchor set, false here. α generalizes to any number of raters, any scale, and
missing data, and reduces to κ in the two-fixed-rater complete-data case.

**Landis–Koch bands** (report the band): <0 poor · 0–.20 slight · .21–.40 fair · .41–.60 moderate ·
.61–.80 substantial · **.81–1.0 almost perfect**. **Gate: α ≥ 0.8** ("reliable"); **0.667** is the
tentative-conclusions floor.

---

## Procedure

1. **Confirm the prerequisite.** Do not start until Stage 4 is **confirmed** (κ ≥ 0.8 + verdict swap) —
   the gold set labels against the confirmed A2 rubric, not the PROVISIONAL one.
2. **Pilot ~50 items first.** Label a 50-item pilot, compute α, and **revise the labeling guidelines on
   the disagreements** (the EvalGen co-construction loop) *before* scaling to ~250. Do not label the full
   set against guidelines the pilot showed are ambiguous.
3. **Label blind.** Give each annotator only the template (their own `r1_*` or `r2_*` columns) + this
   README. Annotators do not see each other's labels.
4. **Use the evidence hierarchy** ([spec §2](../goaljudge_stage5_goldset_spec.md), inherited from Stage 4
   spec §8.3): Langfuse trace (tool trajectory + final answer) is **primary**; Playwright `response_text`
   only on a full DOM render; status-feed-only UI captures are **inadmissible**.
5. **Adjudicate.** Resolve every `goal_met` disagreement to a single gold label; fill `adjudicated_goal_met`
   (and `adjudicated_failure_mode`). This adjudicated column is the gold-set truth.
6. **Score α** on the binary `goal_met` across annotators (below). Freeze the set **only at α ≥ 0.8**;
   below ⇒ revise guidelines, add disambiguating examples, re-label.
7. **Assign splits + firewall.** Synthetic-provenance items → **dev only**; build the **test** split from
   production/fresh items; content-hash and freeze it
   ([spec §9](../goaljudge_stage5_goldset_spec.md#9-dataset-field-contract)).

---

## Computing α

Krippendorff's α on the binary **`goal_met`** axis. For two raters with complete data this equals
Cohen's κ; the helper below handles the general (≥2 raters, missing values) nominal case.

```
α = 1 − (D_o / D_e)
```

- `D_o` = observed disagreement (mean over all rater-pairs within items of pairwise label mismatch).
- `D_e` = expected disagreement (same, computed from the overall label distribution as if pairs were
  drawn at random).

A throwaway helper (do **not** commit a results file here — α results are the live-run output):

```python
from itertools import combinations
from collections import Counter

def krippendorff_alpha_nominal(items: list[list[str]]) -> float:
    """α for nominal data. `items` = one list of rater labels per item (missing
    labels simply omitted; an item needs >=2 labels to contribute)."""
    # observed disagreement
    do_num = do_den = 0
    all_labels: Counter[str] = Counter()
    for labels in items:
        labels = [x for x in labels if x is not None]
        m = len(labels)
        if m < 2:
            continue
        all_labels.update(labels)
        for a, b in combinations(labels, 2):
            do_den += 1
            do_num += (a != b)
    if do_den == 0:
        return float("nan")
    Do = do_num / do_den
    # expected disagreement from the marginal label distribution
    n = sum(all_labels.values())
    De = 1 - sum(c * (c - 1) for c in all_labels.values()) / (n * (n - 1))
    return 1 - (Do / De) if De else float("nan")
```

*(For the simple two-fixed-rater complete-data case you may instead reuse the Stage-4
`cohen_kappa` helper — it returns the same number there.)*

---

## Where this feeds

`α ≥ 0.8` is the **Dataset gate** ([plan §3.2](../../plans/goaljudge_stage5_goldset.plan.md)) that makes
`goaljudge_goldset_v1` trustworthy. Once frozen, the set hands off to **Stage 6 calibration**
([plan §12](../../plans/goaljudge_stage5_goldset.plan.md#12-handoff-to-stage-6)): P/R/F1 on
`goal_met=False`, κ vs human labels, ECE (diagnostic), CoT-gaming flip-rate, terminating in the
[§2.8 enable gates](../fix2_goaljudge_rubric_feasibility_pyramid.md). The flag stays default-off
(`goal_judge_downgrade_enabled=false`) until those clear.
