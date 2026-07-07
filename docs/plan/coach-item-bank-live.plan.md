# Plan — Live test-item generation + browser quiz served from the governed bank

**Status:** Draft — 2026-07-06
**Owner:** Rajnish Khatri
**Spec:** [coach-item-bank-live.spec.md](coach-item-bank-live.spec.md) · **ADR:** [ADR-0021](../adr/0021-bank-backed-practice-scheduler.md)

Derived from the clarified spec + the constitution (root `AGENTS.md` 8 invariants +
`frontend/AGENTS.md` F/W/P/A/T/X/C/B rules). Two features; Feature A (operate) gates
Feature B (wire) because B's seed *is* A's output.

---

## 1. Architecture at a glance

```
FEATURE A (offline; the ONE live-LLM step = the fast-tier key solver, ~1 call/item)
  Claude authors docs/plan/coach-item-bank-live.seed.json          (12–18 items, 6 skills,
        │   reviewed=false, generated_by="claude-session-authored", full teaching fields)
        ▼
  scripts/generate_test_items.py --import-seed <seed> --out promoted_bank.json
        │  (EXISTING importer path: demote_seed_row → run_test_item_cascade;
        │   schema → independent fast-tier solver key gate (key+rationale withheld) → dup;
        │   reviewed=true EARNED, generated_by re-stamped "<model>@<run_id>")
        ▼
  promoted rows  ──►  frontend/lib/adapters/engine/_test_item_bank.ts
                      (checked-in TestItem[] seed, ≥1/skill)
                                                                    │
FEATURE B (browser, TypeScript, deterministic)                     │ loaded at composition (dev guard)
        ┌───────────────────────────────────────────────────────────┘
        ▼
  composition_engine_browser.ts
    db.seedTestItems(TEST_ITEM_BANK)                     ← new seed call
    const bankRepo = new TestItemQuestionRepo(testItemRepo)   ← NEW read-only QuestionRepo adapter
    scheduler: new FsrsScheduler({ db, questions: bankRepo })  ← same FSRS, bank-bound
    seedDevCorpus(db)  → now seeds SKILLS + STATES only (DEV_QUESTIONS/DEV_HINTS removed)
        │
        ▼
  /learn quiz  openQuizItem → scheduler.next() → bankRepo.nextReviewed() → a reviewed bank item
               runQuizSubmit → grader + scheduler.review() → bankRepo.get(bankId) resolves skill
```

**The invariant that must hold (ADR-0015 clause 1 / spec FR-B3):** the practice
`DrizzleQuestionRepo` and the `question` table are *never touched*. `TestItemQuestionRepo`
reads only `TestItemRepo` (the `test_item` table). The two repos never cross → an exam item
cannot reach practice scheduling. This is structural, not a filter.

## 2. File-level touchpoints

### Feature A (authored seed + importer promotion — pivot 2026-07-06, see decisions.md)
| File | Change |
|---|---|
| `docs/plan/coach-item-bank-live.seed.json` | NEW — Claude-authored `reviewed=false` seed (12–18 items, 2–3/skill, full teaching fields, `generated_by="claude-session-authored"`). Committed = authorship lineage. |
| `scripts/generate_test_items.py` | **NO driver change** — the `--import-seed` path exists end-to-end (`promote_test_item_seed.py`). The `--skill` flag is deferred with TC3. |
| `tests/components/test_test_item_generation.py` | VERIFY it already covers FR-A1 (non-items → schema quarantine) + FR-A2 (solver-disagree + undecidable → answer_key quarantine); ADD any missing case. |
| `docs/plan/coach-item-bank-live.impl.md` | NEW — paste the import-run command output (per-skill pass/quarantine counts + solver-disagreement adjudications) as FR-A3/A6 evidence. |

