---
type: brainstorm
title: "Adopt Practical Synthetic Data chapters for workspace data products — SDD Stage-1 brainstorm"
description: >-
  Premise audit + candidate directions for turning docs/SyntheticDataCreation/
  (book chapters on tabular PET synthesis) into something useful for this repo —
  question-bank generation, agent-skill authoring, and other data products.
  Central finding — literal SDV/tabular synthesis is NOT the primary demand
  surface; the chapters' process discipline (prep→method toolbox→utility
  dashboard→overfit/privacy gate) can be translated, but Gen2 bank human-review
  is the present open risk that outranks a greenfield synth skill.
status: "Stage-1 OPEN — 2026-07-17"
authored: 2026-07-17
sources:
  - docs/SyntheticDataCreation/
  - docs/plan/eng-coach-gen2-v2-adoption.session.md
  - docs/questionbank/
---

# Brainstorm — Synthetic-data chapter adoption for workspace data products

**Stage 1 (SDD).** Problem as posed: *read the chapters in
`docs/SyntheticDataCreation/` and adopt them for question-bank generation,
skill generation, or any other data the workspace needs — eventually as a
coding-agent skill.*

**Constitution backdrop:** root `AGENTS.md` (invariants, ADR ratchet, no live
LLM in CI) + `components/AGENTS.md` (cascade lives here; no peer imports) +
`prompts/AGENTS.md` (H1 — all prompts `.j2`) + `frontend/AGENTS.md` (wire Zod;
generated banks under adapters) + `meta/AGENTS.md` (offline only). Binding:
`docs/skills/_sdd/binding.reference.toml` (no `.sdd/binding.toml` yet).

The request reads as “build a synthetic-data skill from the book.” The premise
audit below finds the book teaches **tabular microdata PET synthesis**
(distributions, CART/VAE/GAN, Hellinger, PSS1, privacy assurance), while this
repo’s hottest data product is **LLM-authored educational items** with a
verifier cascade — and a **1000-item Gen2 corpus already on disk, unreviewed,
not wired**. Silently continuing on “implement SDV from Chapter 5” would miss
the actual demand and collide with an open Gen2 adoption track.

---

## Premise audit

Every load-bearing premise checked against the working tree before ideation
(read-only `explore` + direct source reads).

| # | Premise (as stated / implied) | Status | Evidence |
|---|---|---|---|
| P1 | The chapters describe a method we can apply **as-written** to question-bank generation | **REFUTED** (literal) / **VERIFIED** (process analogy) | Chapters cover classical/ML distribution fitting, copulas, CART sequential synth, VAE/GAN, Hellinger, bivariate corr diffs, PSS1 distinguishability, PET spectrum (`docs/SyntheticDataCreation/*`). Bank items are structured **prose + pedagogy** with Zod `TestItem` / cascade gates — not row-level microdata sampling. Live schema: `frontend/lib/wire/engine_entities.ts` (`TestItem` object). Cascade: `components/test_item_generation.py:1-19` (`reviewed` earned, never asserted). |
| P2 | There is **no** existing bank-generation pipeline; we need greenfield synth | **REFUTED** | Gen1 live: 171 items + 513 hints via `scripts/generate_test_items.py` → cascade → `emit_test_item_bank.py` → `_test_item_bank.ts`. Gen2 docs-only: 1000 items + 12000 hints under `docs/questionbank/` (`coach-bank-gen2-qa-report.md`). Session: Gen2 **not wired** (`docs/plan/eng-coach-gen2-v2-adoption.session.md` §2.2). |
| P3 | “Skill generation” means **agent SKILL.md** authoring from the synth chapters | **UNVERIFIABLE** (ambiguous) | Two live meanings of “skill” in-tree: (a) coach `skill_id` buckets `s-rhet`…`s-sent` in batch prompt (`docs/questionbank/act-english-batch-generation-prompt.md:21-28`); (b) Cursor/Claude agent skills under `.claude/skills/`, `.cursor/skills/`, `docs/skills/` (~18 dirs each). No skill today for SDV or bank synth (explore sweep). |
| P4 | A new coding skill for synthetic data is the right first deliverable | **UNVERIFIED** (product) | Create-skill pattern exists (`~/.cursor/skills-cursor/create-skill`); repo mirrors use YAML `name`/`type`/`description` frontmatter. Whether the skill should teach **tabular SDV**, **bank QA process**, or **both** is the open product question — not settled by the chapters alone. |
| P5 | Other workspace data needs tabular synthesis (eval fixtures, gold sets, analytics) | **PARTIALLY VERIFIED** | “Synthetic” in-repo today = constructed eval scenarios (`tests/synthetic/`, GoalJudge batches, governance-trace fixtures) — **not** SDV libraries (`pyproject.toml` has no sdv/synthcity/faker). Closest skill: `llm-eval-grounded-theory` (“synthetic strata… gold sets”). Demand for true tabular PET synth is **not** evidenced by a ticket/spec — tag `needs-probe` for product priority. |
| P6 | Gen2 QA validators mean Gen2 is ready to serve | **REFUTED** | Explicit reject: “Shipping all 1000 Gen2 items because validators passed” (`eng-coach-gen2-v2-adoption.session.md` §6). All rows `reviewed: false` (`coach-bank-gen2-qa-report.md:27-28`). Path A recommended: pedagogy on reviewed Gen1 fuel first. |
| P7 | Book privacy-assurance / motivated-intruder tests apply to coach item banks | **REFUTED** (direct) / **ANALOGY** (overfit) | Item banks are original exam-faithful content, not transforms of personal microdata. The **overfit** lesson *does* transfer: generator that memorizes prompts / near-duplicates / answer leakage ≈ overfit synth model. Dup/leak gates already exist (`_DUP_JACCARD`, hint leak lint). |

