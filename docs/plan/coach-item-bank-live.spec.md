# Spec — Live test-item generation + browser quiz served from the governed bank

**Status:** Approved — 2026-07-06 (spec gate passed; ADR-0021 drafted, plan + tasks derived)
**Owner:** Rajnish Khatri
**Related:**
- [ADR-0013 Test-Mode integrity + blueprint generation](../adr/0013-subject-coach-test-mode-blueprint-generation-integrity.md) (the *delivery tripwire* this re-opens)
- [ADR-0015 test-item bank + TestBlueprint read seam](../adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md) (the tables/ports this consumes)
- [ADR-0014 hint read seam](../adr/0014-subject-coach-hint-repo-read-seam.md) (structural precedent)
- `components/test_item_generation.py` · `scripts/generate_test_items.py` · `prompts/test_item_generator.j2`
- `frontend/lib/adapters/engine/_dev_seed.ts` (the seed precedent this mirrors)
- `frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts` (the bind point)
- **ADR to be written:** `docs/adr/0021-*` — bank-backed practice scheduler (the ⚠️ Ask-first trigger below)

---

## 1. Goal

Make the browser `/learn` practice quiz serve **real, LLM-generated, cascade-verified**
ACT-English items instead of the six hand-authored `_dev_seed.ts` fixtures. Two coupled
deliverables for a learner and for the coach maintainer:

- **Feature A (operate):** run the existing offline generator live to produce a small
  batch of `reviewed=true` items, and capture the run (passed rows + quarantine
  evidence) as a reproducible artifact.
- **Feature B (wire):** load those items into the browser engine DB as a checked-in seed
  and point the existing Dashboard quiz's scheduler at the governed `test_item` bank —
  **without** violating ADR-0015's leak-prevention table separation.

## 2. Context

Today two content systems exist and never meet at runtime (traced 2026-07-06):

- The **generator** (`scripts/generate_test_items.py` + `components/test_item_generation.py`)
  is fully built: a governed `build_graph` job renders `prompts/test_item_generator.j2`,
  runs one graph invocation, then adjudicates each candidate through a cascade
  (schema-parse → **independent-solver key gate** → duplicate). It has apparently never
  been run-and-committed: no generated bank exists on disk.
- The **browser `/learn` quiz** reads `ports.questionRepo.get()` seeded solely by
  `_dev_seed.ts` (6 items). The `test_item`/`test_blueprint` tables, the read-only
  `TestItemRepo`/`TestBlueprintRepo` ports, the Zod entities, and the Drizzle adapters
  all exist and `testItemRepo` is already in the `EnginePortBag` — but `listReviewed`
  has **no caller**; the seam is dark by deliberate ADR-0015 decision.

**The wrinkle (why an ADR is required).** The `FsrsScheduler.next()` asks a
`QuestionRepo`-shaped dependency for `nextReviewed(subject, skillId)`, and `review()`
asks it `get(questionId)` to resolve the attempt's skill. ADR-0015 clause 1 built
`test_item` as a *separate table specifically so the practice scheduler is structurally
unable to serve an exam item*. Pointing the quiz at the bank must therefore **not** merge
the tables and **not** let the practice `DrizzleQuestionRepo` see exam rows. This spec's
mechanism: a thin **`TestItemRepo`→`QuestionRepo`-shaped read adapter** (bank items are
"Question-shaped", ADR-0015 clause 1) injected into a **separately constructed** scheduler
for the bank-quiz path only. Same FSRS code, different bound repo; the leak stays
unrepresentable because the two repos never cross.

> **Decisions locked (user, 2026-07-06):** serving path = *swap the existing dashboard
> quiz to read the bank*; storage = *checked-in seed `.ts`*; generator run = *small real
> run, capture output*; skill coverage = *generate until all 6 skills covered* (scheduler
> stays full-6, bank must have ≥1 reviewed item per skill); dev-seed fate = *remove the 6
> `DEV_QUESTIONS` (+ their `DEV_HINTS`) once the bank is wired* (keep `DEV_SKILLS` +
> `DEV_SKILL_STATES` for the Dashboard mastery spread); Feature-A source = *Claude-authored
> `reviewed=false` seed promoted via the existing `--import-seed` cascade* (not generate
> mode — the user chose in-session authoring over a live generation run), with the
> *repo fast-tier model as the independent answer-key solver* (~1 short call/item — the
> only live-LLM step left; cross-model independence preserved). See the 2026-07-06
> `decisions.md` entry for the rejected solver alternatives.

