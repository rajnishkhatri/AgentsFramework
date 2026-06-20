---
type: spec
title: 'Memory Extractor — Gold Set Specification (`memory-extract-gold-v1`)'
description: 'Specification of the memory-extract-gold-v1 gold set.'
tags: [recipe, memory_extractor]
---

# Memory Extractor — Gold Set Specification (`memory-extract-gold-v1`)

> **Status:** SCAFFOLD — the schema, stratification, and field contract are
> authorable now; the **labeled dataset itself is gated on Stage 2** (the
> frozen taxonomy + κ ≥ 0.80) and is built in Stage 5. This document is the
> canonical schema-and-design half; the labeling half is the live run.
>
> **Date:** 2026-06-17. **Scope:** the `memory-extract-gold-v1` label schema,
> the taxonomy → stratum mapping, the store-decision α-gate field, size/split
> discipline. **Out of scope:** Stage 6 calibration metrics + enable gates
> (see [03_enable_policy.md](03_enable_policy.md)); the live labeling run.
>
> **Taxonomy it labels against:** [01_failure_taxonomy.md](01_failure_taxonomy.md).
> **Schema binding:** [`components/schemas.py`](../../../components/schemas.py)
> `TypedMemory` (`type` ∈ {semantic, episodic, procedural}).

---

## 1. Purpose

The gold set is the **trust anchor** for the extractor: a stratified,
double-labeled set of `(conversation window → should-store? which-type?)`
decisions the extractor is *scored against* in Stage 6. The gate metric is
**precision on the store-trigger class** (cardinal rule 5), not accuracy —
recall is reported but not treasured (a missed fact is cheap; a polluting
store is not).

## 2. The label schema (one row = one candidate fact in a window)

Each row is **one extraction decision**, labeled analytically and **binary**
(Stage 4 rubric): is this worth storing? (pass/fail) and — if yes — is the type
correct? (pass/fail).

| Column | Meaning |
|--------|---------|
| `item_id` | stable id (`ME-####`) |
| `split` | `dev` \| `test` (test is frozen; never tune on it — AP-4) |
| `provenance` | `production-shadow` \| `synthetic` (synthetic → **dev only**, AP-5) |
| `stratum` | taxonomy stratum (see §3) |
| `window` | the conversation window shown to the extractor (the input) |
| `candidate_content` | the distilled fact under judgment (the extractor's proposal, or a held-out should-have-proposed fact) |
| `r1_should_store` | rater 1: should this be stored? (1/0) — **the α axis** |
| `r1_type` | rater 1: correct type if stored (semantic/episodic/procedural/blank) |
| `r2_should_store` | rater 2 (blind to r1) |
| `r2_type` | rater 2 |
| `adjudicated_should_store` | adjudicated gold label (the gate field) |
| `adjudicated_type` | adjudicated gold type |
| `note` | provenance / edge-case note |

## 3. Stratification (oversample the store-trigger class)

Generate **inputs** for rare strata production won't supply (Stage 3 synthetic →
dev only):

| Stratum | What it probes | Why |
|---------|----------------|-----|
| `clear_store_semantic` | obvious durable preference | store-trigger precision |
| `clear_store_episodic` | obvious task-outcome | type correctness |
| `clear_no_store` | one-off chit-chat | over-capture FP rate |
| `update_pressure` | user *corrects* a prior fact | ADD-only vs UPDATE seam |
| `pii_must_not_store` | PII the extractor must refuse | content-leak red-team |
| `three_types_one_turn` | all three types in one turn | mis-type stress |
| `boundary_salience` | borderline-worth-storing | calibration of the salience field |

Oversample `clear_store_*` and `clear_no_store` — the precision gate lives on
that boundary.

## 4. Size & split discipline

- **~200–300** double-labeled rows, stratified per §3.
- **α ≥ 0.80** (Krippendorff) on the `adjudicated_should_store` gate field
  before the set is frozen (Stage 5 gate).
- **Test split frozen** at freeze time; the prompt is NEVER iterated against it
  (AP-4). Synthetic rows are **dev-only** (contamination firewall, AP-5).

## 5. Field contract notes

- `adjudicated_should_store` is the **α axis** and the Stage-6 precision metric's
  ground truth.
- A row whose adjudicated label is "store" but with a *different* type than the
  extractor proposed counts as a **mis-type** (type pass/fail axis), not a
  store-decision miss — the two axes are scored separately.

## 6. Label sheet

A CSV template (`memory_extract_gold_label_sheet_template.csv`) with the §2
columns + two delete-before-labeling example rows lives alongside this spec.
