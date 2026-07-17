---
type: research-note
title: "Synthetic data pipeline best practices (2026 H2) — workspace-grounded"
description: "Dated supplement to docs/SyntheticDataCreation/ mapped to coach banks + eval strata"
tags: [research, synthetic-data, question-bank, evaluation]
authored: 2026-07-17
---

# Synthetic data pipeline best practices (2026 H2) — workspace-grounded

> Dated supplement to the five book chapters in `docs/SyntheticDataCreation/`. Scan window: 2024-01 → 2026-07. Anything older is flagged "carried baseline." Written to be SKILL-READY: recommendations are numbered stage checklists with explicit gate thresholds, decision rules, and per-stage inputs/outputs/owners so a later agent can draft a process-checklist SKILL.md or SDD spec without re-searching. It does **not** implement the skill, code, or prompts.

## 1. TL;DR
- The book's five-stage flow (prep → synth → evaluate → privacy-assurance → consumer-validation) is still structurally sound, but 2024–2026 practice adds two renamed/new stages: an explicit **generate-then-filter / overgenerate-and-rank** stage and a **contamination-control** stage. Both are already implemented in this repo (verifier cascade + dedup/leak lint) but the book does not name them.
- Keep two planes strictly separate. **Plane C (LLM educational content: ACT English items, distractors, rationales, hint ladders)** is where this workspace has a real, evidenced consumer (`frontend/lib/wire/engine_entities.ts` TestItem schema; live 171-item bank served via `emit_test_item_bank.py`). **Plane T (tabular/telemetry SDV/PET synthesis)** has **no evidenced consumer** in this pack — recommend DEFER.
- Do not "generate more." Gen2 already produced 1,000 validator-green items + 12,000 hints, all `reviewed=false` and quarantined. The binding constraint is **human review capacity**, not generation. Spend the next 1–2 quarters building a review/promotion funnel, not a new generator.
- Tabular fidelity metrics (Hellinger distance, bivariate correlation diffs, PSS1/2/3 distinguishability) do not apply to prose stems. Replace them with **Plane C analogs**: single-defensible-key checks, misconception-aligned distractor scoring, hint non-leakage lint, IRT/LLM-simulated difficulty calibration, coverage balance, near-duplicate detection, and solve-consistency.
- AUROC/PSS distinguishability has a legitimate Plane C analog: a **solve-consistency / detector gate** (can a solver model recover exactly one key? do multiple models/samples agree?). Keep the concept, change the instrument.
- Privacy re-identification (motivated-intruder, membership-inference) largely **does not apply** to original exam-faithful item banks that contain no personal microdata. The real "leakage" risks are **answer leakage into hints, near-duplicate stems, and train/test contamination against a timed-test corpus** — treat those as the privacy-analog gates.
- Adopt **statistical acceptance-sampling (ISO 2859-1 / ANSI-ASQ Z1.4 AQL)** to flip `reviewed=true` on large batches without full manual review: zero-tolerance (c=0) for critical defects (wrong key, hint leak, schema break, dup), and a sampled AQL (e.g., 2.5) for minor defects.
- Everything maps onto existing seams (cascade, `generate_*`/`emit_*`/`promote_*` scripts, Gen2 quarantine). Do not build a parallel bank pipeline that bypasses the `reviewed` flag; do not add `sdv` or deep-learning deps without an Ask-first case (AGENTS.md).

## 2. Chapter update matrix

