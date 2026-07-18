---
type: research-prompt
title: Research prompt — latest best practices for a full synthetic-data pipeline (workspace-grounded)
description: >-
  Handover brief for a research agent: supplement the SyntheticDataCreation
  chapters (in this pack) with 2024–2026 best practices for a full synthetic-data
  creation pipeline, mapped to this workspace’s real data products (coach
  item/hint banks, eval/gold strata) — not generic tabular SDV alone.
tags: [research-prompt, synthetic-data, question-bank, eng-coach, evaluation]
status: ready-for-handover
authored: 2026-07-17
pack_root: research/synthetic_data_pipeline_handover/
---

# Research prompt — Full synthetic-data pipeline best practices (workspace-grounded)

**You have been given this handover pack folder.** All baseline paths below are
**relative to this pack root** (the folder that contains this file and `README.md`).
Do not implement code. Do not write a coding skill yet. Produce a dated research
note that a later agent can use to design a pipeline / agent skill.

---

## Mission

Supplement the baseline chapters in `docs/SyntheticDataCreation/` with **current (2024–2026) best practices** for a **full synthetic-data creation pipeline** — preparation → generation method selection → utility/quality evaluation → overfit / leakage / privacy gates → human validation / ops — and map every recommendation onto **this workspace’s real data requirements**.

The chapters teach classical **tabular PET / SDV** synthesis. This repo’s hottest data product is **LLM-authored educational content** (ACT English items + hint ladders) with a verifier cascade. Research must keep that split honest: update the book where it still applies, invent the missing axes where it does not, and never pretend MCQ pedagogy is row-level microdata sampling.

---

## Baseline the agent must read first (in this pack)

Read these before external search. Cite them by the pack-relative path when claiming what the repo already does. Full file list: `MANIFEST.txt`.

### A. Book chapters (baseline to update)

| File | Topic the research must cover / update |
|---|---|
| `docs/SyntheticDataCreation/PracticleDataGeneration.md` | Distribution fitting, framing data, fit tests, overfitting dilemma |
| `docs/SyntheticDataCreation/MethodsOfDataGeneration.md` | Theory sampling, copulas, CART sequential ML, VAE/GAN, sequences |
| `docs/SyntheticDataCreation/evaluatingGenerateDataQuality.md` | Hellinger, corr diffs, AUROC, PSS1/2/3 distinguishability, workload-aware eval |
| `docs/SyntheticDataCreation/PracticalDataGenerationFinal.md` | Field types, IDs/dates/geo, lookup tables, missingness, project org, continuous feeds |
| `docs/SyntheticDataCreation/ImplementingSyntheticDataGeneration.md` | When to synthesize, PET spectrum, privacy–utility–cost–trust, pipeline / CoE |

### B. Workspace demand surface (must ground findings)

| Asset / seam | Why it matters |
|---|---|
| `components/test_item_generation.py` | Verifier cascade; `reviewed` is **earned**, never asserted by the generator |
| `scripts/generate_test_items.py` | Live Gen1 item generation job |
| `scripts/generate_hints.py` | Live Gen1 hint-ladder generation job |
| `scripts/emit_test_item_bank.py` | Emit reviewed items into the serve path |
| `scripts/emit_hint_bank.py` | Emit hints into the serve path |
| `scripts/promote_test_item_seed.py` | Seed/import promotion into the cascade |
| `frontend/lib/wire/engine_entities.ts` (`TestItem`) | Schema the bank must satisfy |
| `docs/questionbank/coach-item-bank-gen2.promoted.json` | Gen2 items on disk (inspect schema/shape only) |
| `docs/questionbank/coach-bank-hints-gen2.json` | Gen2 hints on disk |
| `docs/questionbank/coach-bank-gen2-qa-report.md` | Validators green; **all `reviewed: false`**; not wired |
| `docs/questionbank/act-english-batch-generation-prompt.md` | Quotas, difficulty, distractor/hint rules |
| `docs/plan/eng-coach-gen2-v2-adoption.session.md` | Gen2 must not emit unreviewed; Path A preferred |
| `docs/plan/synthetic-data-workspace-adoption.brainstorm.md` | Premise audit: literal SDV ≠ bank generation; process discipline *does* transfer |
| `docs/plan/act-english-full-bank.brainstorm.md` | Scale-up blockers (generate-mode teaching-payload gap); syllabus × band coverage |
| `research/act_english_authoring_qa_playbook.md` | Existing QA discipline for items/hints |
| `research/act_english_llm_ranking_for_generation.md` | Model-selection evidence already gathered (July 2026) |
| `docs/research/goaljudge_synthetic_dimension_space.md` | Other “synthetic” meaning: constructed eval strata, **not** SDV |
| `docs/research/goaljudge_stage5_goldset_spec.md` | Gold-set authoring / labeling plane |
| `docs/research/goaljudge_stage5_goldset/README.md` | Gold-set pack orientation |
| `tests/synthetic/` | Constructed eval fixtures (blackbox assertions) |
| `AGENTS.md` | No live LLM in CI; prompts via `.j2` / `PromptService`; Ask-first for new deps |

