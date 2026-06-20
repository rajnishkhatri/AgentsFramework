---
type: failure-taxonomy
title: 'Memory Extractor — Failure Taxonomy (skeleton)'
description: 'Category skeleton of memory-extractor failure modes.'
tags: [recipe, memory_extractor]
---

# Memory Extractor — Failure Taxonomy (skeleton)

> **Status:** SCAFFOLD — the category *skeleton* is authorable now; the
> *populated* taxonomy is gated on Stage 1–2 open/axial coding of **real
> shadow-mode extraction traces** (≥100, per the eval pipeline). Do NOT fill
> the category counts or pick the top mode from this file — those come from
> coding actual traces (AP-1: never write the rubric before coding the data).
>
> **Date:** 2026-06-17. **Scope:** the candidate failure-mode skeleton for the
> Phase-2 typed extractor (`components/memory_extractor.py`), the confound-vs-
> defect split, and the IAA target. **Out of scope:** the populated taxonomy,
> the rubric (Stage 4), the gold set (Stage 5), calibration (Stage 6).
>
> **Pipeline:** `llm-eval-grounded-theory` (Stage 0–7). **Plan:**
> [memory_layer_wiring.plan.md](../../plans/memory_layer_wiring.plan.md)
> §"Phase 2 eval workstream". **Schema binding:**
> [`components/schemas.py`](../../../components/schemas.py) `TypedMemory`.

---

## 1. Why this exists

The extractor is a **probabilistic classifier**: it decides *what is worth
remembering* and *which of the three types it is*. Two failure modes are silent
in CI and corrosive in production, so unit tests alone cannot gate write-back:

- **Over-capture** — storing trivia. Every junk memory pollutes *every future
  recall* (the top-3 budget is finite). This is the failure the precision gate
  exists for (cardinal rule 5: precision on the capture-trigger class, not
  global accuracy).
- **Mis-typing** — an episodic event filed as a semantic fact (or vice-versa),
  which corrupts type-filtered recall.

## 2. The category skeleton (candidate — populate from coded traces)

These are *candidate* axial categories to test the coding against — NOT a
finished taxonomy. Each must end up **testable and binary** (Stage 4), with the
confounds split out from genuine judge defects.

| Code | Candidate category | Defect or confound? | One-line definition |
|------|--------------------|---------------------|---------------------|
| `OVER_CAPTURE` | stored trivia / one-off | **defect** | proposed an item no future task will reuse |
| `MISTYPE_EP_AS_SEM` | episodic filed as semantic | **defect** | a one-time event stored as a standing fact |
| `MISTYPE_SEM_AS_EP` | semantic filed as episodic | **defect** | a durable preference stored as a task event |
| `MISSED_SALIENT` | dropped a real fact | **defect** | a genuinely reusable fact was not proposed |
| `STALE_PROFILE_OVERWRITE` | re-proposed known fact | **defect** | re-proposed an item already in the profile (consolidation gap) |
| `CONTENT_LEAK` | PII / secret stored | **defect (severe)** | stored content it was told not to remember |
| `EMPTY_INPUT` | nothing to extract | **confound** | window was empty / trivial — correct empty proposal |
| `BACKEND_DOWN` | store/search failed | **confound** | infra failure, not a judge defect |
| `MALFORMED_ITEM` | invalid item dropped | **confound** | schema-as-classifier guard fired (expected) |

> The confound rows (`EMPTY_INPUT`, `BACKEND_DOWN`, `MALFORMED_ITEM`) are
> already covered by the unit suite (`test_memory_extractor.py`,
> `test_memory_autocapture.py`) — they belong in the taxonomy only so coders
> don't miscount them as defects.

## 3. IAA target

Two coders independently code ≥100 shadow traces; **Cohen's κ ≥ 0.80** on the
category assignment before the taxonomy is frozen (Stage 2 gate). Saturation
(~20 traces with no new code) ends open coding (Stage 1).

## 4. First-failure discipline (Stage 1 coding rule)

For each trace, record the **first** thing wrong (AP-10: no LLM first pass —
human reads the proposed `TypedMemory[]` against the window). Questions to ask,
in order: *content leak? over-capture? mis-type? missed-salient?* The first YES
is the code.

## 5. Anti-patterns (do not commit these)

- **AP-1:** writing `prompts/memory_extractor.j2`'s rubric constraints from this
  skeleton instead of from coded traces. (The current prompt is a *starting*
  prompt; it is re-grounded after Stage 1–2.)
- **AP-3:** gating on global accuracy instead of store-class precision.
- **AP-8:** a holistic salience-Likert instead of binary per-item criteria.