### Corrected problem framing

> How do we adopt the **process discipline** from *Practical Synthetic Data
> Generation* (prep → method toolbox → utility dashboard → overfit/privacy
> gate → validation buy-in) across this repo’s real data products — starting
> with the **coach item/hint bank** (live Gen1 + candidate Gen2), optionally
> extending to **agent-skill authoring** and **eval/gold-set strata** — without
> pretending LLM educational content is SDV tabular synthesis, and without
> shipping unreviewed Gen2?

Directions below are generated over this corrected space.

---

## D0 — Present open risk (blocks capability theater)

**D0. Gen2 / v2 adoption Phase 0 is unlocked; unreviewed Gen2 must not emit**

| | |
|---|---|
| **What** | Finish the human gate already opened in `eng-coach-gen2-v2-adoption.session.md`: lock Path A/B/C, assertion policy, schema for `choice_letter`, A/B metrics — **before** any synth-skill invents a parallel bank pipeline. |
| **Why first** | 1000 items + 12k hints on disk; live serve path is Gen1 only; session hard-blocks unreviewed emit. A new “generate more synthetic items” skill increases supply while review capacity is the bottleneck. |
| **Follows** | Session Path A (recommended). |
| **What breaks if skipped** | Skill/docs that point emit at Gen2 JSON, or that treat validator-pass as `reviewed`. |
| **Invariant stress** | None new — enforces existing cascade contract (`reviewed` earned). |

---

## Six directions

### High-probability (follow existing patterns)

#### D1. Bank-process skill (map chapters → existing cascade + Gen2 QA gates)

| | |
|---|---|
| **What** | Author a project skill (`.claude/skills/` + `.cursor/skills/` + `docs/skills/` mirror) that teaches agents the **bank synthesis workflow**: quota/batch prompt → generate → cascade (schema/solver/dup) → utility dashboard (map Hellinger↔distribution gates, corr↔skill/difficulty/letter balance, PSS1↔distinguishability-from-live-bank / leak) → human review → promote → emit. Cite live scripts; forbid inventing a second pipeline. |
| **Follows** | Skill package layout (`docs/skills/code-review/SKILL.md` pattern); bank drivers in `scripts/generate_*.py` + `components/test_item_generation.py` / `hint_generation.py`; Gen2 QA report as the “utility dashboard” precedent. |
| **Tradeoffs** | High ROI for agents generating/curating banks; does **not** implement SDV. Chapter privacy PET material mostly becomes “don’t claim personal-data synthesis.” |
| **What breaks** | If skill invents new promote/emit paths outside `scripts/emit_*.py`. |
| **Ask-first?** | No new dep/service/node if skill-only. OKF skill Concept + index if mirrored under `docs/skills/`. |
| **gated-on-data** | Gen1=171 / Gen2=1000 (measured). |

#### D2. Close Gen2 as a **curated pool** using chapter “validation studies” discipline

| | |
|---|---|
| **What** | Spec the Phase-2 curate loop: sample challenging-but-representative items (Ch7: not hardest-only, not easiest-only), human review → `reviewed:true`, workload-aware utility (replicate coach analyses / student A/B metrics from session P0.6), then selective promote. Skill or runbook embeds the sampling + dashboard, not bulk emit. |
| **Follows** | `eng-coach-gen2-v2-adoption.session.md` Path A Phase 2; existing QA gates in `coach-bank-gen2-qa-report.md`. |
| **Tradeoffs** | Calendar-bound on human review; engineering time small vs wait time large. |
| **What breaks** | Treating Gen2 dump as drop-in (explicitly rejected). |
| **Ask-first?** | Wire/schema change for `choice_letter` + rung 1–4 → ADR (session P0.4/P0.5). |
| **Depends** | D0 Phase-0 locks. |

