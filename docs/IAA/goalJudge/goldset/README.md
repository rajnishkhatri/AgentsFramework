# GoalJudge Stage 5 — Golden-Set Double-Labeling Protocol (α ≥ 0.8 instrument)

> **What this is.** The double-labeling instrument that produces **Krippendorff's α ≥ 0.8** on `goal_met`
> before `goaljudge_goldset_v1` is trusted. Two annotators label gold-set items **blind**; agreement on
> the binary `goal_met` axis is scored with α. This is the gold-set-trust instrument — distinct from the
> Stage 4 rubric-validity κ.
>
> **Status (2026-06-09):** Pilot batch `gcp_goldset_pilot_2026-06-09` complete (43/43 Playwright pass).
> Double-labeling **complete** (50/50); **α = 0.8846 PASS** on `goal_met`. Stage 4 **G5 κ = 1.0 PASS**
> ([results](../goaljudge_stage4_a2_iaa_results.md)). Shadow behavioral gate **FAIL** (3/5 —
> [log](../../../research/goaljudge_stage4_shadow_execution_log.md)); Tier 2 blocked until shadow passes.
> See the [Stage 5 plan](../../../plans/goaljudge_stage5_goldset.plan.md).
>
> **α computation:** [`scripts/compute_goaljudge_stage5_alpha.py`](../../../../scripts/compute_goaljudge_stage5_alpha.py)

Mirrors the Stage-4 IAA house-style ([`../README.md`](../README.md)): blind annotators, unit-of-agreement
fixed up front, **recomputable from the CSV**.

---

## Three-tier gates (revised 2026-06-09)

| Tier | Gate | What may proceed |
|---|---|---|
| **Pilot (Tier 1)** | Instruments ready + batch traces exported | Pilot labeling by same 2 annotators; α on pilot; guideline revision |
| **Confirmation (Tier 2)** | G5 κ≥0.8 + shadow behavioral pass + G1–G10 | Unlock full ~250 assembly |
| **Dataset (Tier 3)** | α≥0.8 on full set + test-split freeze | `goaljudge_goldset_v1` trusted for Stage 6 |

**Early pilot is explicitly allowed at Tier 1** against the PROVISIONAL A2 rubric (`rubric_version=stage4_provisional`).
If Stage 4 G5 later fails or §8.4 rollback fires, mark pilot rows `superseded` and re-label after rubric revision.

---

## Two IAA numbers — do not conflate

| Instrument | Dir | Unit | Coefficient | Bar |
|---|---|---|---|---|
| **Rubric-validity** (Stage 4) | [`../`](../README.md) | Axis-A **category** (is this A2?) | Cohen's **κ** | ≥ 0.8 |
| **Gold-set-trust** (Stage 5, here) | this dir | binary **`goal_met`** per item | Krippendorff's **α** | ≥ 0.8 |

---

## Files

| File | Role | Show to annotators? |
|---|---|---|
| [`goaljudge_stage5_goldset_pilot_sheet.csv`](goaljudge_stage5_goldset_pilot_sheet.csv) | Pilot items (~50 target); blank `r1_*` / `r2_*` / `adjudicated_*` | **Yes** |
| [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md) | Pilot α report shell (filled after labeling) | No (results doc) |
| [`goaljudge_stage5_goldset_results.md`](goaljudge_stage5_goldset_results.md) | Full-run α report shell (pending Tier 3) | No |

Rebuild pilot sheet from batch JSONL:

```bash
python scripts/build_goaljudge_stage5_pilot_sheet.py
```

Research-dir cross-links (spec, firewall design): [`docs/research/goaljudge_stage5_goldset/`](../../../research/goaljudge_stage5_goldset/README.md).

There is **no committed answer key** for production traces. Gold truth = **adjudication**, not registry.

---

## Unit of agreement

Each item is labeled on the multi-axis schema ([spec §2](../../../research/goaljudge_stage5_goldset_spec.md#2-the-multi-axis-label-schema)).
**Primary agreement is on `goal_met`** — α is computed on it alone.

1. **`goal_met`** (true/false) — *the primary unit, the α axis.*
2. **`graceful_failure`** (true/false) — impossible-correctly-reported (separate axis).
3. **`partial_fraction`** (0.0–1.0) — verified subtasks ÷ total required.
4. **`failure_mode`** (a `GOAL_FAILURE_MODES` code or blank) — member-code disagreement *within* an
   agreed `goal_met=false` is **not** an α disagreement (same convention as Stage 4).

---

## Annotators and evidence discipline

- **Annotator 1:** session walkthrough analyst (Stage 4 `r1_*` complete).
- **Annotator 2:** completes Stage 4 `r2_*` **and** Stage 5 `r2_*` on the same evidence hierarchy.

Reuse Stage 4 working rules from
[`goaljudge_stage4_a2_iaa_annotator1_results.md`](../goaljudge_stage4_a2_iaa_annotator1_results.md):

1. Langfuse trace (tool trajectory + final answer) is **primary**.
2. Playwright `response_text` only on a full DOM render.
3. Grade **observed batch behavior** when it diverges from registry intent (GJ-011, GJ-003B).

**Inadmissible UI cases** (status-feed only per `verify_run`): GJ-001, GJ-003, GJ-007, GJ-011,
GJ-014, GJ-015 — Langfuse-only evidence in `evidence_summary`.

---

## Procedure (pilot — Tier 1)

1. Annotator 2 completes Stage 4 `r2_*` on the 8-anchor sheet (unblocks κ independently).
2. Both annotators blind-label the pilot sheet (`goal_met` primary; `failure_mode` metadata).
3. Adjudicate disagreements → `adjudicated_goal_met` / `adjudicated_failure_mode`.
4. Run `compute_goaljudge_stage5_alpha.py` → record in [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md).
5. **If α < 0.8:** revise guidelines on disagreements; add disambiguating examples; re-label pilot before scaling.

**Pilot success (Tier 1):** α ≥ 0.8 on pilot `goal_met`; disagreement post-mortem documented; guidelines updated for full run.

---

## Computing α

```bash
python scripts/compute_goaljudge_stage5_alpha.py \
  docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_pilot_sheet.csv
```

**Landis–Koch bands:** <0 poor · 0–.20 slight · .21–.40 fair · .41–.60 moderate · .61–.80 substantial ·
**.81–1.0 almost perfect**. **Gate: α ≥ 0.8**; **0.667** is the tentative-conclusions floor.

---

## Where this feeds

`α ≥ 0.8` on the full set is the **Tier 3 Dataset gate** that makes `goaljudge_goldset_v1` trustworthy.
Once frozen, the set hands off to **Stage 6 calibration**
([plan §12](../../../plans/goaljudge_stage5_goldset.plan.md#12-handoff-to-stage-6)).
