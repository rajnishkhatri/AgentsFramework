# Brainstorm — Full ACT-English question bank from the IXL syllabus

**Stage 1 (SDD).** Problem as posed: "question bank is not sufficient; build a
full bank for the topics in `docs/ACT-syllabus/act-english.pdf`."
**Tree:** `main @ bf12a62`. **Syllabus:** IXL Skill Plan for the ACT — English
(12 pp): **5 score bands** (13–15, 16–19, 20–23, 24–27, 28–36) × **3 ACT
reporting categories** (Production of Writing / Knowledge of Language /
Conventions of Standard English) × **~30 recurring standards** (commas,
subject-verb agreement, parallelism, transitions, tone, redundancy, pronouns,
apostrophes, semicolons/colons, modifiers, idioms, …).

## Premise audit

| # | Premise | Status | Evidence |
|---|---|---|---|
| P1 | The bank is insufficient | **verified** | 8 items total, 1–2 per skill (`_test_item_bank.ts`). `nextReviewedQuestion` picks lowest-difficulty-first deterministically (`in_memory_engine_db.ts:109-123`) — with pool depth 1–2 a learner sees the same item every session. |
| P2 | The PDF defines the topics to cover | **verified, with a mapping gap** | It is IXL's alignment (not official ACT spec): band × category × standard. The app taxonomy is 6 flat skills (`s-punc…s-style`, `_dev_seed.ts`); PDF standards do NOT map 1:1 — a taxonomy-mapping decision is load-bearing. Natural fit: **5 PDF score bands ↔ `difficulty` 1..5** (wire already `z.number().int() // 1..5`, `engine_entities.ts:65`). |
| P3 | (implicit) "The generation pipeline scales — just run it with a bigger count" | **REFUTED — blocking defect for generate-mode** | The cascade REQUIRES the teaching payload — `context_html`, `why_correct_md`, `why_tempted_md`, `rule_md`, `item_type`, `per_choice_rationale` per letter (`components/test_item_generation.py:134-155`, fail-closed) — but `prompts/test_item_generator.j2` (38 lines) never asks for those fields. **Generate-mode output quarantines 100 % on schema.** The current 8 items came through `--import-seed` promotion of a hand-built rich seed, not generate-mode. Any scale-up must fix the prompt first. |
| P4 | (implicit) Frontend can serve a bigger bank | **verified** | Serving is data-driven: `seedTestItemBank(db)` inserts whatever rows exist; reviewed gate + per-skill filter at pick time. More ITEMS = zero code. More SKILLS = one dashboard card each (30 standards → 30 mastery cards = UX break) — taxonomy expansion is NOT free. |
| P5 | (implicit) All new content must be generated | **refuted (cheaper supply exists)** | `_test01_english_corpus.ts` holds **48 reviewed rows with the FULL teaching payload** (field census identical to bank rows modulo `stem` vs `stem_md`), skill-tagged (gram 13, punc 13, style 8, sent 6, rhet 5, org 3). Promoting them via the existing `--import-seed` cascade ≈ 56-item bank with near-zero generation cost. Cost: those items double as the timed test (practice/test leakage — exclusivity decision needed). |
| P6 | Cost of a "full" bank | **gated-on-data (bounded estimate)** | Per item: 1 generator + 1 solver graph call, plus hint ladder ≈ 3 rungs with retry risk (observed 3-attempt worst case, PR #134). A 6-skill × 5-band × 4-item matrix ≈ 120 items + 360 hint rungs — a real but one-shot LLM spend; live-LLM never in CI (offline governed job, as today). |

## Directions

**High-probability (follow existing repo patterns):**

- **D1 — Repair generate-mode, then banded scale-up.** Fix
  `test_item_generator.j2` to emit the full teaching payload (closes P3), add
  `--skill/--difficulty` cell-targeting (script already has `--count`,
  `skill_id` hook), then fill a skills × bands matrix through the existing
  cascade → `promote_test_item_seed.py` → emit. *Pattern:* the exact ADR-0015/
  0021 pipeline. *Breaks-if-chosen:* nothing structural; LLM spend (P6).
  *Stress:* none of the 8 invariants — offline job, components stay pure.
- **D2 — Promote the Test-01 corpus into the practice bank (demand-side:
  make generation not happen).** Run the 48 rich rows through the SAME
  `--import-seed` cascade (solver re-verification re-earns `reviewed`), rename
  `stem`→`stem_md`, generate their 48 × 3 hint ladders. 8 → 56 items, zero
  item-generation. *Breaks-if-chosen:* practice/test contamination — a learner
  drills the exact items the timed test serves; needs an exclusivity policy
  (split the 48, or accept overlap, or retire Test-01 as a test). *Pattern:*
  `--import-seed` promotion (task 6.5) + `generate_hints.py`.
- **D3 — Syllabus-as-data substrate.** Convert the PDF into a canonical
  `act-english-syllabus.seed.json` (band × category × standard, with a
  standard→skill mapping) + deterministic converter emitting the TS/Py
  modules; items gain a `standard_id` tag; a coverage ratchet
  (`ladderGaps` pattern, `_hint_bank.test.ts`) fails CI while any standard×band
  cell is below target. *Pattern:* the single-source corpus → two generated
  planes seam (`scripts/emit_hint_bank.py`, ADR-0014 amendment). *Stress:* G1
  new-abstraction — justified by making "full" measurable instead of vibes.

**Exploratory (different abstraction / product shape):**

- **D4 — Two-level taxonomy in the product.** Keep 6 mastery skills; add
  sub-skill standards to the wire model; scheduler picks weakest-standard-
  within-weakest-skill; dashboard drill-down. *Breaks:* wire kernel change
  (`frontend/lib/wire/` Zod), both DB seams, dashboard UX — full spec + ADR;
  calendar-heavy.
- **D5 — Band-adaptive serving.** Map learner mastery → target band; change
  `nextReviewedQuestion` from lowest-difficulty-first to band-matched pick
  (both fake + live seam, parity-tested). Small seam change, but only pays
  off once cells are populated → sequenced AFTER D1/D2 depth exists.
- **D6 — Passage-based item sets (real-ACT fidelity).** Real ACT English = 5
  passages × 15 underlined-portion items. Generate passage bundles sharing one
  `context_html`. *Breaks:* item schema (passage entity), quiz UI, generator +
  solver prompts — the biggest lift; its own spec/ADR.

## Hypotheses for the lead composite (D3 → D1 → D2, D5 deferred)

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Works because the cascade already enforces the full teaching payload + independent-solver key check | **validated** | `test_item_generation.py:90-156` (schema, fail-closed) + solver stage (ADR-0015 clause 5; `test_item_solver.j2` exists) |
| "Just run the generator at scale" is a flag flip | **rejected** | P3 — the 38-line `.j2` omits 6 required fields; prompt work is prerequisite |
| Test-01 rows satisfy the bank schema | **validated** | field census identical modulo `stem`/`stem_md` (48/48 `reviewed: true`, full payload, `generated_by` stamped) |
| Serving scales with data only | **validated** | P4 — seed + reviewed-gate + per-skill pick; no schema change for items |
| Provenance/leakage guards extend to new rows automatically | **validated** | `test_test_item_provenance_confinement` + `test_hint_provenance_confinement.py` + `test_hint_bank_leakage.py` scan the seed FILES, not fixed row lists (≥-count guards need bumping, by design) |

## Dependency map

- **D3 (syllabus-as-data)** — independent, no-LLM, cheap; defines "full" for
  everything else. Do first regardless of pick.
- **D1 (prompt repair + matrix generation)** — prompt fix is BLOCKING for any
  generate-mode scale-up; matrix fill consumes D3's cells.
- **D2 (promote Test-01)** — independent quick win; needs the exclusivity
  decision (human call, not derivable).
- **D5** — sequenced after depth exists. **D4/D6** — separate specs/ADRs;
  product-shape decisions, not content decisions.

ADR triggers if the lead proceeds: syllabus corpus + converter + coverage
ratchet (ADR, citing 0014/0015/0021 precedent); bank-expansion/exclusivity
policy (same ADR or `decisions.md`). No new pyproject deps. Never: live LLM
in CI (generation stays an offline governed job).

## Gate outcome (2026-07-07)

- **Direction:** composite D3→D1→D2 **plus D4 product-level taxonomy** in the
  same initiative. Reframed goal (human, at the gate): *topic-by-topic
  mastery* — extract ALL topics from the PDF; each topic gets its own
  quiz/learn unit; a systematic coaching plan builds mastery step by step,
  topic by topic; once all topics are covered/unlocked, composite-topic
  practices and tests unlock.
- **Exclusivity:** split the 48 Test-01 rows (~half promoted to practice,
  rest stays test-only).
- **Bank sizing:** driven by the topic inventory below (per-topic coverage,
  not a flat skills×bands matrix).
- **Next:** `sdd-spec` for the composite; D4 wire-model change is an ADR
  trigger (⚠️ new abstraction + wire kernel change).

## Topic extraction — the full PDF inventory

**Shape:** 5 score bands × 3 ACT reporting categories; standards recur across
bands with rising sophistication. Deduped: **32 distinct topics** (152 IXL
skill rows). Bands map to `difficulty` 1..5 (13–15→1 … 28–36→5). Existing
app-skill mapping in the last column.

### Production of Writing (→ s-org, s-rhet)

| # | Topic | Bands | App skill |
|---|---|---|---|
| 1 | Topic and organization (topic/concluding sentences, transitions, passage development, thesis, argument tracing) | 1,2,3,4,5 | s-org |
| 2 | Purpose (text purpose, connotation, audience, ethos/pathos/logos) | 2,3,4 | s-rhet |

### Knowledge of Language (→ s-rhet, s-style, s-gram)

| # | Topic | Bands | App skill |
|---|---|---|---|
| 3 | Common word errors | 1 | s-gram |
| 4 | Style and tone (formality, tone comparison, figures of speech) | 2,3,4 | s-rhet |
| 5 | Redundancy | 3 | s-style |
| 6 | Shades of meaning (related words, connotation) | 3 | s-style |
| 7 | Correlative conjunctions | 3,4 | s-gram |
| 8 | Word nuance (precision, connotation/denotation, revisions) | 4 | s-style |
| 9 | Word usage (foreign expressions, related words, redundancy, revisions) | 5 | s-style |

### Conventions of Standard English (→ s-punc, s-gram, s-sent)

| # | Topic | Bands | App skill |
|---|---|---|---|
| 10 | Joining simple clauses (coordinating/subordinating conjunctions, compound sentences) | 1 | s-sent |
| 11 | Inappropriate shifts in verb tense | 1,2 | s-gram |
| 12 | Irregular past tense and past participle | 1 | s-gram |
| 13 | Comparative and superlative adjectives/adverbs | 1,3 | s-gram |
| 14 | Commas (series, dates/places, addresses, introductory, compound/complex, coordinate adjectives, nonrestrictive, antithetical) | 1,2,3,4,5 | s-punc |
| 15 | Sentences, fragments and run-ons | 2,3,4 | s-sent |
| 16 | Adjectives vs. adverbs | 2 | s-gram |
| 17 | Subject-verb agreement (incl. compound subjects, indefinite pronouns) | 2,3,5 | s-gram |
| 18 | Pronoun-antecedent agreement | 2 | s-gram |
| 19 | Frequently confused words | 2,5 | s-gram |
| 20 | Adjective placement | 3 | s-sent |
| 21 | Misplaced and dangling modifiers | 3,4 | s-sent |
| 22 | Relative pronouns (who/whom/whose/which/that) | 3,5 | s-gram |
| 23 | Idiomatic expressions | 3 | s-gram |
| 24 | Apostrophes (plural vs possessive, compound/joint possession) | 3,4,5 | s-punc |
| 25 | Parallelism / parallel structure | 4,5 | s-sent |
| 26 | Verb and pronoun consistency (shifts in number/person/tense, active vs passive) | 4,5 | s-gram |
| 27 | Verb tense (progressive, perfect, past review) | 4 | s-gram |
| 28 | Pronouns (vague reference, subject/object, reflexive, who) | 4,5 | s-gram |
| 29 | Colons and semicolons (lists, joining clauses) | 4,5 | s-punc |
| 30 | Parenthetical elements (appositives, dashes, relative-clause combining) | 4 | s-punc |
| 31 | Restrictive and nonrestrictive elements | 5 | s-punc |
| 32 | Advanced sentence revision (double/illogical comparisons, modifier + parallel-structure review) | 5 | s-sent |

**Coverage today:** the 8-item bank touches ~7 of 32 topics (14 colon-lists,
27/11 tense, 23 idiom, 25 parallelism, 5/9 redundancy-concision, 4 tone,
1 transitions); the 48-item Test-01 corpus adds depth in 14, 17, 24, 29 but
is band-2/4 only. **25 of 32 topics have zero practice items.**