## 3. Functional requirements (EARS)

### Feature A — live generation + capture

- **FR-A1 (failure path).** IF the generator's graph reply is not a parseable
  `{"items":[...]}` object THEN the cascade SHALL emit a `schema`-stage quarantine row
  and SHALL NOT write any `reviewed=true` item. *(already implemented in
  `run_test_item_cascade`; this run must exercise/observe it, not re-build it.)*
- **FR-A2 (failure path — the critical gate).** IF the independent solver's letter for a
  candidate disagrees with, or is undecidable against, the declared `answer_letter` THEN
  that candidate SHALL be quarantined at the `answer_key` stage and SHALL NOT be served.
- **FR-A3.** WHEN `scripts/generate_test_items.py --import-seed <authored-seed> --out <file>`
  completes THE SYSTEM SHALL write only cascade-promoted `reviewed=true` rows to `<file>`,
  each re-stamped `generated_by="<model>@<run_id>"` (the seed's self-asserted state is
  demoted on entry — `demote_seed_row`), and SHALL print the passed/quarantined counts.
  *(Pivot 2026-07-06: the authored seed replaces generate mode; the importer path already
  exists end-to-end — `promote_test_item_seed.py`.)*
- **FR-A6 (coverage).** THE captured bank SHALL contain ≥1 `reviewed=true` item for EACH
  of the six ACT-English skills (`s-punc`, `s-gram`, `s-sent`, `s-rhet`, `s-org`,
  `s-style`), so the full-6-skill scheduler never lands on an uncovered skill. WHERE a
  seed under-covers a skill, additional items SHALL be authored and re-promoted until
  coverage holds (merge by content-hash `id`). *(Pivot 2026-07-06: coverage is now an
  authoring property — Claude authors 2–3 items per skill directly, so the `--skill`
  generation flag is NOT needed this increment; it is deferred with the generate-mode
  prompt update to a future real-generation increment.)*
- **FR-A4.** THE SYSTEM SHALL record every quarantined candidate via `eval_capture` with
  `target="test_item_generator"` (auditability; no fabricated pass — AP-6).
- **FR-A5.** THE run SHALL make live LLM calls **on-demand only** (developer machine with
  `.env` keys) and SHALL NEVER execute in CI or on the learner hot path.

### Feature C — full-fidelity feedback (schema extension; amends ADR-0015 clause 1)

- **FR-C1.** THE `test_item` table (BOTH dialects) and the `TestItem` Zod entity SHALL gain
  the `Question`-parity teaching fields: `context_html`, `per_choice_rationale`,
  `why_correct_md`, `why_tempted_md`, `rule_md`, `item_type` (+ a presentation `stem` or a
  documented `stem_md`-as-stem view mapping), so a bank item carries the payload the
  Feedback screen renders. The dual-dialect parity test SHALL still pass.
- **FR-C2.** THE cascade (`_reviewed_row`/`_schema_violations` in
  `components/test_item_generation.py`) SHALL carry and structurally validate the new
  teaching fields; a candidate missing a required teaching field SHALL be quarantined at
  the `schema` stage. `_reviewed_row` MUST pass the fields through to the promoted row
  (else promotion strips them). *(The `test_item_generator.j2` prompt emission is
  DEFERRED — import mode renders no generator prompt; a future generate-mode run without
  the .j2 update fails closed at this schema stage, which is safe.)*
- **FR-C3 (independent-solver property preserved — failure path).** THE answer-key solver
  gate SHALL continue to see stem + choices ONLY; `per_choice_rationale`/`why_*`/`rule_md`
  SHALL be withheld from the solver view exactly as the declared key is (else the solver
  could read the answer out of the rationale, defeating FR-A2).
- **FR-C4.** THE `TestItemQuestionRepo` mapping SHALL be a lossless `TestItem→Question`
  pass-through (every `Question` field populated from a real bank column — no synthesized
  placeholder), so bank-served practice feedback is byte-equivalent in shape to authored
  feedback.

