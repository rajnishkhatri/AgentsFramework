# GoalJudge Stage 5 — Golden-Set Double-Labeling Protocol (α ≥ 0.8 instrument)

> **What this is.** The double-labeling instrument that produces **Krippendorff's α ≥ 0.8** on `goal_met`
> before `goaljudge_goldset_v1` is trusted. Two annotators label gold-set items **blind**; agreement on
> the binary `goal_met` axis is scored with α. This is the gold-set-trust instrument — distinct from the
> Stage 4 rubric-validity κ.
>
> **Status (2026-06-11):** **Phase 5 COMPLETE + Phase 6 v0.9 PROVISIONAL manifest shipped.** Fresh corpus
> (79 rows) labeled by A1 + A2 blind; round-1 α = 0.2682 (grader-bug residue); 22 disagreements adjudicated;
> 79/79 frozen gold labels. Combined fresh + pilot-production sheet:
> [`goaljudge_stage5_goldset_combined_sheet.csv`](goaljudge_stage5_goldset_combined_sheet.csv) (101 rows).
> Provisional v0.9 manifest:
> [`cache/goaljudge_eval/goldset_v0_9_manifest.json`](../../../../cache/goaljudge_eval/goldset_v0_9_manifest.json)
> (hash `ad5eccc0…dbc453cd`, `provisional=true`, `floor_gap_summary` non-empty).
> **v0.9 unblocks Stage 6 development**; v1 freeze gated on Phase 4 wave 2 (~150 prompts targeting under-floor cells).
> See [v0.9 contract](goaljudge_stage5_goldset_v0_9_contract.md) for what's blessed against v0.9.
>
> **Prior gates (unchanged):** Pilot batch `gcp_goldset_pilot_2026-06-09` complete (43/43 Playwright pass).
> Pilot double-labeling **α = 0.8846 PASS** on `goal_met`. Stage 4 **G5 κ = 1.0 PASS**
> ([results](../goaljudge_stage4_a2_iaa_results.md)). Shadow behavioral gate **CLEARED — 5/5 §10.2 anchors PASS**
> ([log §v7_full](../../../research/goaljudge_stage4_shadow_execution_log.md#v7_full-re-run-2026-06-09--cleared)).
> **Tier 2 CLEARED**; Tier 3 plumbing + Phase 4 fixture **LANDED** ([assembly plan Phase 4 handoff](../../../plans/goaljudge_stage5_tier3_assembly.plan.md#phase-4--cell-targeted-fresh-task-authoring-medium-human-paced)).
>
> **Read before labeling:** [`full_set_labeling_protocol.md`](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md) — annotator runbook with the 5 refined rules + EvalGen loop.
> **α computation:** [`scripts/compute_goaljudge_stage5_alpha.py`](../../../../scripts/compute_goaljudge_stage5_alpha.py) — supports `--diff OUT.csv` for the adjudicator's working copy.
> **Assembly + freeze:** [`scripts/assemble_goaljudge_goldset.py`](../../../../scripts/assemble_goaljudge_goldset.py) — single-shot CLI: CSV → invariants → SHA-256 → Langfuse load → manifest.

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
| [`goaljudge_stage5_goldset_pilot_results.md`](goaljudge_stage5_goldset_pilot_results.md) | Pilot α report (filled — α = 0.8846 PASS) | No (results doc) |
| [`goaljudge_stage5_goldset_results.md`](goaljudge_stage5_goldset_results.md) | Full-run α report scaffold (READY; live labeling pending) | No |
| [`../../../research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md`](../../../research/goaljudge_stage5_goldset/fresh_task_authoring_guide.md) | Phase 4 cell-targeted authoring discipline (cluster table + decision tree) | **Yes** (for authors filling fresh tasks) |
| [`../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md`](../../../research/goaljudge_stage5_goldset/full_set_labeling_protocol.md) | Phase 5 annotator runbook (5 refined rules + EvalGen loop) | **Yes** (for annotators) |

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
