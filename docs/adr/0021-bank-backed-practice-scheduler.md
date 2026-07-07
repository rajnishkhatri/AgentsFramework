---
type: decision-record
title: 'ADR-0021: Bank-backed practice scheduler — serve /learn quiz items from the governed test_item bank via a read-only QuestionRepo adapter'
status: accepted
created: 2026-07-06
updated: 2026-07-06
owner: Rajnish Khatri
related: 0013-subject-coach-test-mode-blueprint-generation-integrity.md, 0015-subject-coach-test-item-bank-blueprint-read-seam.md, 0014-subject-coach-hint-repo-read-seam.md, 0006-subject-coach-component-protocols.md, coach-item-bank-live.spec.md
tags: [decision-record]
---

# ADR-0021: Bank-backed practice scheduler

**Status:** Accepted — 2026-07-06 (ratified at the tasks→implement human gate, schema
extension included).
**Related:** [ADR-0015 test-item bank + read seam](0015-subject-coach-test-item-bank-blueprint-read-seam.md) (the tables/ports consumed) · [ADR-0013 Test-Mode integrity + delivery tripwire](0013-subject-coach-test-mode-blueprint-generation-integrity.md) (the tripwire this fires for the practice plane) · [ADR-0014 hint read seam](0014-subject-coach-hint-repo-read-seam.md) (the read-only-adapter precedent) · [ADR-0006 component protocols](0006-subject-coach-component-protocols.md) (the 11-port engine) · [spec](../plan/coach-item-bank-live.spec.md)
**Audience:** anyone touching the browser engine composition, the `/learn` quiz scheduler, or the `test_item`/`question` table separation.

---

## Context

Since ADR-0015 the browser engine has a governed `test_item` bank (separate table, two
read-only ports `TestItemRepo`/`TestBlueprintRepo`, Zod entities, Drizzle adapters, all
wired into `EnginePortBag`), but nothing serves from it: `TestItemRepo.listReviewed` has
no caller, and the `/learn` practice quiz reads six hand-authored `_dev_seed.ts` fixtures
through `QuestionRepo`. The [coach-item-bank-live spec](../plan/coach-item-bank-live.spec.md)
now makes the bank the practice quiz's real source (the user chose "swap the existing
Dashboard quiz to read the bank").