| Chapter topic (docs/SyntheticDataCreation/) | Still sound | Outdated / niche | Missing in book | Workspace mapping (Plane) |
|---|---|---|---|---|
| **PracticleDataGeneration.md** — distribution fitting, framing data, fit tests, overfitting dilemma | Prep discipline, "frame the data first," overfitting concern all still sound | Distribution-fitting as the *primary* method is now niche for content generation | No generate-then-filter stage; no LLM-simulator concept; overfitting treated as one coarse dilemma | Overfitting → 4 split risks: prompt memorization / near-dup stems / answer leakage / contamination (Plane C); distribution fitting (Plane T, defer) |
| **MethodsOfDataGeneration.md** — theory sampling, copulas, CART sequential ML, VAE/GAN, sequences | Copulas/CART still the pragmatic low-dep tabular default | **GAN/VAE now largely superseded by diffusion** for tabular | Diffusion (TabDDPM/TabSyn/TabDiff), LLM-as-simulator, constrained decoding, verifier cascades, teacher-in-the-loop distillation | Methods toolbox split by plane; Plane C = AIG + overgenerate-and-rank + deterministic validators |
| **evaluatingGenerateDataQuality.md** — Hellinger, bivariate corr, AUROC, PSS1/2/3, workload-aware | Workload-aware / ROI-oriented evaluation is *more* central now (SDMetrics ROI vs fidelity split) | Hellinger/PSS are tabular-only; **do not force onto prose** | Pedagogical axes (key defensibility, distractor plausibility, hint leak, difficulty calibration, coverage, dedup, solve-consistency) | Gen2 QA report already implements many analogs; each metric mapped in §6 |
| **PracticalDataGenerationFinal.md** — field types, IDs/dates/geo, lookup tables, missingness, project org, continuous feeds | Field-typing, IDs, project org still sound | Geo/lookup/missingness are tabular concerns | Schema-as-contract via constrained decoding; continuous-feed contamination control | TestItem wire schema *is* the "field types"; `emit_*` scripts are the serve contract (Plane C) |
| **ImplementingSyntheticDataGeneration.md** — when to synthesize, PET spectrum, privacy-utility-cost-trust, CoE/pipeline | "When to synthesize" + PUCT tradeoffs + Center-of-Excellence all still sound and load-bearing | Full PET spectrum (DP, motivated-intruder) is Plane-T only | Demand-side restraint ("when NOT to generate"), model-collapse caution, acceptance-sampling for the human gate | PUCT trust axis → the `reviewed` flag; CoE → cascade + governed offline jobs |

## 3. Reference pipeline (2026) — skill-extractable stages