#### D3. Agent-skill authoring skill (meta-skill), chapters as **one** reference pack

| | |
|---|---|
| **What** | A thin skill for “turn a durable methodology pack under `docs/` into a project `SKILL.md`” — frontmatter, trigger description, staged workflow, reference.md for deep chapters, do-not-do list. First customer: the synth/bank skill from D1. |
| **Follows** | `create-skill` layout; OKF `type: skill`; existing dual-mirror habit (`.claude` + `.cursor` + `docs/skills`). Precedent brainstorm: `docs/plan/agentsframework-axial-coding-skill.brainstorm.md`. |
| **Tradeoffs** | Orthogonal to bank fuel; helps skill-generation ask; risk of abstraction without a first concrete skill (G1). |
| **What breaks** | Skill sprawl if every markdown folder becomes a skill without a demand trigger. |
| **Ask-first?** | G1 if it adds a new “skill factory” abstraction beyond markdown. |

### Exploratory (different abstraction / demand lens)

#### D4. Class-level **utility dashboard** for any generated corpus (bank, gold set, fixtures)

| | |
|---|---|
| **What** | Extract a shared “utility framework” module/docs: univariate similarity, bivariate structure, multivariate/workload tests, distinguishability — **parameterized by corpus type**. Bank instance: letter/skill/difficulty/NO-CHANGE + leak/dup. Eval-fixture instance: strata coverage (grounded-theory). Architecture test: next corpus without a dashboard fails a hygiene check. |
| **Follows** | Chapter 4 framework; Gen2 QA report as instance; `llm-eval-grounded-theory` strata language; TAP/eval probe pattern (`agentsframework-eval-probe`). |
| **Tradeoffs** | Class fix > one-off skill; can become abstract without a second consumer. |
| **What breaks** | Forcing Hellinger on free-text stems without a defined embedding/binning — need bank-native metrics, not cargo-cult. |
| **Ask-first?** | New shared service/component → Ask first + ADR. Prefer `scripts/` + skill docs first. |
| **Invariant stress** | If placed in `components/`, keep framework-agnostic; no peer imports. |

#### D5. Demand-side: **stop generating** — template/deterministic cascade + curate Gen2

| | |
|---|---|
| **What** | For standards with stable item shapes (span-revision + NO CHANGE), prefer deterministic templates / known-answer packs over new LLM batches; use LLM only for hard rhetorical items. Map to Ch7 “not all fields must be synthesized” + repo deterministic-cascade precedent (`components/router.py`, guardrails cascade). |
| **Follows** | Demand-side lens; session F1 (don’t integrate Gen2 as-is); AP-6 quarantine over fabricated pass. |
| **Tradeoffs** | Lower novelty / coverage speed; higher consistency; fewer overfit near-dupes. |
| **What breaks** | Batch quota research assumes LLM variety — templates may under-cover misconception diversity. |
| **Ask-first?** | No if stays in scripts/content; yes if new graph node. |

#### D6. Tabular SDV toolbox for **true microdata** surfaces only (eval analytics / privacy demos)

| | |
|---|---|
| **What** | If (and only if) we need synthetic learner-event tables, claim-like analytics, or privacy-demo datasets: implement a small method toolbox (fit → CART/copula → Hellinger/PSS1 → privacy note) behind a skill + optional `scripts/`, with explicit out-of-scope for text/banks. |
| **Follows** | Chapters 3/5/7 literally; under-used signal = none yet (no SDV dep). |
| **Tradeoffs** | Faithful to the book; **weak demand evidence** today (`needs-probe`). New dep (sdv/synthcity/etc.) is Ask-first + ADR. |
| **What breaks** | Premature dep; conflating with bank pipeline; CI live-LLM risk if generators call models. |
| **Ask-first?** | **Yes** — new dependency. |
| **gated-on-data** | `needs-probe`: who consumes tabular synth in prod? |

---

## Leading-direction hypotheses

**Lead candidate for this ask (skill-first):** **D1**, sequenced behind **D0**, with **D2** as the first real workload the skill operates on. **D3** only if “skill generation” was meant as meta-authoring. **D6** deferred until demand probe.