### Feature B — seed the bank + serve it in the quiz

- **FR-B1.** THE SYSTEM SHALL provide a checked-in seed module
  (`frontend/lib/adapters/engine/_test_item_bank.ts`) exporting the generated items as
  `TestItem` rows, loaded into the browser `InMemoryEngineDb` at composition time behind
  the same dev guard as `_dev_seed.ts` (never in tests, never in production).
- **FR-B2.** WHEN the `/learn` Dashboard quiz opens an item (`openQuizItem`) THE SYSTEM
  SHALL serve a `reviewed=true` item drawn from the `test_item` bank (via the bank-backed
  scheduler), not from the `_dev_seed.ts` `question` rows.
- **FR-B2a (dev-seed removal).** WHEN Feature B lands THE `_dev_seed.ts` module SHALL no
  longer export `DEV_QUESTIONS` or `DEV_HINTS`, SHALL retain `DEV_SKILLS` +
  `DEV_SKILL_STATES` (the Dashboard mastery spread + focus anchor), and SHALL no longer
  seed `question`/`hint` rows into the browser DB — the bank is the sole quiz-question
  source. *(Grounded blast radius — three consumers to update: (1)
  `composition_engine_browser.ts` seed wiring; (2) `drizzle_hint_repo.test.ts:104` which
  imports `seedDevCorpus` for its fixture — a G8 test-change; (3)
  `e2e/fixtures/preact_learn_corpus.ts`. Each weakened assertion SHALL be G8-justified.)*
- **FR-B3 (the leak-prevention invariant — failure path).** THE practice
  `DrizzleQuestionRepo.nextReviewed` SHALL remain structurally unable to return a
  `test_item` row: bank items are served only through the `TestItemRepo`-backed adapter,
  and no code path SHALL merge `test_item` rows into the `question` table.
- **FR-B4 (failure path).** IF the bank has zero `reviewed=true` items for a scheduled
  skill THEN the bank-backed scheduler SHALL raise the existing
  `no reviewed question for skill '<id>'` `EngineNotFoundError` (fail closed, surfaced —
  never an empty/blank item).
- **FR-B5.** THE bank-backed read adapter SHALL expose only reviewed rows: given a bank
  containing both `reviewed=true` and `reviewed=false` items, its `nextReviewed`/`get`
  SHALL never return a `reviewed=false` row (defense-in-depth mirror of the repo gate).
- **FR-B6.** THE grader/attempt/FSRS-review path SHALL be unchanged for bank items:
  `runQuizSubmit` grades against the served item's `answer_letter` and `review()` resolves
  the item's `skill_id` through the same bank-backed adapter (so `scheduler.review` works
  for an attempt whose question id is a bank id).
- **FR-B7 (provenance gate).** THE checked-in `_test_item_bank.ts` SHALL contain only rows
  whose `generated_by` matches the `<model>@<run_id>` cascade format (the ADR-0015
  write-confinement backstop) — a hand-authored or `dev-seed`/`authored` row in the
  `test_item` family SHALL fail the arch test. *(Grounded: the gate
  `tests/architecture/test_test_item_provenance_confinement.py` ALREADY exists but scans a
  hardcoded `_SEED_FILES = ("_dev_seed.ts", "_test01_english_corpus.ts")` — so Feature B
  MUST add `"_test_item_bank.ts"` to that tuple, else the new bank ships unguarded. This
  is a required task, not a "already passes" claim.)*

## 4. Data model / contracts

- **`TestItem` GAINS teaching fields (FR-C1).** Grounding found the mapping is *lossy*:
  `Question` carries `context_html`, `stem`, `per_choice_rationale`, `why_correct_md`,
  `why_tempted_md`, `rule_md`, `item_type` that `TestItem` and the `test_item` table
  (stem_md/choices/answer_letter/reviewed/generated_by) do **not**. The Feedback view reads
  `per_choice_rationale` + `rule_md` (`feedback_vm.ts:61,77`), so bank items would render
  empty feedback. Decision (user, 2026-07-06): **extend** the `test_item` table (both
  dialects) + `TestItem` entity + the generator to produce them → lossless mapping. This
  amends ADR-0015 clause 1 (the exam-only minimal shape) — covered by ADR-0021's schema
  extension. It is a schema change but **not** a trust-kernel type → no re-sign.