Modern end-to-end synthetic-data pipelines in 2024–2026 practice (Fireworks AI 2025; ml4devs 2025; arXiv:2501.18493 "Examining the Expanding Role of Synthetic Data" FAccT'25; the SyGra seven-stage pattern in REDACT) converge on the stages below. Each is expressed with inputs, outputs, and gate criteria so a later skill can lift them directly.

**Stage 0 — Demand check / "when NOT to synthesize"**
- Input: named downstream consumer + evidence of shortage. Output: GO / DEFER. Owner: lead.
- Gate: DEFER if no evidenced consumer OR a validator-green unreviewed backlog already exceeds review capacity. (Workspace: Gen2 backlog exists → new generation DEFERRED.)

**Stage 1 — Preparation / framing**
- Input: seed corpus, spec (quotas, difficulty targets, standards list), wire schema. Output: per-standard × difficulty-band generation plan. Owner: content lead.
- Gate: spec is machine-readable; schema contract pinned.

**Stage 2 — Generation (method-selected per plane)**
- Input: plan + Jinja2/PromptService prompts + few-shot anchors. Output: raw candidates, overgenerated N× target. Owner: governed offline job.
- Gate: constrained-decoding / schema-valid emission (100% JSON-schema compliance is now table stakes; §5.1).

**Stage 3 — Automated filter / overgenerate-and-rank**
- Input: raw candidates. Output: ranked survivors. Owner: cascade.
- Gate: deterministic validators (schema, spec conformance, single key, per-choice rationales, ladder structure), dedup (exact + fuzzy), leak lint, letter balance, coverage.

**Stage 4 — Utility/quality evaluation ("dashboard")**
- Input: survivors. Output: scorecard. Owner: cascade + eval job.
- Gate: plane-appropriate thresholds (§6). Fail-closed on any critical-defect metric.

**Stage 5 — Overfit / leakage / privacy / contamination gate**
- Input: survivors + live bank + timed-test corpus. Output: contamination report. Owner: cascade.
- Gate: zero overlap vs served bank; near-dup below threshold; no answer leakage into hints; provenance + timestamp recorded.

**Stage 6 — Human validation / acceptance**
- Input: gated candidates (still `reviewed=false`). Output: `reviewed=true` promotion decision per acceptance-sampling plan. Owner: human reviewers.
- Gate: AQL acceptance criteria met (§7). Only here is `reviewed=true` earned.

**Stage 7 — Ops / serve / continuous feed**
- Input: reviewed items. Output: served bank (`emit_*` path). Owner: ops.
- Gate: monitoring (validation-error rate, label-distribution drift), re-decontamination on each feed cycle; model-collapse watch on any regeneration loop.

**Comparison to the book's flow:** the book's prep → synth → evaluate → privacy-assurance → consumer-validation maps 1:1 onto Stages 1, 2, 4, 5, 6. **New/renamed since the book:** Stage 0 (demand-side restraint), Stage 3 (overgenerate-and-rank / generate-then-filter — a distinct, named stage in essentially all 2024–2026 LLM pipelines), and the contamination sub-part of Stage 5 (train/eval contamination became a first-class concern post-2023).

## 4. Plane T findings (tabular/structured event & telemetry synthesis)

**Recommendation: DEFER.** This pack contains no evidenced tabular-microdata consumer. `tests/synthetic/` holds constructed eval fixtures (blackbox dataset + Langfuse assertions) and the goaljudge docs (`docs/research/goaljudge_synthetic_dimension_space.md`, `goaljudge_stage5_goldset_spec.md`) describe **constructed eval strata / gold-set authoring for an LLM-as-judge evaluator — not SDV tabular synthesis**. Adopting `sdv`/deep-learning tabular generators would trigger the AGENTS.md Ask-first dependency rule with no consumer to justify it.

Kept brief, for the record, so a future consumer can pick this up without re-searching:
- **Method state of the art (2024–2026):** diffusion has overtaken GAN/VAE for tabular fidelity — TabDDPM (Kotelnikov et al., ICML 2023), TabSyn (Zhang et al., ICLR 2024, VAE-then-diffusion in latent space), CoDi, STaSy, and TabDiff (arXiv:2410.20626, mixed-type diffusion). Copulas/CART remain the pragmatic low-dependency default; GAN/VAE are now largely superseded for fidelity (survey: arXiv:2502.17119).
- **Evaluation:** SDMetrics (DataCebo, v0.28.0) is the de-facto scorecard — Column Shapes, Column Pair Trends, NewRowSynthesis, BoundaryAdherence, DisclosureProtection, plus ROI/efficacy metrics kept explicitly distinct from fidelity. α-Precision / β-Recall / authenticity form the fidelity/diversity/authenticity triad.
- **Privacy:** motivated-intruder testing (UK ICO; ISO/IEC 27559) and membership-inference; DP synthesizers (Pereira et al., PLOS ONE, 2024-02-05).
- **When not to synthesize (Plane T):** no privacy-regulated microdata to protect and no downstream ML consumer → do not synthesize. Both conditions hold here.

## 5. Plane C findings (LLM educational content synthesis — PRIMARY DEPTH)

### 5.1 Preferred methods (2024–2026)
- **AIG (automatic item generation) with LLMs** is flexible and effective across languages/domains, but the field's own systematic review of 60 studies (Tan, Armoush, Mazzullo, Bulut & Gierl, *IJATE* 12(2):317–340, June 2025, DOI:10.21449/ijate.1602294) states verbatim: *"We found that LLMs are flexible and effective in generating various types of items across different languages and subject domains. However, many studies have overlooked the quality of the generated items, indicating a lack of a solid educational foundation."* Verdict: **generation is easy; evaluation is the moat.**
- **Overgenerate-and-rank** is the dominant quality pattern: generate N candidates, then rank/filter to top-k. Scarlatos, Feng, Smith, Woodhead & Lan, "Improving Automated Distractor Generation for Math MCQs with Overgenerate-and-rank" (BEA 2024, ACL Anthology 2024.bea-1.19; arXiv:2405.05144), *"train[ed] a ranking model to predict how likely distractors are to be selected by real students,"* while noting *"human-authored ones are still preferred over generated ones."* The Gen2 job already embodies this shape (overgenerate → deterministic filter → human accept).
- **Misconception-based distractor generation:** distractors should target specific student errors, not just be plausible-wrong. DiVERT (Fernandez et al., arXiv:2406.19356, 2024) encodes group-level misconceptions as text; Feng et al. (NAACL Findings 2024, aclanthology 2024.findings-naacl.193) show LLMs *"are less adept at anticipating common errors or misconceptions among real students"* — a load-bearing caution: LLM distractors are usually linguistically valid but not necessarily misconception-aligned.
- **Constrained decoding** for schema compliance is table stakes. Per OpenAI's launch post "Introducing Structured Outputs in the API" (Aug 6, 2024): *"With Structured Outputs, gpt-4o-2024-08-06 achieves 100% reliability in our evals, perfectly matching the output schemas"* (versus <40% for gpt-4-0613), via *"constrained sampling or constrained decoding."* Self-hosted equivalents: Outlines / XGrammar / Guidance (JSONSchemaBench, arXiv:2501.10868, 2025). **CRITICAL caveat:** structured output is not reliable output — 100% schema compliance guarantees *format*, not *semantic* correctness (Rotascale 2026). Schema validity ≠ defensible key. This is exactly why the cascade's fail-closed-on-teaching-payload design is necessary.
- **Verifier cascade / teacher-in-the-loop:** deterministic validators + solver-agreement + LLM-judge, composed so `reviewed=true` is EARNED, never asserted. This is `components/test_item_generation.py`.

### 5.2 Evaluation metrics (full catalog with thresholds in §6)
Pedagogical quality axes the book is weak on:
- **Single defensible key:** solve-consistency — multiple models/samples must recover exactly one key (SelfCheckGPT-style answer-consistency; multi-model self/cross-validation, arXiv:2502.07036, 2025).
- **Difficulty calibration:** IRT is the gold standard but needs field response data (the cold-start problem). 2024–2026 practice bridges it with **LLM-simulated students** (Zelikman et al. 2023; Liu, Bhandari & Pardos 2025) — prompt LLMs at graded ability levels and fit IRT to simulated responses. Caution: simulated students "may still misalign with real student response patterns" (Säuberli et al. 2025) and LLMs "struggle to measure item discrimination" (arXiv:2606.18709).
- **Large-scale field evidence that AI items can match experts:** Isley, Gilbert, Kassos, Kocher, Nie, Brunskill, Domingue, Hofman, Legewie, Svoronos, Tuminelli & Goel, "Assessing the Quality of AI-Generated Exams: A Large-Scale Field Study" (arXiv:2508.08314, 2025) — a field study of **91 classes / 1,686 students** across dozens of US colleges (1,208 students in 71 classes got AI exams; 478 in 20 statistics classes got AP-based exams). Using a Bayesian hierarchical 2PL IRT model, they conclude verbatim: *"the AI-generated questions performed on par with those created by experts, both in terms of their overall difficulty and their discriminative power. On average, the AI-generated items we produced were somewhat easier but also more discriminating than the expert-produced questions."* Concretely: mean difficulty β̄_AI = −0.45 vs β̄_STD = 0.35 (δβ = −0.79, 95% CI [−0.94, −0.65]); mean discrimination ᾱ_AI = 1.3 vs ᾱ_STD = 1.2; AI exams reached higher max test information (I_max = 3.85, reliability 0.79) than standardized (I_max = 2.61, reliability 0.72). The generation method was a **Self-Refine–style iterative critique loop** (OpenAI o3-mini): repeat generate → AI-judge → prompt-self-refine until 20 judge-labeled "good" items exist, then a final AI-judge round trims to the 10 hardest (checking difficulty, appropriateness, and confirming the key is correct). **Important scope note:** the authors do NOT claim AI items are safe to serve without human review; their stated limitations are statistics-only benchmarking, MCQ-only, 10-question tests, and an LLM-matched (not fully human) reference condition. Do not over-read this as "skip human review" — read it as validation of the *iterative-critique generation pattern* and the *psychometric evaluation lens*.
- **Skill/standard coverage** and **answer-letter balance** (chi-square uniformity).
- **Near-duplicate detection:** MinHash-LSH is the standard (Jaccard threshold typically 0.7–0.9; Olmo 3 (arXiv:2512.13961) uses exact→MinHash→suffix-array; large-scale LM work uses ~0.7 cosine for semantic dedup).
- **Hint non-leakage:** no key content words, letter references, or "no change" tells in hints.

### 5.3 Failure modes and "when not to synthesize" (Plane C)
- **Key ambiguity / no defensible key** → solve-consistency gate.
- **Distractor implausibility or non-misconception** → distractor plausibility + misconception-alignment scoring.
- **Hint answer leakage** → leak lint.
- **Near-duplicate stems** → dedup gate.
- **Coverage skew** → per-standard × difficulty quotas.
- **Unreviewed emit** → the `reviewed` flag + cascade fail-closed on teaching payload.
- **Model collapse on regeneration loops:** Shumailov, Shumaylov, Zhao, Papernot, Anderson & Gal, "AI models collapse when trained on recursively generated data," *Nature* 631(8022):755–759, 24 July 2024 (DOI:10.1038/s41586-024-07566-y): *"indiscriminate use of model-generated content in training causes irreversible defects in the resulting models, in which tails of the original content distribution disappear."* Practical rule: keep a human-authored/real anchor set in every regeneration cycle; never seed generation N+1 purely from unreviewed generation N output.
- **When NOT to synthesize (Plane C):** when a validator-green unreviewed backlog already exceeds review capacity (current state), OR when the target standard is already well-covered by the reviewed bank. Generate only against evidenced coverage gaps.

## 6. Metric catalog

| Metric | Plane | Already in pack? (path) | Proposed gate + threshold | Citation (dated) |
|---|---|---|---|---|
| Column Shapes / Column Pair Trends | T | No | (defer) SDMetrics overall ≥ 0.85 typical | SDMetrics docs, DataCebo 2026 |
| Hellinger distance / PSS1-3 distinguishability | T | Book only (evaluatingGenerateDataQuality.md) | Tabular-only; **DO NOT apply to prose** | book baseline (carried) |
| NewRowSynthesis (novelty vs real rows) | T→C analog | Gen2 QA report (dedup vs live bank, 0 hits) | Zero exact overlap with served bank | SDMetrics; Gen2 QA report 2026-07-16 |
| Single defensible key (solve-consistency) | C | Partial: cascade answer-key checks | Multi-sample/multi-model agreement unanimous on key; flag any disagreement | SelfCheckGPT; arXiv:2502.07036 (2025) |
| Distractor plausibility / misconception alignment | C | Playbook (research/act_english_authoring_qa_playbook.md) | Each distractor maps to a named error type; reject "impossible" distractors | Feng et al. NAACL 2024; DiVERT arXiv:2406.19356 |
| Hint non-leakage | C | Yes: cascade leak lint (key words, letter refs, "no change" on key-A) | Zero leak hits (c=0, critical) | Gen2 QA report; act-english-batch-generation-prompt.md |
| Difficulty calibration | C | Targets only (batch prompt; Gen2 difficulty histogram 1:36/2:242/3:378/4:263/5:81) | LLM-simulated-student IRT as pre-field proxy; field IRT once responses exist | Isley et al. arXiv:2508.08314 2025; Liu/Bhandari/Pardos 2025 |
| Item discrimination (IRT α) | C | No | Field-only; flag α<0.3 for review once response data exists | Isley et al. 2025; arXiv:2606.18709 |
| Skill/standard coverage | C | Yes: Gen2 skill dist (s-gram 133 / s-org 200 / s-punc 133 / s-rhet 200 / s-sent 134 / s-style 200) | Per-standard quota met ±10%; no standard at 0 | act-english-full-bank.brainstorm.md |
| Answer-letter balance | C | Yes: Gen2 (A273/B243/C242/D242, chi-square 2.82) | 25% ±3, chi-square uniform p≥0.01 | Gen2 QA report 2026-07-16; ANSI/ASQ |
| NO CHANGE key rate | C | Yes: Gen2 28.0% on 750 NO CHANGE-bearing items (target 25–33%) | 25–33% | Gen2 QA report 2026-07-16 |
| Near-duplicate detection | C | Yes: exact + Jaccard≥0.75 / difflib≥0.85, max within-standard 0.50 | Jaccard <0.75 within batch AND vs served bank | MinHash-LSH; Olmo 3 arXiv:2512.13961 |
| Schema conformance | C | Yes: per-shard validators 40/40 vs TestItem schema | 100% (constrained decoding) | JSONSchemaBench arXiv:2501.10868 2025; engine_entities.ts |
| Contamination vs timed-test corpus | C | Partial (dedup vs live bank) | Zero overlap; provenance + timestamp recorded | LiveBench/AntiLeak-Bench 2024; survey arXiv:2404.00699 |
| Reviewed flag (trust) | C | Yes: reviewed=false on all 1,000 Gen2 rows | reviewed=true only via acceptance sampling (§7) | eng-coach-gen2-v2-adoption.session.md |

## 7. Ops & review capacity

The binding constraint is Gen2 review capacity, not generation.

**Adopt acceptance-sampling to flip `reviewed=true` at batch scale.** ISO 2859-1 (1999/updated 2026) and ANSI/ASQ Z1.4 (attributes sampling indexed by AQL) give a statistically defensible way to accept a lot without inspecting every unit. Apply a **two-tier defect model**:
- **Critical defects (c=0, zero tolerance):** wrong/indefensible key, hint leaks the answer, schema violation, duplicate of a served item, rung-4 states the key. Any single critical defect in the sample → reject the whole shard, route back to generation/repair. (Critical-defect AQL is conventionally 0.)
- **Minor defects (AQL sampled):** stylistic infelicity, weak-but-valid distractor, opener repetition. Use a normal-inspection Level-II AQL (e.g., 2.5) with the ISO 2859-1 sample size and accept/reject numbers for the shard size.

**Key efficiency lever:** critical-defect gates (key, leak, dup, schema, rung-4) are cheap to run *deterministically on 100% of rows*. Run those exhaustively first; then human-sample only the residual (misconception quality, pedagogical soundness, defensibility edge cases) that machines cannot yet judge reliably. This is what lets a small reviewer budget clear a 1,000-item backlog.

**Concrete plan for the three corpora:**
- **Live 171-item bank:** already served; treat as the gold anchor. Use it as the reference set for dedup/contamination and as few-shot generation anchors.
- **Gen2 1,000 items (quarantined):** organize into inspection lots by standard/shard (Gen2 already has per-shard structure with 40/40 validators). Run all deterministic critical-defect gates on 100%. Then draw an ISO-2859-1 Level-II sample per shard and human-review for minor/pedagogical defects at AQL 2.5; accept the shard if the sample passes.
- **Gen2 12,000 hints (1,000 items × 3 wrong letters × 4 rungs):** sample at the *item* level (review all 12 hints for a sampled item together, since they share context). Run the rung-4 "states the rule but never the key" invariant deterministically on 100% as a critical-defect check.

**Hybrid real+synth ("promote rich seed vs generate new"):** prefer promoting/importing the Test-01 / rich-seed corpus through `scripts/promote_test_item_seed.py` into the cascade over generating net-new, because seed items carry human provenance and reduce model-collapse risk. Only generate against *evidenced coverage gaps* (standards 33–43 are new-standard gap-fillers: add/delete, essay purpose, intro/conclusion, ordering, division, modifiers, colons, unnecessary punctuation, precision, register — verify demand before prioritizing them).

**Continuous feeds vs one-shot batches:** for now, one-shot batch review of the existing Gen2 backlog is the correct mode. If a continuous feed is stood up later, re-run decontamination against the served bank AND any timed-test corpus every cycle, and keep a human/real anchor in every regeneration to avoid collapse.

## 8. Minimal viable pipeline for this workspace (dry run of a future skill)

Ordered stages, each with inputs → outputs, gate criteria with thresholds, and decision rules. Reads as a dry run of a future SKILL.md; does not implement it.

**Step 1 — Demand gate (restraint).**
- Input: coverage report of served 171-item bank by standard × difficulty; review-capacity estimate. Output: evidenced coverage gaps OR "no gap." Owner: lead.
- Decision rule: IF the Gen2 unreviewed backlog covers the gap → GO TO Step 4/5 (review), do NOT generate. ELSE IF a gap exists that the backlog does not cover → allow scoped generation (Step 2). ELSE → STOP (non-goal: generating into well-covered standards).

**Step 2 — Scoped generation (only if Step 1 allows).**
- Input: gap list, `docs/questionbank/act-english-batch-generation-prompt.md` spec, TestItem schema, few-shot anchors from the reviewed bank. Output: overgenerated candidates (N× target) via `scripts/generate_test_items.py` / `scripts/generate_hints.py` as an offline governed job (no live LLM in CI). Owner: governed job.
- Gate: constrained/schema-valid emission; provenance (model IDs, e.g., claude-fable-5+claude-opus-4-8) + timestamp recorded.
- Decision rule: model selection per `research/act_english_llm_ranking_for_generation.md` (do NOT re-derive the July-2026 ranking).

**Step 3 — Deterministic filter cascade (fail-closed), 100% of rows via `components/test_item_generation.py`.**
- Gate criteria (all c=0 critical unless noted):
  1. Schema conformance vs `frontend/lib/wire/engine_entities.ts` — 100%.
  2. Exactly one underlined span per span item; exactly one key.
  3. Per-choice rationales present; 4-rung ladders (pump → hint → prompt → assertion) on exactly the 3 wrong letters; rung-4 states the rule but never the key.
  4. Leak lint: no key content words, no letter references, no "no change" on key-A items — zero hits.
  5. Dedup: exact + fuzzy (Jaccard ≥0.75 / difflib ≥0.85) within batch AND vs served bank — zero hits.
  6. Letter balance 25% ±3, chi-square p≥0.01; NO CHANGE key rate 25–33%.
  7. Coverage: per-standard quota met; no target standard at 0.
- Decision rule: ANY critical failure → route row back to generation/repair; never emit. Output stays `reviewed=false`.

**Step 4 — Solve-consistency + contamination gate.**
- Input: cascade survivors + served bank + any timed-test corpus. Output: consistency + contamination report. Owner: cascade/eval job.
- Gate: multi-sample/multi-model solver recovers exactly one key with unanimous agreement (flag disagreements for human review); zero contamination overlap vs served/timed corpora.
- Decision rule: key disagreement → human-review queue as suspected key-ambiguity; contamination hit → drop.

**Step 5 — Human acceptance sampling (the ONLY place `reviewed=true` is earned).**
- Input: gated shard (`reviewed=false`). Owner: human reviewers.
- Gate: ISO 2859-1 Level-II sample; critical-defect AQL = 0, minor-defect AQL = 2.5; accept/reject numbers from the shard-size table. Humans judge only what machines cannot: misconception alignment, pedagogical soundness, defensibility edge cases.
- Decision rule: sample passes → flip shard to `reviewed=true`; sample fails on any critical defect → reject shard, return to Step 3/repair.

**Step 6 — Emit to serve.**
- Input: `reviewed=true` items/hints. Output: served bank via `scripts/emit_test_item_bank.py` / `scripts/emit_hint_bank.py`. Owner: ops.
- Gate: only `reviewed=true` rows may be emitted (the cascade earns the flag; emit never asserts it).

**Step 7 — Monitor / feed.**
- Output: per-job scorecards for validation-error rate and label-distribution drift; re-decontaminate each cycle; keep a human/real anchor set in any regeneration to avoid model collapse.

**Explicit deferrals / non-goals:**
- DEFER Plane T entirely (no consumer); do not add `sdv` or deep-learning deps (Ask-first per AGENTS.md).
- DEFER a shared dashboard *service*; start with per-job scorecards (the Gen2 QA report is already this shape).
- NON-GOAL: a parallel bank pipeline that bypasses the `reviewed` flag.
- NON-GOAL: choosing Gen2 Path A/B/C (open product decision; this note only informs review metrics).
- NON-GOAL: treating Gen2 JSON as product fuel (it is quarantined evidence).

## 9. Deltas vs docs/plan/synthetic-data-workspace-adoption.brainstorm.md
- **Confirmed:** literal SDV ≠ question-bank generation, but the *process discipline* (prep → method toolbox → utility dashboard → overfit/privacy gate → validation buy-in) transfers. Fresh 2024–2026 literature strongly supports this.
- **Refinement, not overturn:** the brainstorm's single "overfit synthetic model" analogy is best split into *four* distinct Plane-C risks — prompt memorization, near-duplicate stems, answer leakage into hints, and train/test contamination — each with its own gate (§6). The book's single "overfitting dilemma" is too coarse.
- **New since brainstorm:** (a) constrained decoding makes schema compliance ~free (OpenAI Structured Outputs, 100% vs <40%) but does NOT solve semantic correctness — reinforcing the cascade's necessity; (b) model-collapse evidence (Shumailov et al., *Nature* 2024: "tails of the original content distribution disappear") adds a concrete argument against seeding regeneration from unreviewed synthetic output; (c) acceptance-sampling (ISO 2859-1 / ANSI-ASQ Z1.4) gives a defensible statistical basis for flipping `reviewed=true` without full manual review — not present in the brainstorm.
- **No claim in the brainstorm is overturned by fresh research.**

## 10. References (fetched and dated)
- Tan, Armoush, Mazzullo, Bulut, Gierl. "A review of automatic item generation techniques leveraging large language models." *IJATE* 12(2):317–340, June 2025. DOI:10.21449/ijate.1602294 (fetched).
- Isley, Gilbert, Kassos, Kocher, Nie, Brunskill, Domingue, Hofman, Legewie, Svoronos, Tuminelli, Goel. "Assessing the Quality of AI-Generated Exams: A Large-Scale Field Study." arXiv:2508.08314, 2025 (fetched, incl. IRT parameters via primary-source extraction).
- Shumailov, Shumaylov, Zhao, Papernot, Anderson, Gal. "AI models collapse when trained on recursively generated data." *Nature* 631(8022):755–759, 24 July 2024. DOI:10.1038/s41586-024-07566-y (fetched).
- OpenAI. "Introducing Structured Outputs in the API," Aug 6, 2024 (100% vs <40% schema-match; constrained decoding).
- SDMetrics documentation, DataCebo, v0.28.0, 2026 (fetched).
- JSONSchemaBench, arXiv:2501.10868, 2025 (fetched); "Structured Output Isn't Reliable Output," Rotascale, 2026 (fetched).
- Feng et al. "Exploring Automated Distractor Generation for Math MCQs via LLMs." NAACL Findings 2024, aclanthology 2024.findings-naacl.193 (fetched).
- DiVERT, Fernandez et al., arXiv:2406.19356, 2024 (fetched).
- Scarlatos, Feng, Smith, Woodhead, Lan. "Improving Automated Distractor Generation with Overgenerate-and-rank." BEA 2024, ACL Anthology 2024.bea-1.19; arXiv:2405.05144 (fetched).
- UK ICO anonymisation guidance / motivated-intruder test (fetched); ISO/IEC 27559.
- ISO 2859-1 (AQL attributes sampling) / ANSI-ASQ Z1.4 (fetched).
- TabDiff arXiv:2410.20626; TabSyn ICLR 2024; diffusion-for-tabular survey arXiv:2502.17119 (fetched).
- Contamination survey arXiv:2404.00699; contamination-resistant benchmarks arXiv:2605.19999 (fetched).
- Self-consistency / SelfCheckGPT: arXiv:2502.07036 (fetched).
- Near-duplicate / dedup: Olmo 3 arXiv:2512.13961; MinHash-LSH practitioner sources (fetched).
- Pereira et al., "DP synthetic data … end-to-end ML pipelines for tabular data," PLOS ONE, 2024-02-05 (fetched).
- Workspace paths: `components/test_item_generation.py`; `scripts/generate_test_items.py`, `generate_hints.py`, `emit_test_item_bank.py`, `emit_hint_bank.py`, `promote_test_item_seed.py`; `frontend/lib/wire/engine_entities.ts`; `docs/questionbank/coach-bank-gen2-qa-report.md` (2026-07-16); `act-english-batch-generation-prompt.md`; `docs/plan/*.md`; `research/act_english_*.md`; `docs/research/goaljudge_*.md`; `tests/synthetic/`; `AGENTS.md`.

## 11. Open questions for humans (decision-shaped)
1. **Review budget:** how many reviewer-hours/week are available for Gen2? This sets the AQL sample size and whether the 1,000-item backlog clears in one or several quarters.
2. **Test-01 / rich-seed exclusivity:** is the Test-01 corpus exclusive/licensed such that promoting it into the served bank via `promote_test_item_seed.py` is permitted? (Determines Step-5 hybrid strategy.)
3. **Timed-test contamination scope:** is there a specific timed-test corpus the bank must never overlap with? If so, provide it so Step 4 can decontaminate against it.
4. **Coverage priority:** are new standards 33–43 (add/delete, essay purpose, intro/conclusion, ordering, division, modifiers, colons, unnecessary punctuation, precision, register) actually in product demand, or should review effort concentrate on standards 1–32 first?