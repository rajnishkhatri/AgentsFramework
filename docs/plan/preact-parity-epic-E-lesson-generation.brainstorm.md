---
title: 'Epic E — Lesson generation & structure · Stage-1 sub-brainstorm'
type: brainstorm
epic: E
stage: 1
scope: 'refines D1 (author-the-bank) — HOW lessons are structured + authored + verified'
date: 2026-07-11
status: Open — awaiting human direction gate
parent: docs/plan/preact-parity-epic-E.brainstorm.md
board: docs/plan/preact-parity-sprint-board-E.md
research:
  - 'research/eng_coach_v2_pedagogy_spec.md (722-line pedagogy spec — FILED IN-REPO 2026-07-11; §7.1 faded examples, §9.4 Skill-screen binding, §3.3 misconception lib, §3.6 content lint, §11 autograder)'
  - 'research/act_english_item_generation_prompt.md (B2 generator-prompt template pattern) + act_english_authoring_qa_playbook.md (QA cascade) + act_english_llm_ranking_for_generation.md (generator model choice)'
  - 'docs/plan/act-english-rule-taxonomy.spec.md (D5 rule_type: fact|procedure|meta)'
  - 'docs/adr/0021-bank-backed-practice-scheduler.md + components/hint_generation.py + prompts/hint_generator.j2 (cascade precedent to mirror)'
---

# Epic E — Lesson generation & structure · **Sub-brainstorm**

