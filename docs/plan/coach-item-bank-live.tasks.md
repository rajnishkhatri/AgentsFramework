# Tasks — Live test-item generation + browser quiz served from the governed bank

**Status:** Draft — 2026-07-06
**Spec:** [coach-item-bank-live.spec.md](coach-item-bank-live.spec.md) · **Plan:** [coach-item-bank-live.plan.md](coach-item-bank-live.plan.md) · **ADR:** [ADR-0021](../adr/0021-bank-backed-practice-scheduler.md)

Atomic, dependency-ordered. `[P]` = parallelizable with siblings in the same phase.
Every task: red-first where verifiable (write the test, watch it fail, then implement).
Pass/fail maps 1:1 to the EARS FR in the spec. Sequence: **C → A → B** (the generator must
emit teaching fields before the live run).

Legend — **V** verify pass/fail · gate: `make check` (backend) / `pnpm --dir frontend test` +
`tsc --noEmit` (frontend) / `pytest tests/architecture -q` (arch).

---

## Phase 0 — Ratify (human gate) — ✅ DONE 2026-07-06

- **T0. ✅** ADR-0021 ratified (Proposed→Accepted; frontmatter + body + `index.md` lead +
  `log.md` ratification entry), schema extension included. Feature-A pivot recorded in
  `decisions.md`: Claude-authored seed → `--import-seed` promotion, repo fast-tier solver.

---

## Phase C — Schema + generator extension (do first; red-first)  → FR-C1..C4

- **TC1.** Extend the `TestItem` Zod entity (`frontend/lib/wire/engine_entities.ts`) with
  `context_html`, `per_choice_rationale` (record), `why_correct_md`, `why_tempted_md`,
  `rule_md`, `item_type` (+ `stem` or documented `stem_md`-as-stem). Update
  `frontend/lib/wire/test_item_entities.test.ts` first (assert new fields required).
  **V (FR-C1):** `test_item_entities.test.ts` red → green; a row missing a teaching field fails parse.
- **TC2.** Add the same columns to `test_item` in `schema.sqlite.ts` **and** `schema.pg.ts`;
  update `drizzle_test_item_repo.ts` row↔`TestItem` mapping (read + insert).
  **V (FR-C1):** the dual-dialect `schema.spec` parity test stays green; `drizzle_test_item_repo.test.ts` round-trips the new fields.