### C. Corrected problem framing (do not re-litigate)

> Adopt the **process discipline** from practical synthetic-data generation (prep → method toolbox → utility dashboard → overfit/privacy gate → validation buy-in) across this repo’s real data products — starting with the coach item/hint bank — without pretending LLM educational content is SDV tabular synthesis, and without recommending “generate more” while Gen2 review capacity is the bottleneck.

---

## Research questions (answer all)

### RQ1 — Pipeline shape (2024–2026)

What does a **modern end-to-end synthetic-data pipeline** look like in current practice (industry + research)? Cover stages, ownership, tooling, and gating. Explicitly compare to the book’s prep → synth → evaluate → privacy-assurance → consumer validation flow. What stages are new or renamed since the book’s framing?

### RQ2 — Two synthesis planes (mandatory split)

Produce **two parallel recommendation tracks** with no conflation:

1. **Plane T — Tabular / structured event & telemetry synthesis** (classic SDV/PET; only if this workspace has a real consumer).
2. **Plane C — LLM educational content synthesis** (items, distractors, rationales, hint ladders, optional standards coverage).

For each plane: preferred methods, evaluation metrics, failure modes, and “when not to synthesize.”

### RQ3 — Method toolbox update

Relative to Chapter 5 (multivariate / copulas / CART / VAE / GAN / sequences):

- What methods are still recommended in 2024–2026?
- What is considered outdated or niche?
- What new families matter (e.g. diffusion for tabular, LLM-as-simulator, constrained decoding, overgenerate-and-rank, verifier cascades, teacher-in-the-loop)?
- For Plane C specifically: cite educational-item-generation / distractor literature and how it composes with deterministic validators (schema, answer-key solver, dup/leak).

### RQ4 — Utility & quality metrics beyond Hellinger / PSS

What replaces or supplements Hellinger, bivariate corr diffs, AUROC, and PSS1–3 for:

- Tabular utility dashboards (SOTA libraries / scorecards)?
- **LLM content banks** (the book is weak here): pedagogical quality axes — single defensible key, misconception-aligned distractors, hint non-leakage, difficulty calibration, skill/standard coverage, answer-letter balance, near-duplicate detection, solve-consistency, human review sampling plans.

Map each metric to something this pack already contains (Gen2 QA report, cascade gates, playbook) vs. something missing.

### RQ5 — Overfit, leakage, privacy — honest transfer

- Where do motivated-intruder / re-identification tests **not** apply to original exam-faithful item banks?
- What is the correct **analogy** of “overfit synthetic model” for LLM banks (prompt memorization, near-dup stems, answer leakage into hints, train/test contamination with timed-test corpus)?
- What are current best practices for train/eval contamination controls and continuous regeneration feeds?

### RQ6 — Ops & human gate

Best practices for:

- Review capacity planning (sampling vs. full review; acceptance criteria for `reviewed=true`)
- Partial synthesis / hybrid real+synth (book concept) applied to “promote rich seed / Test-01 corpus vs generate new”
- Continuous feeds vs one-shot batches
- Decision criteria when **not** to generate more data (demand-side restraint)

### RQ7 — Workspace-specific recommendations

Given only this pack’s evidence, recommend a **minimal viable pipeline** for the next 1–2 quarters:

- Ordered stages
- What to measure at each gate
- What to defer (literal SDV deps, shared dashboard service, etc.)
- Explicit non-goals

Tie recommendations to existing scripts/cascades in this pack; do not invent a parallel bank pipeline that bypasses `reviewed`.

---

## Out of scope

- Implementing code, prompts, or a `SKILL.md`
- Choosing Gen2 Path A/B/C (product decision already open; research may *inform* review metrics only)
- Replacing the architecture invariants or adding `sdv`/deep-learning deps without an Ask-first case
- Generic “how to use Faker” tutorials with no workspace mapping
- Re-deriving the July 2026 LLM ranking from scratch — **cite** `research/act_english_llm_ranking_for_generation.md` and only add deltas if newer evidence appears
- Treating Gen2 JSON in this pack as reviewed/approved product fuel (it is quarantined evidence)