- **New (Feature B) — a thin adapter, not a port:** an in-repo class satisfying the
  existing `QuestionRepo` interface, backed by `TestItemRepo.listReviewed()` output,
  mapping `TestItem` → `Question` shape (both are underlined-span MC items with identical
  answer-bearing fields). No new `ports/` module (would violate F2/F-R3 one-interface
  discipline; this is an adapter over two existing ports).
- **New file (Feature A output → Feature B input):** `_test_item_bank.ts` — a generated,
  reviewed, committed seed. Not `question` rows; loaded via `db.seed*` at composition.
- **No trust-kernel type change** → no re-signing.

## 5. Invariants & security boundaries

- **Root invariant #3/#4 (framework-agnostic components/services):** untouched. The
  generator already imports no `langgraph` in `components/` (the driver in `scripts/`
  owns the graph). Feature B is entirely `frontend/`.
- **Frontend F2 / F-R3 (five sub-packages, one interface per port):** honored — Feature B
  adds an **adapter**, not a ninth port; `testItemRepo` already exists as the 11th engine
  port.
- **Frontend Rule C1/C2 (composition-root-only wiring):** the bank-backed scheduler is
  constructed only in `composition_engine_browser.ts` (+ the pg composition root for
  parity), injected by port; no consumer names it.
- **ADR-0015 clause 1 (leak unrepresentable by table separation):** preserved — see FR-B3.
  This is the security-critical boundary of the whole change.
- **ADR-0013 delivery tripwire:** this change **intentionally fires it** for the
  *practice* plane (moving the served practice corpus off `_dev_seed.ts` onto the governed
  bank). `/learn/test` (timed Test Mode) stays on the frozen `_test01_english_corpus.ts`
  fixture — Test Mode's tripwire is unrelated and stays unfired. The paired ADR records
  this scope split.
- **Live-LLM-in-CI ban (root 🚫):** Feature A run is on-demand only (FR-A5); the seed it
  produces is static data, so `make check` and CI never call an LLM.
- **⚠️ Ask-first → ADR trigger:** "a new abstraction on a governance seam" + re-opening a
  ratified ADR's tripwire ⇒ **ADR-0021 required** (bank-backed practice scheduler): the
  *why* behind serving practice items from the exam-item bank and the table-separation
  argument for why it's still leak-safe.

## 6. Edge cases