- **TC3. DEFERRED** — `prompts/test_item_generator.j2` teaching-fields emission moves to a
  future real-generation increment (import mode renders no generator prompt; a generate-mode
  run without it fails closed at TC4's schema stage — safe). Recorded in `decisions.md`.
- **TC4.** `components/test_item_generation.py`: `_reviewed_row` carries the new fields;
  `_schema_violations` requires them (quarantine if missing). Write the quarantine test first.
  **V (FR-C2):** `tests/components/test_test_item_generation.py::test_missing_teaching_field_quarantines_schema` red → green.
- **TC5.** Confirm `_solver_view` still returns stem+choices ONLY (rationale withheld).
  Add a test if absent.
  **V (FR-C3):** `test_solver_view_withholds_rationale` — solver view has no `per_choice_rationale`/`why_*`/`rule_md` key.
- **Gate C:** `make check` + `pnpm --dir frontend test` + `tsc --noEmit` green.

---

## Phase A — Authored seed + cascade promotion (on-demand; produces B's seed)  → FR-A1..A6

> **Pivot 2026-07-06 (decisions.md):** Claude authors the content; the cascade earns
> `reviewed=true`; the repo fast-tier model is the independent key solver (~1 short
> call/item — the only live-LLM step). The `--skill` flag + generate-mode prompt update
> are deferred (TC3).

- **TA1.** AUTHOR the seed: 12–18 ACT-English items (2–3 per skill × 6 skills), each with
  full teaching fields (`context_html`, `stem_md`, 4 choices, `answer_letter`,
  `per_choice_rationale`, `why_correct_md`, `why_tempted_md`, `rule_md`, `item_type`,
  `difficulty`, `skill_id`), `reviewed=false`, `generated_by="claude-session-authored"`.
  Commit as `docs/plan/coach-item-bank-live.seed.json` (lineage evidence; reviewed=false
  rows are exempt from the provenance gate, which gates reviewed=TRUE only).
  **V (FR-A6 input):** ≥2 items per skill id; every row carries all TC4-required fields.
- **TA2.** VERIFY the cascade failure paths already exist; author any gap:
  FR-A1 (non-`items` reply → `schema` quarantine), FR-A2 (solver-disagree + undecidable →
  `answer_key` quarantine).
  **V (FR-A1/A2):** both cases present + green in `test_test_item_generation.py`.
- **TA3.** [live] Promote the authored seed through the real cascade (fast-tier solver
  blind-solves each item — key + rationale withheld per FR-C3):
  `.venv/bin/python scripts/generate_test_items.py --import-seed docs/plan/coach-item-bank-live.seed.json --out promoted_bank.json`.
  **V (FR-A3/A4):** prints passed/quarantine counts; quarantines recorded via
  `eval_capture target=test_item_generator`; output rows `reviewed=true`,
  `generated_by="<model>@<run_id>"` (re-stamped — never the authoring marker). A
  solver-disagreed item is FIXED-or-DROPPED, never key-adjusted to match the solver blindly
  (adjudicate: whose letter is right?).
- **TA4.** Write the run evidence (verbatim command output + per-skill pass/quarantine
  counts + any adjudication notes) into `docs/plan/coach-item-bank-live.impl.md`.
  **V (FR-A3/A6):** ≥1 promoted item per skill; evidence pasted (not summarized). FR-A5: no CI job added.

---

## Phase B — Wire the bank into the /learn quiz (red-first)  → FR-B1..B7

- **TB0.** Add `seedTestItems(rows)` to `InMemoryEngineDb` (+ the `EngineDb` interface),
  mirroring `seedQuestions`. (Q1: it does not exist today.)
  **V:** unit test seeds + `testItemRepo.listReviewed` returns them.
- **TB1.** Create `frontend/lib/adapters/engine/_test_item_bank.ts` from TA3 output:
  `TEST_ITEM_BANK: readonly TestItem[]` + `seedTestItemBank(db)`. Test first.
  **V (FR-B1):** `_test_item_bank.test.ts::seeds_reviewed_test_items` green.
  **V (FR-A6):** `::covers_all_six_skills` — ≥1 reviewed row per skill id.
- **TB2.** [P] `frontend/lib/adapters/engine/repos/test_item_question_repo.ts` —
  `TestItemQuestionRepo implements QuestionRepo` over an injected `TestItemRepo`; lossless
  `TestItem→Question` map; `nextReviewed(subject, skillId)` filters reviewed + skill;
  `get(id)` resolves a bank id; `save()` throws `EngineRepoError`. **Failure tests first.**
  **V (FR-B5):** `::never_returns_unreviewed` (feed mixed rows) red → green.
  **V (read-only):** `::save_throws`.
  **V (FR-C4):** `::maps_every_question_field_from_bank` — no empty/synthesized field.
  **V (FR-B6 support):** `::get_resolves_bank_id`.
- **TB3.** Add FR-B3 guard test: `drizzle_question_repo.test.ts::nextReviewed_never_returns_test_item_rows`
  (db holds both families; practice repo blind to bank).
  **V (FR-B3):** red (if it ever could leak) → green; documents the structural separation.
- **TB4.** Wire `composition_engine_browser.ts`: `db.seedTestItems(TEST_ITEM_BANK)`;
  `const bankRepo = new TestItemQuestionRepo(testItemRepo)`; bind the practice
  `FsrsScheduler` to `{ db, questions: bankRepo }`. Keep `seedDevCorpus` (skills/states).
  Mirror in `composition_engine.ts` (pg parity).
  **V (FR-B2):** `use_quiz.test.ts::openQuizItem_serves_bank_item` (seeded bag) green.
  **V (FR-B6):** `::runQuizSubmit_reviews_bank_item` — grade + FSRS review on a bank id.
- **TB5.** FR-B4 fail-closed guard: seed a bank missing one skill; assert
  `openQuizItem`/`scheduler.next` raises `EngineNotFoundError` (no blank item).
  **V (FR-B4):** test green.
- **TB6.** Remove `DEV_QUESTIONS` + `DEV_HINTS` from `_dev_seed.ts`; `seedDevCorpus` seeds
  skills+states only. Fix the 3 consumers: `composition_engine_browser.ts` (done in TB4),
  `drizzle_hint_repo.test.ts:104` (reseed hints locally), `e2e/fixtures/preact_learn_corpus.ts`.
  Each weakened test carries a G8 token.
  **V (FR-B2a):** frontend suite green; `test_no_test_weakening.py` passes (G8 justified).
- **TB7.** Add `"_test_item_bank.ts"` to
  `tests/architecture/test_test_item_provenance_confinement.py::_SEED_FILES`.
  **V (FR-B7):** arch test green with real `<model>@<run_id>` rows; detector still flags a self-stamped row.

---

## Phase V — Verify end-to-end (no new code)

- **TV1.** Gates: `make check` + `pnpm --dir frontend test` + `tsc --noEmit` +
  `pytest tests/architecture -q` all green. Paste output into `.impl.md`.
- **TV2.** `/learn` preview: Dashboard → Start adaptive session → a **bank** item →
  submit → **full feedback** (rationale + rule present) → Summary. Screenshot/snapshot as
  proof (FR-B2 + FR-C4 live).
- **TV3.** Confirm reversibility note in `.impl.md`: rebind practice scheduler to
  `questionRepo` + restore dev questions rolls back.

---

## Dependency graph

```
T0 ✅ ─► [C: TC1 ─► TC2 ; TC4 ; TC5]  (TC3 deferred) ─► Gate C
              │
              │   TA1 (authoring) may run [P] with Phase C — the field set is
              │   already fixed by the spec; only TA3 hard-needs C merged.
              ▼
   [A: TA1[P] ─► TA2 ─► TA3(live import) ─► TA4]
        │  (produces the promoted rows → _test_item_bank.ts input)
        ▼
   [B: TB0 ; TB2[P] ; TB3[P]] ─► TB1 ─► TB4 ─► TB5 ─► TB6 ─► TB7
        ▼
   [V: TV1 ─► TV2 ─► TV3]
```

## Definition-of-Done cross-check (spec §9)

- [ ] Every FR (A1–A6, B1–B7, C1–C4) has a task + a pass/fail test seen to fail first.
- [ ] ADR-0021 accepted; `make check` + frontend gates + arch suites green (output pasted).
- [ ] Live-run + preview evidence in `coach-item-bank-live.impl.md` (not summarized).
- [ ] G8 tokens on each weakened dev-seed test; provenance `_SEED_FILES` extended.
