# GoalJudge Stage 5 — Golden Dataset Specification

> **Status:** PREP — schema, stratification, and field contract are authorable now; the **labeled
> dataset itself is gated on Stage 4 Confirmation** (κ ≥ 0.8 + verdict swap) and is built in Phase 4 of
> the [Stage 5 plan](../plans/goaljudge_stage5_goldset.plan.md). This document is the canonical Stage 5
> artifact (the analogue of the [Stage 4 rubric spec](goaljudge_stage4_a2_rubric_spec.md)).
>
> **Date:** 2026-06-08. **Scope:** the `goaljudge_goldset_v1` multi-axis label schema, the taxonomy →
> stratum mapping, the `failure_mode` ↔ Axis-A crosswalk, the dataset field contract, and the
> public-benchmark schema-reuse table. **Out of scope:** Stage 6 calibration metrics and the §2.8 enable
> gates; the live labeling run.
>
> **Foundation (READ FIRST):** [`rubricgoldsetreseachforgoaljudge.md`](rubricgoldsetreseachforgoaljudge.md)
> — this spec *applies* its schema/size/IAA prescription to this repo; it does not restate the research.
> **Pipeline:** [Stage 5 of the playbook](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md).
> **Taxonomy:** [phase 3 axial coding §3](goaljudge_phase3_axial_coding.md). **Rubric the set labels
> against:** [Stage 4 A2 spec](goaljudge_stage4_a2_rubric_spec.md). **Schema binding:**
> [`components/schemas.py`](../../components/schemas.py) `GoalVerdict` + `GOAL_FAILURE_MODES`.

---

## Table of contents