### Feature C (schema extension — DO BEFORE A's live run, so generated items carry the fields)
| File | Change |
|---|---|
| `frontend/lib/adapters/engine/db/schema.sqlite.ts` + `schema.pg.ts` | ADD columns to `test_item`: `context_html`, `per_choice_rationale` (json), `why_correct_md`, `why_tempted_md`, `rule_md`, `item_type` (+ presentation `stem` or document `stem_md`-as-stem). Keep dual-dialect parity (`schema.spec`). |
| `frontend/lib/wire/engine_entities.ts` | EXTEND `TestItem` Zod with the same fields (FR-C1); update `test_item_entities.test.ts`. |
| `prompts/test_item_generator.j2` | **DEFERRED** (pivot: import mode renders no generator prompt; a future generate-mode run without this update fails closed at the cascade schema stage — safe). |
| `components/test_item_generation.py` | `_reviewed_row` carries the new fields; `_schema_violations` validates them (FR-C2); `_solver_view` stays stem+choices-only (FR-C3 — rationale withheld like the key). |
| `frontend/lib/adapters/engine/repos/drizzle_test_item_repo.ts` | Map the new columns in the row↔`TestItem` conversion (both read + the seed insert path). |

### Feature B (frontend / TypeScript)
| File | Change |
|---|---|
| `frontend/lib/adapters/engine/_test_item_bank.ts` | NEW — `export const TEST_ITEM_BANK: readonly TestItem[]` (the curated generator output, now WITH teaching fields) + `seedTestItemBank(db)`. Mirror `_dev_seed.ts` structure/guards. |
| `frontend/lib/adapters/engine/_test_item_bank.test.ts` | NEW — FR-B1 (rows are reviewed `TestItem`) + FR-A6 (≥1 per skill id). |
| `frontend/lib/adapters/engine/repos/test_item_question_repo.ts` | NEW — `TestItemQuestionRepo implements QuestionRepo` over `TestItemRepo`; `nextReviewed`/`get` return reviewed rows mapped `TestItem→Question`; `save()` throws `EngineRepoError`. |
| `frontend/lib/adapters/engine/repos/test_item_question_repo.test.ts` | NEW — FR-B5 (never returns unreviewed), `save()` throws, `get(bankId)` resolves for `review()`, `nextReviewed` empty → `null`. |
| `frontend/lib/adapters/engine/_dev_seed.ts` | REMOVE `DEV_QUESTIONS` + `DEV_HINTS` + their seeding in `seedDevCorpus`; keep `DEV_SKILLS`/`DEV_SKILL_STATES`. |
| `frontend/lib/composition_engine_browser.ts` | Seed the bank (`db.seedTestItems(...)` or the module's `seedTestItemBank`); construct `TestItemQuestionRepo`; bind the practice `FsrsScheduler` to it; keep `seedDevCorpus` (skills/states). E2E-override branch unchanged. |
| `frontend/lib/composition_engine.ts` (pg parity root) | Mirror the bank-backed scheduler construction so pg + browser stay parallel (Rule F3). |
| `frontend/lib/adapters/engine/repos/drizzle_hint_repo.test.ts` | UPDATE (`:104` imports `seedDevCorpus` for a fixture that assumed `DEV_HINTS`) — reseed hints locally in the test instead. G8-justify. |
| `frontend/e2e/fixtures/preact_learn_corpus.ts` | UPDATE if it re-exports/depends on `DEV_QUESTIONS`/`DEV_HINTS`. |
| `frontend/components/quiz/use_quiz.test.ts` | ADD FR-B2 (`openQuizItem` serves a bank item) + FR-B6 (`runQuizSubmit` grades+reviews a bank id) against a seeded bag. |
| `frontend/lib/adapters/engine/repos/drizzle_question_repo.test.ts` | ADD FR-B3 (`nextReviewed` never returns a `test_item` row — feed a db with both, assert practice repo blind to bank). |

### Governance / arch
| File | Change |
|---|---|
| `tests/architecture/test_test_item_provenance_confinement.py` | ADD `"_test_item_bank.ts"` to `_SEED_FILES` (FR-B7) — else the new bank is unguarded. Re-run: green with real `<model>@<run_id>` rows. |
| `docs/adr/0021-*.md` + `index.md` + `log.md` | DONE (this session). Ratified at the tasks→implement gate. |

## 3. Migration / sequence

Feature **C precedes A** — the generator must emit teaching fields *before* the live run,
so the captured bank is already full-fidelity (no re-run after a schema change).

1. **C — schema + generator extension (red-first).** Extend `test_item` (both dialects) +
   `TestItem` entity + generator prompt/cascade to carry the teaching fields; solver view
   stays stem+choices-only. Dual-dialect parity green.
2. **A — author + promote (produces B's input).** Claude authors the seed (can start [P]
   with C — the field set is spec-fixed); after C merges, run `--import-seed` (fast-tier
   solver blind-checks each key, ~1 call/item). Curate promoted rows to
   `_test_item_bank.ts` (≥1/skill, full teaching fields). Evidence into `.impl.md`.
3. **B — read adapter + tests (red-first).** `TestItemQuestionRepo` lossless mapping;
   failure-path tests (unreviewed never returned, `save()` throws) before happy-path.
4. **B — db seam + wiring.** Add `seedTestItems` to the db adapter; compose the bank-backed
   scheduler at both roots; add the seed to the provenance `_SEED_FILES`.
5. **B — dev-seed removal.** Drop `DEV_QUESTIONS`/`DEV_HINTS`, fix the 3 consumers (G8).
6. **Gates** — `make check` + frontend `pnpm test`/`tsc` + arch suites; `/learn` preview
   (Dashboard quiz serves a bank item; submit → *full* feedback → summary green).

**Reversibility:** rebind the practice scheduler to `questionRepo` + restore dev questions
to roll back. The bank file and `--skill` flag are additive.

## 4. Constitution check (why the plan stays in-bounds)

- **Inv #3/#4 (framework-agnostic components/services):** Feature A touches only
  `scripts/` (owns the graph) + the already-agnostic cascade in `components/`. No new
  `langgraph`/`langchain` import in `components/`. ✅
- **Inv #6 (thin orchestration):** untouched — no graph-node change. ✅
- **Frontend F2 / F-R3:** no new port; `TestItemQuestionRepo` is an **adapter** over the
  existing `QuestionRepo` + `TestItemRepo`. ✅
- **Frontend A1/A2 (adapter SDK boundary, no cross-adapter import):** the new adapter
  imports the `TestItemRepo` **port** (injected), not the concrete `DrizzleTestItemRepo`. ✅
- **Frontend C1/C2 (composition-root-only wiring):** the bank scheduler is constructed only
  in the two composition roots; consumers see the `EnginePortBag`. ✅
- **⚠️ Ask-first → ADR:** covered by ADR-0021 (drafted). ✅
- **G8 (test-mass-rewrite):** the dev-seed removal weakens/rewrites 2–3 tests → each gets a
  `G8-OK:`/justification token (constitution + `test_no_test_weakening.py`). ✅
- **🚫 live-LLM-in-CI:** Feature A is on-demand; the committed seed is static data. ✅

## 5. Analyze-pass (Stage 4) findings — RESOLVED

- **Q1 — `db.seedTestItems`: DOES NOT EXIST.** `InMemoryEngineDb` has no `seedTestItems`
  (only `seedSkills/Questions/SkillStates/Hints`). → **Add `seedTestItems` to the db
  adapter** (task B0). Small, mirrors `seedQuestions`.
- **Q2 — `EngineRepoError`: RESOLVED.** `import { EngineRepoError } from
  "../../../ports/engine/errors"` (as in `drizzle_test_item_repo.ts:13`). The adapter's
  `save()` throws it.
- **Q3 — `e2e/fixtures/preact_learn_corpus.ts`:** references `_dev_seed` — confirm exact
  coupling at task time; if it re-exports `DEV_QUESTIONS`/`DEV_HINTS`, give it its own
  corpus. (Low risk; verify in implement.)
- **Q4 — `test_test_item_generation.py`:** EXISTS; verify FR-A1/A2 coverage at task time,
  extend if a case is missing (do not assume).
- **Q5 — MAPPING IS LOSSY (the big finding).** `Question` has 7 fields `TestItem`/the
  `test_item` table lack (`context_html`, `stem`, `per_choice_rationale`, `why_correct_md`,
  `why_tempted_md`, `rule_md`, `item_type`); `feedback_vm.ts:61,77` renders
  `per_choice_rationale` + `rule_md`, so bank items would show empty feedback. **Resolved by
  Feature C** (extend schema + generator; user decision 2026-07-06) → the mapping becomes
  lossless. This is why Feature C sequences **before** A's live run.
