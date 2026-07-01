---
type: architecture
title: 'Subject-Coach Engine — Data Schema & Component Protocols'
description: 'The WHAT: persistence schema + port/protocol definitions backing the PreACT English Coach prototype, designed English-concrete with subject seams (OCP). The WHY lives in ADR-0005 (engine home + substrate) and ADR-0006 (protocols).'
tags: [architecture, frontend-ring, schema, ports]
---

# Subject-Coach Engine — Data Schema & Component Protocols

**Status:** Draft — 2026-06-30 · **Owner:** Rajnish Khatri
**Audience:** anyone implementing the engine schema, the data ports, or the coach contract.

**Companion records (the WHY — read first to reconsider a decision):**
- [ADR-0005](../adr/0005-subject-coach-engine-home-and-substrate.md) — engine home (Frontend-Ring local-first) + substrate (Drizzle, Postgres↔SQLite).
- [ADR-0006](../adr/0006-subject-coach-component-protocols.md) — the seven component protocols (ports).

**Builds on (does not restate):**
- [FOUR_LAYER_ARCHITECTURE.md](FOUR_LAYER_ARCHITECTURE.md) — dependencies point inward; *"introduce protocols only when the second consumer arrives; document future abstractions now, build on demand."* This doc applies that rule.
- [FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) — one interface per `ports/` module (F-R3); SDKs confined to `adapters/`; composition root injects.
- UI contract: [`preact-english-coach-ui.spec.md`](../plan/preact-english-coach-ui.spec.md) §4 (view-models).
- Engine direction: [`QUIZ-APP-RESEARCH.md`](../../PreAct/QUIZ-APP-RESEARCH.md) Part 2 (the seed schema).
- Genericity stance: [`subject-coach-engine.brainstorm.md`](../plan/subject-coach-engine.brainstorm.md) — **English-concrete, seams only** (Option C3).

---

## 1. Governing thought

The prototype is one subject (ACT English) over a flow the engine owns. We model the
**data concretely for English** but place every subject-variant decision (taxonomy,
item-type, grading) **behind a port**, so the schema does not have to change to add Math —
only a new adapter + content rows do. This is the same discipline the four-layer doc
already mandates: *the seam exists now; the second adapter is built when Math arrives.*

**Two planes (from the brainstorm), mapped to storage:**
- **Objective plane** (UI text, skill taxonomy labels, screen copy) → `content_string`
  rows keyed by `(subject, key, locale)` behind a `ContentRepo` port. Subject is treated
  as a dimension *alongside* locale (the 2026 headless-CMS norm).
- **Subjective plane** (questions, rationales, coach replies) → `question` /
  `tutorial` rows whose bodies are LLM-generated offline and **verifier-gated** before a
  learner sees them (`reviewed` flag), plus the live coach over SSE.

---

## 2. Entity model (English-concrete, subject column = the only seam in the rows)

Synthesized from `QUIZ-APP-RESEARCH.md` Part 2 + the UI spec's view-models. Every table
carries a `subject` discriminator (default `'act-english'`) — that single column is what
keeps the schema open without making it abstract. ER overview:

```
                 ┌──────────────┐
                 │   subject    │  'act-english' (seed) · 'algebra-i' (future)
                 └──────┬───────┘
        ┌───────────────┼────────────────────────────┐
   ┌────▼────┐     ┌────▼─────┐                  ┌─────▼──────┐
   │  skill  │     │ content_ │                  │  tutorial  │
   │(taxonomy│     │ string   │  objective plane │ (per skill)│
   │ + share)│     │(i18n UI) │                  └────────────┘
   └────┬────┘     └──────────┘
        │ 1..N
   ┌────▼─────┐        ┌──────────────┐        ┌───────────────┐
   │ question │◄───────│   attempt    │───────►│ quiz_session  │
   │(item +   │  N..1  │(chosen,      │  N..1  │(mode, focus,  │
   │ choices, │        │ correct,     │        │ started/ended)│
   │ reviewed)│        │ ms, hint?)   │        └───────────────┘
   └────┬─────┘        └──────────────┘
        │ 1..1 per (skill, learner)
   ┌────▼──────────┐
   │  skill_state  │ mastery, fsrs_stability/difficulty, due_at  → drives adaptivity
   └───────────────┘
```

### 2.1 Table sketches (dialect-neutral; concrete DDL pinned by ADR-0005's substrate)

> Types shown abstractly (`id`, `text`, `int`, `real`, `bool`, `ts`, `json`) so this doc
> survives the Postgres-vs-SQLite choice in ADR-0005. `subject` defaults to `'act-english'`.

| Table | Columns (sketch) | Backs UI |
|---|---|---|
| **skill** | `id, subject, key('punctuation'…), name, share_of_test_pct, accent_var, description, order` | `BucketCardVM`, mastery grid, Skill detail header |
| **question** | `id, subject, skill_id→skill, difficulty(1–5), context_html(underlined-span markup), stem, choices(json:[{letter,label,isNoChange}]), answer_letter, per_choice_rationale(json), why_correct_md, why_tempted_md, rule_md, item_type('underlined-span-mc'), reviewed(bool), generated_by` | `QuizItemVM`, `FeedbackVM` |
| **quiz_session** | `id, subject, learner_id, mode('adaptive'\|'drill'\|'review'), skill_focus→skill?, started_at, ended_at, score_correct, score_total` | session bar, Summary stats |
| **attempt** | `id, session_id→quiz_session, question_id→question, chosen_letter, correct(bool), elapsed_ms, used_hint(bool), created_at` | Feedback, Summary, "review my misses" |
| **skill_state** | `subject, skill_id→skill, learner_id, mastery(0–1), last_seen(ts), fsrs_stability(real), fsrs_difficulty(real), due_at(ts)` — PK `(subject, skill_id, learner_id)` | Due badges, adaptivity, Progress bars |
| **tutorial** | `id, subject, skill_id→skill, body_md, examples(json), generated_from('rule'\|'misses'), reviewed(bool)` | Skill detail "rule in one line" |
| **content_string** | `subject, key('screen.dashboard.greeting'…), locale, value` — PK `(subject, key, locale)` | every UI label (objective plane) |
| **progress_point** *(or derived)* | `subject, learner_id, at(ts), projected_score, items_reviewed` | Progress trend line |