**Why this exists.** The parent gate chose **D1 — author the tutorial bank now** with the lesson
**included** in E1. D1 answered *"do we author?"* — **yes**. It did **not** answer the two questions
that actually shape the spec: **(a) what STRUCTURE does a lesson have** (the `Tutorial` schema's flat
`body_md`+`examples[]` vs. the prototype's richer faded-example structure), and **(b) HOW is a lesson
authored + verified** so `reviewed=true`/`generated_from` are earned, not forged. This sub-brainstorm
settles those, grounded in research the sweep found — it **refines D1, does not re-decide it.**

> **Key context from the research sweep (2026-07-11).** The lesson structure is **already designed**
> in `eng-coach-v2.md` (a 722-line instructional-design spec) and its §9.4 binding table maps every
> Skill-screen region to a source. The item bank already carries per-item lesson atoms (`rule`,
> `whyCorrect`, `heuristic`). The misconception library (16 tags, 4-rung ladder, leakage-linted) is
> the exact "why you missed" source. So this is **not blank-canvas ideation** — it's picking among
> already-specified structures and deciding the authoring path. **Caveat: the richest source
> (`eng-coach-v2.md`) lives in a SIBLING dir outside the git repo — it must be brought in (or cited)
> before the spec can lean on it.**

---

## 1. What the research already fixes (premises, verified)

| # | Fact | Source |
|---|------|--------|
| R1 | **The Skill screen's every region already has a designated source.** Rule+examples → *authored (bank/lib-derived)*; Faded cards → *authored + transform*; "Why you missed" → *misconception `lib[tag].label + hint`*; accuracy bars → *[PROD] history*; due → *[PROD] scheduler*. | `eng-coach-v2.md` §9.4 binding table |
| R2 | **The lesson body has a designed structure richer than `Tutorial`'s flat shape:** `skill.faded[]` = 3 backward-fading cards (**Worked example ●●● → Completion ●●○ → Independent ○○○**), each `{kind, sub, prob, steps[], answer}`. Fading is CLT / expertise-reversal grounded; [PROD] is mastery-adaptive. | `eng-coach-v2.md` §7.1 |
| R3 | **The item bank already holds per-item lesson atoms.** Every `Item` carries `rule` (one-line rule), `whyCorrect`, `heuristic` (reusable worked heuristic), `selfExplain`, `standardLabel`. So "the rule, in one line" (SD-2) **may aggregate from existing items on the skill**, not be net-new prose. | `eng-coach-v2.md` §3.2; repo `Question`/bank |
| R4 | **`rule_type` taxonomy exists** (`fact\|procedure\|meta`), clusters by skill (punc→fact, rhetoric→meta, style→procedure), with a rubric for *when* to surface each. A ready-made **organizing axis** for the rule line. | `docs/plan/act-english-rule-taxonomy.spec.md` (D5, Draft) |
| R5 | **"Why you missed" is the misconception library, already built + linted.** 16 tags, each `{label, pump, hint, prompt, assertion}`, leakage-lint (`leaks()`) gates `pump/hint/prompt`. SD-3 = `lib[tag].label + hint` per the learner's real miss tags. | `eng-coach-v2.md` §3.3, §3.6 |
| R6 | **The authoring/verification cascade already exists for questions+hints** — the precedent D1 must mirror. Generator → schema-parse → **leakage lint** → dup/similarity → only then `reviewed=True`; failures quarantine, never serve. Same predicate as the autograder. | `components/hint_generation.py`, `prompts/hint_generator.j2`, ADR-0021/0015; `eng-coach-v2.md` §3.6, §11.1 |
| R7 | **`Skill` carries `description` + `share_of_test_pct` + `name` + `accent_var`** but **no rule/examples** — SD-1 header is fully sourced; SD-2 body genuinely needs its own store. | `frontend/lib/wire/engine_entities.ts:34-44` |
| R8 | **`Tutorial` schema is flat:** `body_md: string`, `examples: string[]`, `generated_from`, `reviewed`. It can hold prose + example strings but **NOT the structured `faded[]` cards** (steps, scaffold dots, blank-row) without either encoding them in markdown or extending the schema. **This is the central structural tension.** | `frontend/lib/wire/engine_entities.ts:272-282` |
| R9 | **Phasing already assigns this work:** v2 §14.3 — **P1** = full data model + content lint + acceptance suite; **P4** = content scale-up via lint. Faded-card *adaptivity* is [PROD]/P2; the 3-card *display* is the authoring/reference form (shippable at P1). | `eng-coach-v2.md` §14.3, §7.1 FR-SC-2 |

**The tension in one sentence:** the **screen** wants the structured 3-card faded lesson (R2), but the
**`Tutorial` schema** is flat prose+examples (R8) — so either the lesson is *simpler than the
prototype* (flat), the *schema grows* to hold `faded[]`, or the faded structure is *encoded inside
`body_md`* markdown. That choice (§2 axis A) is the real structural decision.

---

## 2. Two decision axes (structure × authoring source)

The design space is a 2×N grid: **Axis A = what shape the lesson takes** (constrained by R8's flat
schema) × **Axis B = where the content originates** (constrained by R3/R6's existing atoms + cascade).

### Axis A — lesson STRUCTURE (how rich, and how it fits `Tutorial`)

**A1 — Flat prose + examples (fit the schema as-is).** `body_md` = the one-line rule + a short
explanation; `examples[]` = worked-example strings. **No faded cards.** SD-2 renders rule + a list of
✓ examples (the §9.4 "Rule + ✓ examples" row), *not* the 3-card fade.
- *Buys:* zero schema change; ships the spec's literal SD-2 ("rule in one line" + worked examples);
  smallest build. The faded cards are a §7.1 *enhancement*, not required by §5.6's SD-2 text.
- *Costs:* drops the pedagogically-strongest feature (backward fading, CLT-grounded). Less than the
  prototype shows.
- *Stresses:* nothing — pure fit.

**A2 — Extend `Tutorial` with a structured `faded[]` field (build the full §7.1 lesson).** Grow the
schema to carry the 3-card fade; SD-2 renders Worked→Completion→Independent.
- *Buys:* full parity with the prototype + the pedagogy spec's centerpiece; the mastery-adaptive
  [PROD] path (R9) has a home.
- *Costs:* **schema change to a wire kernel** (`engine_entities.ts`) → wire-drift baseline update +
  Python mirror (W2) + `⚠️ Ask first` (trust/type-adjacent). Authoring burden per skill is much
  higher (steps, scaffold levels). Adaptivity is [PROD]/P2 anyway, so P1 ships the static 3-card form.
- *Stresses:* W2 (wire mirror), F2 (no schema sprawl), the ADR surface.

**A3 — Encode the faded cards inside `body_md` markdown (no schema change, full structure).** Author
the 3 cards as structured markdown sections in `body_md`; the view parses/renders them.
- *Buys:* full faded lesson with **zero schema change**; keeps `Tutorial` flat on the wire.
- *Costs:* pushes structure into an unvalidated string — the leakage lint + schema checks can't see
  card boundaries; renderer must parse markdown conventions (brittle). A "structured data as
  markdown" smell.
- *Stresses:* content-lint coverage (R6) — the cascade can't validate what it can't parse.

### Axis B — content SOURCE (where lesson text comes from; all under D1's "authored" umbrella)

**B1 — Aggregate from existing item atoms (derive-then-review).** Build the first draft of `body_md`
(rule) + `examples[]` by **pulling from the bank items already on the skill** (`rule`, `heuristic`,
`whyCorrect` per R3), then a human reviews/edits → `reviewed=true`, `generated_from="bank-aggregate:<skill>@<rev>"`.
- *Buys:* content already exists per-item (R3) — this is the cheapest *truthful* path; provenance is
  honest (it genuinely came from reviewed items); consistent voice with the drill.
- *Costs:* per-item rules may not generalize to one skill-level rule without editing; needs a human
  pass (that's the point — earns `reviewed`).
- *Stresses:* none — this IS the cascade (R6) applied to aggregation.

**B2 — LLM-generate from a `tutorial_generator.j2`, then run the cascade (mirror hints exactly).**
New generator prompt → draft `body_md`+`examples[]` → schema-parse → **leakage lint** → human/judge
review → `reviewed=true`, `generated_from="llm:<model>@<promptrev>"`.
- *Buys:* exact mirror of the shipped hint/item cascade (R6) — proven pattern, scales to all skills;
  provenance truthful (names the model + prompt rev + review).
- *Costs:* new prompt + a `tutorial_generation.py` component + a judge/lint for tutorial quality (the
  leakage lint is for answer-leakage; tutorial "quality" may need its own rubric — an eng-coach-judge
  hook). LLM cost + review cadence (v2 OQ-6).
- *Stresses:* `⚠️ Ask first` (new component + prompt + possibly a new judge seam); demand-side note —
  authoring is one-time offline, not a per-serve call, so cost is bounded.

**B3 — Hand-author from the pedagogy spec's canonical examples.** A human writes each skill's lesson
directly, using `eng-coach-v2.md` §4 canonical sample + the `rule_type` rubric as the template.
- *Buys:* highest quality/voice control; no generator infra; `generated_from="hand:<author>@<date>"`
  is the most honest stamp.
- *Costs:* pure calendar cost; doesn't scale past the in-scope skills; no reusable pipeline (P4
  scale-up would still need B1/B2).
- *Stresses:* none structurally; it's the "author it yourself" baseline.

---

## 3. Dependency structure + the real decision

- **Axis B is nearly settled by the constitution.** Whatever the source, it MUST pass the **same
  cascade as questions/hints** (R6) to earn `reviewed=true` — else it's a forged stamp (the parent
  brainstorm's #1 obligation). So B1/B2/B3 differ only in **who writes the first draft**; the
  *verification gate is identical and non-negotiable*. B1 (aggregate) is the cheapest truthful draft
  because the atoms already exist (R3); B2 (LLM+cascade) is the scalable one; B3 is the fallback.
- **Axis A is the genuine open decision.** It trades **parity/pedagogy (A2/A3)** against **schema
  simplicity + ship speed (A1)**. Note R9: fading *adaptivity* is [PROD]/P2 regardless, so even A2
  ships a *static* 3-card form at P1 — the A1-vs-A2 gap at P1 is "list of examples" vs "3 labeled
  cards," not "no fade" vs "adaptive fade."
- **Bringing the research in-repo is a do-regardless prerequisite.** `eng-coach-v2.md` §7.1/§9.4 and
  the misconception `lib` are load-bearing for the spec but live in a sibling dir. Either copy the
  relevant sections into the repo (an OKF research bundle) or the spec cites an out-of-tree file it
  can't guarantee. **This should happen before sdd-spec regardless of A/B picks.**

---

## 4. Leading direction + hypotheses (for the gate)

**Proposed lead: A1 structure (flat, ship §5.6 literally) + B1 source (aggregate from item atoms,
run the cascade), with A2 (faded cards) as an explicit P2 enhancement.**

- **Works *because* X:** §5.6's SD-2 literally asks for "the rule, in one line" + "worked examples" —
  A1 delivers exactly that with no schema change (R8 fit). B1's source already exists per-item (R3),
  so the first draft is real content, not invented, and the human review that earns `reviewed=true`
  is an *edit* pass, not a *write-from-scratch* pass — the cheapest truthful cascade (R6).
- **Safe *because* Y:** provenance is honest (`bank-aggregate` genuinely traces to reviewed items);
  the leakage lint + schema checks apply unchanged (no markdown-encoded structure to blind them, vs
  A3); no wire-kernel change (vs A2), so no drift-baseline/ADR-on-schema risk. The faded pedagogy
  isn't lost — it's sequenced to P2 where its *adaptivity* (the actual value, R9) also lands.
- **What re-poses it:** if you want **prototype-visual parity now** (the 3 faded cards on screen),
  the lead becomes **A2** (extend schema) or **A3** (markdown-encode) — bigger, with a schema ADR. If
  you want the **scalable pipeline** over the one-time draft, swap B1→**B2** (LLM+cascade), accepting
  a new generator component + a tutorial-quality judge.

---

## 5. Constitution / gate notes

- **A2 adds a wire-kernel schema change** → W2 (Python mirror + drift baseline) + `⚠️ Ask first` +
  the E0 ADR must cover it. **A1/A3 do not touch the schema.**
- **B2 adds a generator component + prompt (+ likely a judge)** → `⚠️ Ask first` (new abstraction +
  new prompt `.j2`); F-R5 (prompt stays a `.j2` in `prompts/`, never inline TS). **B1/B3 add no new
  runtime component** — B1 is an offline authoring script mirroring `scripts/generate_hints.py`.
- **All of B*** must run the **existing content-lint predicate** (R6) to set `reviewed=true` — this
  is the parent brainstorm's obligation #1 and is non-negotiable regardless of the pick.
- **Research-in-repo** (`eng-coach-v2.md` §7.1/§9.4 + misconception `lib`) is a do-regardless
  prerequisite (agentsframework-okf-curator can file it as a research bundle).

---

## 6. Human gate — pick per axis (two independent questions)

- **Q-LG1 (structure): how rich is the lesson body, given the flat `Tutorial` schema?**
  **A1** flat rule+examples (fit schema, ship §5.6 literally, faded cards → P2) · **A2** extend schema
  with `faded[]` (full 3-card fade now, schema ADR) · **A3** markdown-encode the faded cards (full
  structure, no schema change, lint-blind risk).
- **Q-LG2 (source): who writes the first draft (all paths run the same cascade to earn `reviewed`)?**
  **B1** aggregate from existing item atoms (cheapest truthful draft) · **B2** LLM generator + cascade
  (scalable pipeline, new component + judge) · **B3** hand-author from the pedagogy canonical (highest
  control, no pipeline).
- **Do-regardless:** bring `eng-coach-v2.md` §7.1/§9.4 + the misconception `lib` into the repo (OKF
  research bundle) before sdd-spec, so the spec cites in-tree sources.

> On accept → the `{A?, B?}` pair feeds **sdd-spec** (which also carries the parent triple {D1,
> lesson-in, resolve-pin}). Loop back if a picked structure needs a schema change you don't want to
> ADR, or if the cascade can't truthfully stamp the chosen source.

---

## 7. Accepted decision (gate closed 2026-07-11)

| Axis | Chosen | Consequence |
|---|---|---|
| **Q-LG1 structure** | **A1 — flat now, faded cards → P2** | `Tutorial` schema unchanged; SD-2 renders rule (`body_md`) + worked `examples[]` per §5.6 literally. **No wire-kernel change, no schema ADR.** The 3-card fade + its mastery-adaptivity are sequenced to **P2**. |
| **Q-LG2 source** | **B2 — LLM generator + cascade** | New **`prompts/tutorial_generator.j2`** + **`tutorial_generation.py`** component, mirroring `hint_generation.py`. Draft → schema-parse → **leakage lint** → review → `reviewed=true`, `generated_from="llm:<model>@<promptrev>"`. Scalable to all skills (P4 free). |
| **Q-LG3 research** | **Yes — file as OKF research bundle** | Bring `eng-coach-v2.md` §7.1/§9.4 + the misconception `lib` into `docs/research/` (agentsframework-okf-curator) **before sdd-spec**, so the spec cites in-tree sources. Do-regardless prerequisite — **do this first.** |

**A1 + B2 fit well:** a flat `body_md`+`examples[]` is far easier for an LLM generator to emit and for
the cascade to lint than structured faded cards would be — the two "recommended" picks compose with B2.

**⚠️ B2 adds ADR surface to E0.** Beyond the parent triple's two triggers (`insertTutorial` write seam
· `?focus=` scheduler-pin), B2 adds: the **tutorial generator component + `.j2` prompt** (new
abstraction + F-R5 prompt-in-`prompts/`), and **likely a tutorial-quality judge** — the existing
leakage lint catches *answer-leakage*, not *lesson quality* (v2 OQ-6 / §11.3 "phrasing quality
LLM-as-judge"). So E0's ADR now spans **four** decisions:
1. `insertTutorial` write seam on `EngineDb`,
2. `?focus=` → scheduler-pin (closes [[preact-drill-focus-not-pinned]]),
3. `tutorial_generation.py` + `tutorial_generator.j2` (mirror the hint cascade),
4. a tutorial-quality judge/rubric (or an explicit decision to defer it + rely on human review only).

**sdd-spec must decide: one ADR or split** (e.g. content-source+generator+judge in one; scheduler-pin
in its own, since it's a behavior change to a different seam). Raise at spec time.

**Next action order:** (1) file the research bundle (Q-LG3) → (2) advance to **sdd-spec** with the
full decision set: `{D1, lesson-in-E1, resolve-pin}` (parent) × `{A1, B2}` (this doc).