---

## Method constraints for the research agent

1. **Evidence over assertion.** Every load-bearing claim needs a dated citation (paper, vendor doc, standard, or pack-relative path). Prefer primary sources fetched in this research window.
2. **Date the scan.** Target literature and practitioner sources from **2024–01 through 2026-07** (context date). Flag anything older as “carried baseline.”
3. **Falsify the book where needed.** Explicit “still sound / outdated / missing” table per chapter topic.
4. **No plane conflation.** If a metric only makes sense for tabular microdata, say so; propose the Plane C analog instead of forcing Hellinger onto prose stems.
5. **Respect repo constraints** (`AGENTS.md`). No live LLM in CI; offline governed jobs OK; new Python deps are Ask-first; cascade fail-closed on teaching payload.
6. **Citation hygiene.** Do not cite abstracts you did not fetch. If a source 403s/paywalls, note the gap rather than inventing the finding.
7. **Conflict with prior brainstorm.** If fresh research overturns a claim in `docs/plan/synthetic-data-workspace-adoption.brainstorm.md`, say so in a short “deltas vs brainstorm” section.

---

## Required deliverable shape

Write one markdown research note. Preferred return path in the main repo (outside this pack):

`docs/research/synthetic_data_pipeline_best_practices_2026H2.md`

If you only have this pack writable, write:

`OUTPUT/synthetic_data_pipeline_best_practices_2026H2.md`

### Frontmatter

```yaml
---
type: research-note
title: "Synthetic data pipeline best practices (2026 H2) — workspace-grounded"
description: "Dated supplement to docs/SyntheticDataCreation/ mapped to coach banks + eval strata"
tags: [research, synthetic-data, question-bank, evaluation]
authored: YYYY-MM-DD
---
```

### Body sections (mandatory)

1. **TL;DR** (≤8 bullets) — what changed since the book; what this workspace should do next.
2. **Chapter update matrix** — rows = chapter topics; columns = Still sound / Outdated / Missing in book / Workspace mapping (Plane T vs C).
3. **Reference pipeline (2026)** — stage diagram or numbered stages with gates.
4. **Plane T findings** — only as deep as demand justifies; include “defer if no consumer.”
5. **Plane C findings** — primary depth; metrics, methods, human-review sampling.
6. **Metric catalog** — table: metric → plane → already in pack? → proposed gate → citation.
7. **Ops & review capacity** — concrete sampling / promotion recommendations for Gen1/Gen2-scale banks.
8. **Minimal viable pipeline for this workspace** — ordered; explicit deferrals.
9. **Deltas vs** `docs/plan/synthetic-data-workspace-adoption.brainstorm.md`.
10. **References** — fetched & dated; reject unseen sources.
11. **Open questions for humans** — only decisions research cannot settle (product priority, review budget, exclusivity of Test-01 corpus, etc.).

### Quality bar

- A later agent should be able to draft a process-checklist skill or an SDD spec **without re-searching**.
- Prefer pointed recommendations over literature surveys.
- If Plane T has no evidenced consumer in this pack, recommend **defer** and spend pages on Plane C.

---

## Success criteria

Research is done when:

- [ ] All RQ1–RQ7 answered with citations
- [ ] Chapter update matrix covers every baseline file in §A
- [ ] Plane T vs Plane C never conflated
- [ ] At least one concrete metric/gate proposed for each major failure mode in Plane C (key ambiguity, distractor quality, hint leak, near-dup, coverage skew, unreviewed emit)
- [ ] MVP pipeline names existing seams in this pack (cascade, scripts, Gen2 quarantine) rather than a greenfield stack
- [ ] Open human questions are few, concrete, and decision-shaped (ids the human can answer)

---

## Paste-block (short form)

```
You are a research agent. You have been given the folder
research/synthetic_data_pipeline_handover/ (or a copy of it).
Execute RESEARCH_PROMPT.md end-to-end. Read all pack baselines listed there
first, then scan 2024–2026 external best practices for full synthetic-data
pipelines. Deliver docs/research/synthetic_data_pipeline_best_practices_2026H2.md
(or OUTPUT/… if pack-only). Do not write code or a SKILL.md. Keep Plane T
(tabular PET) and Plane C (LLM educational content) strictly separate. Ground
every recommendation in this pack’s coach bank / cascade / Gen2 quarantine reality.
```