- [1. Purpose](#1-purpose)
- [2. The multi-axis label schema](#2-the-multi-axis-label-schema)
- [3. `failure_mode` ↔ Axis-A crosswalk](#3-failure_mode--axis-a-crosswalk)
- [4. Stratification design](#4-stratification-design)
- [5. Item sourcing and provenance](#5-item-sourcing-and-provenance)
- [6. Size and split discipline](#6-size-and-split-discipline)
- [7. IAA — the α gate](#7-iaa--the-α-gate)
- [8. Public-benchmark schema reuse (definitions, not items)](#8-public-benchmark-schema-reuse-definitions-not-items)
- [9. Dataset field contract](#9-dataset-field-contract)
- [10. References](#10-references)

---

## 1. Purpose

The golden dataset is the **trust anchor** for the GoalJudge: a stratified, double-labeled set the judge
is *scored against* in Stage 6. Stage 4 confirmed *whether the A2 definition is right* (κ on the
category); Stage 5 measures *how well the judge applies it* (precision/recall on a labeled set). These
are different instruments — see [§7](#7-iaa--the-α-gate).

This spec is the **schema-and-design half** (authorable now). The **labeling half** is gated on Stage 4
Confirmation per the [plan §2](../plans/goaljudge_stage5_goldset.plan.md).

---

## 2. The multi-axis label schema

Each gold-set item carries the foundation doc's multi-axis schema (§C.2), collapsed to binary for the
gate. Every axis binds to an existing `GoalVerdict` field — so a labeled item and a judge verdict are the
**same shape**, and Stage 6 scoring is a field-by-field comparison.

| Axis | Type | Gate role | `GoalVerdict` binding | Notes |
|---|---|---|---|---|
| `goal_met` | bool | **gate signal + α unit** | `goal_met` | the only field the downgrade reads |
| `graceful_failure` | bool | metadata | `graceful_failure` | impossible-correctly-reported ≠ goal achieved |
| `partial_fraction` | float 0..1 | metadata | `partial_fraction` | verified subtasks ÷ total required |
| `failure_mode` | enum∣null | **stratum label** | `failure_mode` ([§3](#3-failure_mode--axis-a-crosswalk)) | Axis-A member code; null = pass/unclassified |
| `evidence_spans` | list[str] | audit | `per_criterion[].evidence` | observable tool-output/state per condition |
| `split` | {dev,test} | held-out discipline | dataset field | test split frozen + hashed |
| `provenance` | {production,synthetic} | contamination firewall | dataset field | synthetic ⇒ dev only |

> **Binarization is inherited, not re-derived** (Stage 4 spec §7): partial ⇒ `goal_met=false`;
> correct-impossible ⇒ `goal_met=false` + `graceful_failure=true`; fabricated-impossible ⇒
> `goal_met=false` + `graceful_failure=false`. The gold set labels to this contract so the judge is
> scored on the same rule it is prompted with.

---

## 3. `failure_mode` ↔ Axis-A crosswalk

The `failure_mode` axis is the **closed vocabulary** `GOAL_FAILURE_MODES`
([`components/schemas.py`](../../components/schemas.py)) — the **16 active Axis-A member codes**, kept in
sync with the executable registry's `target_code` values (drift-guarded by
`TestFailureModeEnumIntegrity`). `correct-complete` (pass baseline) and `tool-stub-limitation` (retired →
Axis-B B5) are **not** failure modes.

| Axis-A category ([phase 3 §3](goaljudge_phase3_axial_coding.md)) | `failure_mode` member codes | v1 labeling density |
|---|---|---|
| **A1 · semantic / synthesis** | `missing-requested-information`, `incomplete-synthesis`, `fluent-evasion`, `criteria-mismatch` | best-available |
| **A2 · corrupt-success** | `subtask-dropped`, `partial-counted-as-full`, `fabricated-progress` | **dense (confirmed criterion)** |
| **A3 · error & exception** | `raw-error-propagation`, `tool-error-misread`, `non-existent-file-error` | best-available |
| **A4 · feasibility & gracefulness** | `graceful-failure-honest`, `impossible-task-reported`, `impossible-task-unhandled`, `premature-impossible` | best-available |
| **A5 · process quality** | `right-answer-wrong-process`, `goal-met-but-unsafe-wasteful` | best-available |

**Why all five are in the enum even though v1 only confirms A2.** The gold-set schema must be **stable
across the A1–A5 rollout** — adding a category later must not require re-labeling existing items against a
changed enum. So `failure_mode` carries the full Axis-A vocabulary from day one; v1 simply *samples the
A2 strata densely* (it is the confirmed criterion and the CoT-gaming red-team stratum) and labels the
others as traces are available.

---

## 4. Stratification design

The Stage-3 Axis-A categories **define the strata** (foundation doc §C.4: "the taxonomy defines the
strata"). The gold set must contain enough of each `goal_met=False` category — especially
`fabricated-progress` — to estimate **per-category** precision/recall in Stage 6.

### 4.1 Composition target

Foundation doc §C.4 standard composition, **oversampling the `goal_met=False` and impossible strata**
(the downgrade decision depends on them):

| Stratum | Share | What it is |
|---|---|---|
| Representative | ~40 % | typical production tasks across domains (D1) |
| Boundary | ~30 % | the contested A1/A2, A2/A5, A2/A3 seams (Stage 4 spec §4.2) |
| Edge | ~20 % | rare combinations (blocked-tool → prose → claimed done; conditional else-branch drop) |
| Impossible | ~10 % | genuinely-impossible tasks (graceful vs hallucinated-completion) |

Within these, **oversample `goal_met=False`** so the trigger class is well-estimated, and ensure each A2
member code clears a minimum count for per-code P/R.

### 4.2 Domain spread (D1, from the corpus dimension space)

Spread strata across the corpus D1 domains — file_io, computation/math, web/retrieval, shell,
multi-tool composite, knowledge-only — so calibration is not a single-domain artifact
([synthetic corpus plan](../plans/goaljudge_synthetic_saturation_corpus.plan.md) D1–D5).

---

## 5. Item sourcing and provenance

| Source | Split eligibility | Provenance | Notes |
|---|---|---|---|
| Stage 4 G1/G2 batch traces (registry-joined, `eval.goal_judge`-bearing) under `synthetic-saturation-user` | **dev + test** | `production` | the real-trace backbone; double-labeled |
| Synthetic augmentation of scarce strata (corpus generator) | **dev ONLY** | `synthetic` | *generate inputs, ground in real constraints, verify the case triggers the intended scenario*; never in test |
| Fresh human-authored tasks (reusing public-benchmark *schemas*) | **dev + test** | `production` | dodge contamination/decay; the final-calibration backbone |

> **The firewall is structural, not advisory.** `provenance=synthetic ⇒ split=dev` is an asserted
> invariant at assembly time ([plan §8.2](../plans/goaljudge_stage5_goldset.plan.md)). The held-out test
> split is built **only** from independent production/fresh items and is hash-frozen — the EvalGen
> criteria-drift mitigation (a split you never tune on).

---

## 6. Size and split discipline

- **Size:** ~250 items — validates 80 % human–judge agreement at 95 % CI (binomial proportion;
  foundation doc §C.6). Allocate extra to the higher-variance `goal_met=False` class.
- **Split:** dev/test ≈ 60/40. **Never** iterate the rubric/prompt on the test split.
- **Freeze:** content-hash the test split; diff the hash on every Stage-6 run to prove it was untouched.
- **Refresh:** re-check α quarterly; alert on α drop; rebuild from production failures (foundation doc
  §C.6).

---

## 7. IAA — the α gate

**Two IAA numbers exist in this pipeline; do not conflate them.**

| Instrument | Stage | Unit | Coefficient | Bar | Gates |
|---|---|---|---|---|---|
| Rubric-validity | **4 (G5)** | Axis-A **category** (is this A2?) | Cohen's/Fleiss' **κ** | **≥ 0.8** | whether you may *build* the gold set |
| Gold-set-trust | **5** | binary **`goal_met`** per item | Krippendorff's **α** | **≥ 0.8** | whether the *built set* is trustworthy |

**Why α (not κ) for the gold set.** Krippendorff's α generalizes to ≥2 annotators, any measurement
scale, and **missing data** — the realistic gold-set setting where annotators rotate and some items are
partially labeled (foundation doc §C.4). Stage 4 used Cohen's κ because it had exactly two raters on one
nominal category; the gold set will not.

**Procedure** (the [protocol dir](goaljudge_stage5_goldset/) owns the operational form): pilot ~50 items
→ compute α → revise guidelines on disagreements (EvalGen co-construction) → scale to ~250 → ≥2 blind
annotators per item → adjudicate disagreements to a gold label → score α on `goal_met` → freeze only at
**α ≥ 0.8** (≥0.667 floor; below ⇒ revise + re-label). Member-code disagreement *within* an agreed
`goal_met=False` is **not** a `goal_met` disagreement (agreement is at the gate signal).

---

## 8. Public-benchmark schema reuse (definitions, not items)

Borrow ground-truth **definitions**, not items, for the held-out test (foundation doc §B / catalog) —
authoring fresh tasks dodges contamination/decay:

| Benchmark | Reusable definition | Applies to |
|---|---|---|
| τ-bench / τ²-bench (arXiv 2406.12045) | deterministic end-state == goal state | `goal_met` ground truth where goals map to inspectable state |
| TheAgentCompany (arXiv 2412.14161) | checkpoint partial-credit (`S_full` iff all checkpoints) | `partial_fraction` thresholding; A2 partial strata |
| WebArena (arXiv 2307.13854) | **unachievable tasks** + programmatic predicates | impossible stratum; A4 (heed the over-credit-premature-"N/A" caveat) |
| AgentBoard (arXiv 2401.13178) | annotated subgoals + progress rate | goal decomposition; A2 subtask accounting |
| AgentRewardBench (arXiv 2504.08942) | expert success labels + reviewer protocol | the double-labeling protocol shape |
| SWE-bench Verified (deprecated Feb-2026) | test-based pass/fail | **cautionary** — contamination/decay; reuse *protocol*, not items |

---

## 9. Dataset field contract

`goaljudge_goldset_v1` (Langfuse dataset) — one item per row:

```
item_id            str            stable, unique; no orphans/duplicates
task_input         str            the prompt (registry /workspace paths where applicable)
final_answer       str            the agent's final answer under judgment
evidence_digest    str            _summarize_evidence output (tool trajectory)
goal_met           bool           ADJUDICATED gold label (the α unit + gate signal)
graceful_failure   bool           gold label
partial_fraction   float 0..1     gold label (telemetry)
failure_mode       enum|null      gold label (Axis-A member code; one of GOAL_FAILURE_MODES)
evidence_spans     list[str]      observable justification per satisfied condition
split              {dev,test}     test split frozen + hashed
provenance         {production,synthetic}   synthetic ⇒ split=dev (asserted)
source_trace_id    str|null       Langfuse join back to the originating batch trace (null for fresh)
```

**Assembly invariants** (asserted at build, [plan §8.1](../plans/goaljudge_stage5_goldset.plan.md)):
`provenance=synthetic ⇒ split=dev`; `test ∩ synthetic = ∅`; `failure_mode ∈ GOAL_FAILURE_MODES ∪ {null}`;
`set(item_ids)` unique; the test split's content hash is recorded and frozen.

---

## 10. References

| # | Source | Used for |
|---|---|---|
| F1 | [Foundation: gold-set + rubric research](rubricgoldsetreseachforgoaljudge.md) | schema, size, stratification, IAA, dataset catalog — the prescription this spec applies |
| F2 | [Pipeline playbook Stage 5](goaljudge_evaluation_pipeline_open_axial_coding_rubric.md) | how the upstream coding stages feed the gold set; contamination discipline |
| F3 | [§2.8 enable-policy](fix2_goaljudge_rubric_feasibility_pyramid.md) | the terminal Stage-6 gates the gold set is built to feed |
| F4 | [phase 3 axial taxonomy §3](goaljudge_phase3_axial_coding.md) | the Axis-A categories that define the strata + `failure_mode` enum |
| F5 | [Stage 4 A2 rubric spec](goaljudge_stage4_a2_rubric_spec.md) | the rubric + binarization contract the set labels against; the §9 `failure_mode` handoff |
| F6 | [Stage 5 plan](../plans/goaljudge_stage5_goldset.plan.md) | the gating, phases, and the live/human boundary |
| F7 | [Synthetic saturation corpus plan](../plans/goaljudge_synthetic_saturation_corpus.plan.md) | the dev-split augmentation generator (D1–D5 dimension space) |

> External arXiv IDs (τ-bench 2406.12045, TheAgentCompany 2412.14161, WebArena 2307.13854, AgentBoard
> 2401.13178, AgentRewardBench 2504.08942) are carried verbatim from the foundation doc's verified
> catalog.