| ID | Hypothesis | Status | Evidence |
|---|---|---|---|
| H1 | D1 can teach the live pipeline without new emit code | **SUPPORTED** | Emit sole source: `scripts/emit_test_item_bank.py`; cascade earns `reviewed`: `components/test_item_generation.py:1-9`; Gen2 QA already lists gates the skill can checklist. |
| H2 | Chapter utility metrics map 1:1 to bank QA | **REJECTED as 1:1** / **SUPPORTED as analogy** | Hellinger/PSS1 assume comparable numeric/categorical microdata. Bank uses schema, solver agreement, Jaccard dup, letter χ², NO-CHANGE rate, leak lint (`coach-bank-gen2-qa-report.md:16-24`). Skill must **translate**, not paste. |
| H3 | Shipping a synth skill unblocks Gen2 serve | **REJECTED** | Session: human review + Phase 0 locks are blockers; validators ≠ reviewed (`coach-bank-gen2-qa-report.md:27-28`; session §6). |
| H4 | D6 is needed for `/learn` | **REJECTED (current evidence)** | `/learn` seeds Gen1 banks (`composition_engine_browser` pattern per explore); no SDV on serve path. |
| H5 | “Skill generation” = coach `skill_id` expansion | **PLAUSIBLE** | Batch prompt owns skill×standard quotas; Gen2 extended standards 33–43 (`coach-bank-gen2-qa-report.md:31-33`). That work is **content/taxonomy**, better as D1/D2 workload than a separate meta-skill — unless user confirms agent-SKILL.md intent. |
| H6 | D4 without a second consumer is premature abstraction | **SUPPORTED (G1)** | Only bank QA dashboard exists as a worked example; grounded-theory strata is conceptual. Prefer skill-embedded checklist (D1) until a second corpus demands a shared module. |

---

## Dependency map

```text
Do-regardless (hygiene)
  └─ Keep Gen2 under docs/questionbank/ as candidate; never default emit to it
  └─ Preserve cascade contract: reviewed earned in components/, not asserted by generator

Track α — Gen2 adoption (product fuel)     Track β — Methodology skill (agent UX)
  D0 Phase-0 locks ─────────────────────┐
  D2 curate/review loop ←───────────────┤
       │                                │
       └──────── consumes ──────────────┴── D1 bank-process skill
                                            D3 meta skill-authoring (optional)
Track γ — Class dashboard (defer)
  D4 after D1 has one concrete dashboard + a second corpus asks for reuse
Track δ — Literal SDV (defer)
  D6 gated-on demand probe + Ask-first dep
Track ε — Demand-side generation restraint
  D5 can parallel Track α (templates for mechanical standards)
```

| Axis | Cost nature |
|---|---|
| D0 / D2 human review | **Calendar time** (review capacity), not eng complexity |
| D1 skill authoring | Eng time small; no ADR if skill-only |
| D6 SDV | Eng + **Ask-first dep** + unclear consumer |

Capability (bigger reviewed bank) and operational deliverable (agent skill that doesn’t ship junk) share substrate **D0+D1** — which priority the human picks is the real decision.

---

## Human gate — pick what to specify next

Direction-level acceptance only. Reply with option ids (a bare “yes” is not consent).

### Q1 — Priority track (pick one)

| Id | Choice |
|---|---|
| **A1** | **D0 → D1 → D2**: lock Gen2 adoption Phase 0, author bank-process skill, then curate Gen2 with chapter-style validation studies |
| **A2** | **D1 only** (skill from chapters + live pipeline docs); Gen2 adoption stays on its session track separately |
| **A3** | **D3 first** (meta skill-authoring), then use it to mint the bank/synth skill |
| **A4** | **D6** literal tabular SDV toolbox (accept Ask-first dep); banks out of scope |
| **A5** | **D5 + D2**: stop new LLM batches; curate Gen2 + templates for mechanical standards |
| **A6** | Re-pose: my intent was specifically ________ (write in) |

### Q2 — What did “skill generation” mean? (pick one)

| Id | Meaning |
|---|---|
| **B1** | Agent `SKILL.md` authoring (Cursor/Claude project skills) |
| **B2** | Coach `skill_id` / ACT standard coverage (content taxonomy + quotas) |
| **B3** | Both, but sequenced (say order) |
| **B4** | Neither — I meant the synthetic-data coding skill only |

### Q3 — Scope of the first skill body (pick one)

| Id | Scope |
|---|---|
| **C1** | Process translation only (checklist + pointers to scripts/cascades/QA metrics) — light spec carve-out OK |
| **C2** | Process + runnable dashboard script for bank corpora (Hellinger-analog metrics already in Gen2 report, automated) |
| **C3** | Full book toolbox including privacy assurance / PET decision framework (enterprise CoE material) |

### Explicitly not proposing without a pick

- New `sdv`/deep-learning deps
- Pointing `emit_*.py` at Gen2
- A shared utility-dashboard **service** before a second consumer (G1)

---

## Advance condition

On A\* + B\* + C\* acceptance → **sdd-spec** for the chosen direction with validated hypotheses H1–H6 carried forward (and H2’s “translate not paste” constraint as a non-negotiable AC).