**Invariants (carried from the existing schema discipline):**
- **`reviewed` gate** — `question`/`tutorial` with `reviewed = false` MUST NOT reach a
  learner. Mirrors the research doc's "nothing reaches the learner until gated" and the
  repo's verifier-cascade habit.
- **IR-NEON-5 analogue** — engine tables live behind the same drizzle `tablesFilter`
  whitelist that already excludes LangGraph checkpoint tables; the engine never manages
  `checkpoints*`. (ADR-0005 confirms the migration substrate.)
- **`skill_state` is the adaptivity source of truth** — next item = highest-priority
  weak/most-due skill. FSRS writes only here.

### 2.2 View-model mapping (schema → UI, no leakage)

The UI never sees rows; a **translator** (Frontend-Ring convention) maps rows → the spec's
view-models. This keeps `FR-*` UI contracts stable even if the schema evolves:

| UI view-model (spec §4) | Derived from |
|---|---|
| `BucketCardVM` | `skill` ⋈ `skill_state` (mastery, due) |
| `QuizItemVM` | `question` (context_html, stem, choices) + session index/total |
| `FeedbackVM` | `question` (per_choice_rationale, why_*) + the learner's `attempt` |
| `ProgressVM` | `progress_point` (or aggregated `attempt`) + `skill_state` bars |
| `CoachMessage` | **not stored as engine rows** — rides the coach SSE stream (ADR-0006 §CoachAgentClient) |

---

## 3. Component protocols (ports) — the contract surface

Per F-R3: **one interface per `ports/` module**. Seven engine ports. SDK/vendor code
(Drizzle, FSRS lib, agent client) lives only in `adapters/`; the composition root injects.
Full signatures + rationale: **ADR-0006**. Summary of the seam:

| Port (`lib/ports/…`) | Responsibility | English adapter | Subject seam it keeps open |
|---|---|---|---|
| `SkillTaxonomy` | list skills for a subject (name, share, accent) | `act-english` rows | Math strands = different rows |
| `QuestionRepo` | fetch/store `question` (reviewed only) | Drizzle adapter | item-type-agnostic body |
| `AttemptRepo` | record attempts, read misses | Drizzle adapter | subject-neutral |
| `SessionRepo` | open/close `quiz_session`, score it | Drizzle adapter | subject-neutral |
| `Scheduler` (FSRS) | `next(subject, learner)` + `review(attempt)` → updates `skill_state` | ts-fsrs adapter | subject-agnostic algorithm |
| `Grader` | `grade(question, answer) → Verdict` (canonicalized) | exact-letter-match | symbolic/rubric grader later |
| `ContentRepo` | `text(subject, key, locale)` → UI string | in-repo bundle → CMS later | objective-plane authoring |
| `CoachAgentClient` | subscribe to coach SSE over the BFF | AG-UI/CopilotKit adapter | subject persona via prompt param |

> **Renderer registry, not a port** (React-OCP): the Quiz screen renders
> `registry[question.item_type]`, never `switch(subject)`. English registers
> `underlined-span-mc`; Math would register a symbolic renderer. The registry is the
> client-side twin of the `Grader` seam.

**Dependency direction (unchanged from the four-layer law):** ports define contracts;
adapters depend on ports; the engine (flow state machine, translators, registry) depends
on ports, never on adapters. Subject packs depend on engine interfaces; the engine
imports **zero** subject code.

---

## 4. What is deliberately NOT built yet (OCP discipline)

Documented-open, not implemented (per the four-layer "build on the second consumer" rule):
- No generic `ItemType` table — `item_type` is a column; the *renderer/grader* are the
  pluggable pieces. A table arrives only if a subject needs per-type metadata.
- No `Grader` strategy beyond exact-letter-match. The *interface* is generic
  (`grade(question, answer) → Verdict`); the symbolic/rubric strategy is built with Math.
- No external CMS — `ContentRepo` is satisfied by an in-repo typed bundle; the port makes
  the later swap an adapter change (ADR-0005 §substrate consequences).
- No CRDT/sync engine — local-first *posture* is designed in (ADR-0005), but the sync
  adapter is added when a second device/sync need is real.

Each line above maps to a §6 "don't-bake-it-in" item in the brainstorm. A PR that
hard-codes the left-hand assumption closes a door this design keeps open.

---

## 5. Open items handed to the ADRs

- **ADR-0005:** engine home (Frontend-Ring vs backend vs split) + substrate
  (Drizzle Postgres vs Postgres+SQLite) — with the local-first research trade-off.
- **ADR-0006:** the exact `typing`-level signatures of the seven ports, the `Verdict`
  shape, and the coach SSE contract (reuse of the existing AG-UI transport).