Two forces collide. **First**, ADR-0015 clause 1 built `test_item` as a *separate table
from `question` specifically so the practice scheduler is structurally unable to serve an
exam item* — "separation by table, not by a filter every query must remember." **Second**,
the `FsrsScheduler` (the sole `skill_state` writer, ADR-0006 #5) is bound to a
`QuestionRepo`-shaped dependency in exactly two places: `next()` calls
`questions.nextReviewed(subject, skillId)` to resolve the chosen skill → a served item
([`fsrs_scheduler.ts:108`](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts)),
and `review()` calls `questions.get(attempt.question_id)` to resolve the attempt's skill
for the FSRS update. Naively pointing the quiz at the bank would either merge the two
tables (destroying the leak-prevention invariant) or fork the FSRS scheduler into a second
implementation (a determinism/parity liability on the *sole* `skill_state` writer).

A decision is required because serving practice items from the exam-item bank re-opens
ADR-0013's **delivery tripwire** for the practice plane, and because introducing a new
abstraction on this governance-sensitive seam is an `⚠️ Ask first` trigger under the root
`AGENTS.md` ratchet.

---

## Decision

Serve `/learn` practice items from the governed `test_item` bank by introducing a thin
**read-only `QuestionRepo` adapter over `TestItemRepo`** — `TestItemQuestionRepo` — that
maps each `reviewed=true` `TestItem` to the structurally-identical `Question` shape, and
injecting it (at the browser + pg composition roots only) into a **separately constructed**
`FsrsScheduler` for the practice path. The FSRS scheduler code is reused byte-for-byte; the
only change is which `QuestionRepo` it is bound to. The practice `DrizzleQuestionRepo` and
the `question` table are left untouched, so the two repos never cross and the ADR-0015
table separation still makes an exam-item leak into practice **unrepresentable**. The
adapter is read-only: `nextReviewed`/`get` return reviewed bank rows; `save()` throws
(serving code never writes the bank — the ADR-0014 posture). The six `_dev_seed.ts`
`DEV_QUESTIONS`/`DEV_HINTS` are removed (the bank is the sole quiz-question source);
`DEV_SKILLS`/`DEV_SKILL_STATES` stay for the Dashboard mastery spread.

This is scoped to the **practice plane only**: `/learn/test` (timed Test Mode) keeps
serving the frozen `_test01_english_corpus.ts` fixture, so ADR-0013's Test-Mode delivery
tripwire stays unfired; the practice-plane tripwire is fired knowingly here.

**Schema extension (amends ADR-0015 clause 1).** The practice Feedback screen renders
per-choice rationale (`feedback_vm.ts` → `question.per_choice_rationale`, FR-E1/E3) and the
rule (`question.rule_md`), which the minimal `test_item` table (stem/choices/answer/
reviewed/generated_by) does not carry. To serve *full-fidelity* practice feedback, the
`test_item` table (both dialects) and the `TestItem` Zod entity gain the `Question`-parity
teaching fields — `context_html`, `stem_md`↔`stem` presentation, `per_choice_rationale`,
`why_correct_md`, `why_tempted_md`, `rule_md`, `item_type` — and the generator
(`test_item_generator.j2` + `components/test_item_generation.py`) emits and validates them.
This makes the `TestItemQuestionRepo` mapping lossless (straight pass-through). ADR-0015
clause 1 deliberately stored only answer-bearing fields (exam items show no rationale); this
ADR extends that shape because the *practice* consumer needs the teaching payload. The
leak-prevention property (separate table, separate repo) is unchanged — only columns are
added; no discriminator, no FK to `question`.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **`TestItemQuestionRepo` read adapter → separate scheduler (chosen)** | Reuses the sole FSRS writer unchanged; leak stays unrepresentable (repos never cross); read-only `save()` throw enforces the no-write posture. The abstraction is an *adapter over two existing ports*, not a new port. ✅ |
| **Merge `test_item` rows into the `question` table (discriminator column)** | Directly reverses ADR-0015 clause 1: every practice query must filter forever; one missed filter serves an exam item into scheduling. Reintroduces the exact leak the table split made unrepresentable. ❌ |
| **Fork `FsrsScheduler` into a `BankScheduler`** | Two implementations of the *sole `skill_state` writer* to hold in parity — the determinism/mastery-projection logic (FSRS card round-trip, retrievability) duplicated, the drift risk ADR-0014 already flagged for two planes, now on the writer itself. ❌ |
| **New `ports/engine/bank_question_source.ts` port** | Violates F2/F-R3 (the engine is capped at its ports; a new interface needs two competing implementations). `TestItemRepo` already exists as port 11; this is an adapter that *bridges* it to `QuestionRepo`, earning no new port. ❌ |
| **Add a new Practice-from-bank quiz mode, leave the dashboard quiz on dev-seed** | The user explicitly chose to swap the existing quiz. A parallel mode leaves the six dead dev fixtures live and splits the practice UX. ❌ (revisit only if a separate exam-practice surface is later wanted) |
| **Bank preferred, dev-seed question fallback for uncovered skills** | The practice quiz would then read BOTH `question` and `test_item` — blurring the ADR-0015 separation the whole design defends. Superseded by generating full 6-skill coverage instead (spec FR-A6). ❌ |
| **Write surface on the adapter (`save` implemented)** | Serving code must never flip `reviewed` or write the bank; writes belong to the generator/importer at the composition boundary (ADR-0014 precedent). The adapter's `save()` throws. ❌ |

---

## Rationale

The chosen option is the smallest change that satisfies "swap the quiz to the bank" while
keeping every ADR-0015 guarantee. The leak-prevention invariant is a *structural* property
(two tables, two repos that never meet) rather than a filter discipline — the adapter
preserves it because the practice `DrizzleQuestionRepo` is never touched and the bank is
reached only through the read-only `TestItemRepo`. Reuse of the unchanged `FsrsScheduler`
keeps the sole `skill_state` writer single-sourced (no parity liability on the determinism
path). `TestItem` and `Question` are the same underlined-span-MC shape with identical
answer-bearing fields (ADR-0015 clause 1 "Question-shaped fields"), so the mapping is a
field rename, not a semantic translation. And confining the swap to the practice plane
keeps ADR-0013's Test-Mode Option-A posture and its code-enforced tripwire untouched.

---

## Consequences

**Commits us to:**
- **A `test_item` schema extension** (both dialects `schema.sqlite.ts`/`schema.pg.ts` + the
  `TestItem` Zod entity): add `context_html`, `per_choice_rationale`, `why_correct_md`,
  `why_tempted_md`, `rule_md`, `item_type`, and a presentation `stem` (or reuse `stem_md`
  in the view). Migration in both dialects; the dual-dialect parity test must still pass.
- **Generator + cascade emit the teaching fields:** `prompts/test_item_generator.j2` renders
  them; `components/test_item_generation.py::_reviewed_row`/`_schema_violations` carry and
  structurally validate them (the answer-key solver gate still sees stem+choices only —
  rationale is withheld like the declared key, so the independent-solver property holds).
- `frontend/lib/adapters/engine/repos/test_item_question_repo.ts` — the read-only
  `QuestionRepo` adapter over `TestItemRepo`, now a **lossless** `TestItem→Question`
  pass-through (+ conformance/behavior test: reviewed gate holds, `save()` throws, `get`
  resolves a bank id for `review()`).
- A **second `FsrsScheduler` construction** in `composition_engine_browser.ts` (and the pg
  `composition_engine.ts` for parity) bound to `TestItemQuestionRepo`; the practice quiz
  uses it. Composition-root-only (Rule C1/C2).
- A checked-in `frontend/lib/adapters/engine/_test_item_bank.ts` seed (generated, reviewed,
  ≥1 item per skill), loaded behind the `_dev_seed` dev guard; and its addition to the
  **existing** `tests/architecture/test_test_item_provenance_confinement.py::_SEED_FILES`
  tuple (else the new bank ships unguarded by the write-confinement backstop).
- Removal of `DEV_QUESTIONS`/`DEV_HINTS` from `_dev_seed.ts`, updating the three grounded
  consumers (`composition_engine_browser.ts`, `drizzle_hint_repo.test.ts`,
  `e2e/fixtures/preact_learn_corpus.ts`) — a G8 test-change (justify each weakened
  assertion).
- **ADR-0013 delivery tripwire fired for the practice plane** — this ADR is the recorded
  evaluation of that tripwire for practice; Test Mode's tripwire remains a separate, unfired
  event.

**Accepted risks / mitigations:**
- *Thin/skewed bank coverage* → the full-6 scheduler could land on an uncovered skill and
  fail closed. Mitigated by generating ≥1 reviewed item per skill (spec FR-A6); FR-B4 keeps
  fail-closed as the guard for a coverage regression.
- *Bank items ship without hint ladders this increment* (DEV_HINTS removed; no authored
  hints for bank items yet) → the iPad CoachPanel falls back to its generic nudge (a
  documented fallback, not a crash). Authored hints for bank items are deferred to a later
  `scripts/generate_hints.py` run.
- *Two `FsrsScheduler` instances share one `skill_state` table* → both write the same
  learner rows; acceptable because only the practice path is active per session and the
  writer logic is identical (single-sourced). If Test Mode ever also writes `skill_state`,
  revisit isolation.
- *Adapter is a new indirection on the hot path* → negligible (an in-memory list filter);
  the read-only `save()` throw is the only behavioral surprise, covered by a test.

## Supersedes / related

Consumes [ADR-0015](0015-subject-coach-test-item-bank-blueprint-read-seam.md); fires the
practice-plane half of [ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md)'s
delivery tripwire; follows the read-only-adapter posture of
[ADR-0014](0014-subject-coach-hint-repo-read-seam.md). Realized by the
[coach-item-bank-live spec](../plan/coach-item-bank-live.spec.md) and its plan/tasks.
Supersedes no prior ADR.