- **Empty bank / thin skill coverage:** resolved by decision — the bank MUST cover all six
  skills (FR-A6), so the full-6 scheduler never lands on an uncovered skill in the happy
  path. FR-B4 (fail-closed) remains the guard for a *regression* (a skill's items dropped),
  proven by a test that seeds a bank missing one skill and asserts `EngineNotFoundError`.
- **Hint ladder after `DEV_HINTS` removal:** `openQuizItem` loads `hintRepo.list()` and the
  iPad CoachPanel steps the reviewed rungs (FR-J3a). With `DEV_HINTS` gone the practice
  hint ladder is `[]` → the panel falls back to the generic nudge (documented fallback,
  not a crash). Bank items ship without hints in this increment; authored hints for bank
  items are out of scope (a later generator run through `scripts/generate_hints.py`).
- **Duplicate collision on re-generation:** re-running the generator yields
  content-hash ids; identical items collide to the same id (idempotent) — the seed must
  de-dupe on id when appending a second batch.
- **Solver undecidable (bare/ambiguous letter):** already handled — `extract_solver_letter`
  returns `None` → quarantine (FR-A2). Observe, don't rebuild.
- **Bank id vs question id in `review()`:** an attempt recorded against a bank item carries
  a `ti-gen-*` id; `scheduler.review` must resolve it through the bank adapter, not the
  practice `questionRepo` (FR-B6) — else "unknown question" on submit.
- **Mixed `reviewed` rows in the seed:** if a `reviewed=false` row leaks into the seed, the
  adapter gate (FR-B5) + the provenance arch test (FR-B7) must both catch it.

## 7. Non-functional requirements

- **Determinism:** Feature B is fully deterministic (static seed + FSRS fuzz OFF) → L1/L2
  exact assertions are valid. Feature A's *content* is probabilistic (LLM) — assert the
  cascade's *structural* guarantees (L1 on `run_test_item_cascade`), never exact item text
  (TAP-3).
- **Cost/latency:** Feature A ≈ 1 generation call + 1 solver call per candidate, one-off.
  Feature B adds zero runtime LLM cost.
- **Reversibility:** Feature B is revertible by flipping the composition wiring back to the
  `_dev_seed` scheduler; the seed file is additive. Feature A output is a file.

## 8. Test plan

Failure-path tests first. "In `make check`?" = deterministic gate; live = on-demand.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-A1 | `tests/components/test_test_item_generation.py` (EXISTS — verify it covers the non-items schema quarantine; extend if gap) | L1 | yes |
| FR-A2 | `tests/components/test_test_item_generation.py` (EXISTS — verify solver-disagreement + undecidable quarantine cases; extend if gap) | L1 | yes |
| FR-A3 | manual run log pasted into `.impl.md` (passed rows + counts) — evidence, not a unit test | L4 | live/on-demand |
| FR-A6 | `frontend/lib/adapters/engine/_test_item_bank.test.ts::covers_all_six_skills` (asserts ≥1 reviewed row per skill id) | L1 | yes (vitest) |
| FR-C1 | `frontend/lib/wire/test_item_entities.test.ts` (teaching fields required) + the dual-dialect `schema.spec` parity test stays green | L1 | yes (vitest) |
| FR-C2 | `tests/components/test_test_item_generation.py::test_missing_teaching_field_quarantines_schema` | L1 | yes |
| FR-C3 | `tests/scripts/test_generate_test_items_config.py::test_solver_view_withholds_rationale` (solver view has stem+choices only) | L1 | yes |
| FR-C4 | `frontend/.../test_item_question_repo.test.ts::maps_every_question_field_from_bank` (no empty/synthesized field) | L1 | yes (vitest) |
| FR-A4 | assert `eval_capture.record` called with `target="test_item_generator"` per quarantine (unit, mocked capture) | L2 | yes |
| FR-A5 | n/a (policy) — enforced by not adding a CI job; note in `.impl.md` | — | — |
| FR-B1 | `frontend/lib/adapters/engine/_test_item_bank.test.ts::seeds_reviewed_test_items` | L1 | yes (vitest) |
| FR-B2 | `frontend/components/quiz/use_quiz.test.ts::openQuizItem_serves_bank_item` (seeded bag) | L2 | yes (vitest) |
| FR-B2a | `frontend/lib/adapters/engine/_dev_seed.test.ts` updated: no `DEV_QUESTIONS`/`DEV_HINTS` export; `seedDevCorpus` seeds skills+states only (G8-justified) | L1 | yes (vitest) |
| FR-B3 | `frontend/.../drizzle_question_repo.test.ts::nextReviewed_never_returns_test_item_rows` | L1 | yes (vitest) |
| FR-B4 | `...::openQuizItem_empty_bank_fails_closed` (expects `EngineNotFoundError`) | L1 | yes (vitest) |
| FR-B5 | `frontend/.../test_item_question_adapter.test.ts::never_returns_unreviewed` | L1 | yes (vitest) |
| FR-B6 | `frontend/components/quiz/use_quiz.test.ts::runQuizSubmit_reviews_bank_item` (grade + FSRS review on a bank id) | L2 | yes (vitest) |
| FR-B7 | `tests/architecture/test_test_item_provenance_confinement.py` (EXISTS) — ADD `"_test_item_bank.ts"` to its `_SEED_FILES`, then it guards the new bank; re-run to confirm green with real rows | L1 | yes |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was *seen to fail first*.
- [ ] `make check` green (backend) **and** `pnpm --dir frontend test` + `tsc --noEmit` green.
- [ ] Invariants in §5 unbroken (`tests/architecture/` + `test_frontend_layering.ts` green).
- [ ] **ADR-0021 appended** (bank-backed practice scheduler) with index/log entries — the
      ⚠️ Ask-first trigger fired.
- [ ] Live generator run evidence (actual command output + passed/quarantine counts)
      pasted into `docs/plan/coach-item-bank-live.impl.md` — not summarized.
- [ ] `/learn` preview verified: Dashboard quiz serves a bank item (screenshot/snapshot),
      submit → feedback → summary loop still green end-to-end.
