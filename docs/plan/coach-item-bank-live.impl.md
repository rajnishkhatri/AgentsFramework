# Implementation evidence — coach-item-bank-live

**Date:** 2026-07-06 · **Spec:** [coach-item-bank-live.spec.md](coach-item-bank-live.spec.md) ·
**ADR:** [ADR-0021](../adr/0021-bank-backed-practice-scheduler.md) (Accepted)

Evidence log per the spec's Definition of Done: verbatim outputs, not summaries.

---

## Phase C — schema + cascade teaching-fields extension

Red→green per task (failing output seen first in-session for every new gate):

- **TC1** `TestItem` Zod entity + tests: red `8 failed | 9 passed` → green `17 passed`.
- **TC2** both dialect `test_item` tables + `toTestItem` mapping + fixtures
  (`drizzle_test_item_repo.test.ts`, `assemble_test_form.test.ts`,
  `convert_test01_seed*.test.ts`): red via `tsc` (4 break sites incl.
  `toTestItem` TS2740) → green: targeted vitest `39 passed`, `tsc` exit 0.
  - Note: the ADR-0010 "dual-dialect parity test" does **not exist yet** (it is
    that ADR's *future* condition); the operative parity gate today is `tsc`
    over both dialect modules — clean.
  - Bonus: `convert_test01_seed.ts` now carries the teaching payload through
    (reversing its pre-ADR-0021 "dead weight" drop), so the 48-row test01 seed
    stays fully importable — pinned by the roundtrip test.
- **TC4** cascade `_schema_violations` requires the teaching payload (incl.
  per-letter rationale coverage) and `_reviewed_row` carries it: red
  `4 failed, 22 passed` → green.
- **TC5** `_solver_view` withhold pin: green-on-arrival (whitelist) — kept as a
  regression pin; **extended after the live defect below**.

**Gate C:** `make check` → `5181 passed, 52 skipped, 72 deselected … in 122.04s`, exit 0.

## Phase A — authored seed → cascade promotion (live)

- **TA1** seed: [coach-item-bank-live.seed.json](coach-item-bank-live.seed.json)
  — 12 Claude-authored items (2 per skill × 6), `reviewed=false`,
  `generated_by="claude-session-authored"`. Offline pre-flight (schema stage +
  stem-duplicate check, zero LLM): `rows: 12 … PRE-FLIGHT: CLEAN`.
- **TA2** FR-A1/A2 cascade failure paths: already covered
  (`test_non_json_reply_quarantines`, `test_missing_items_key_quarantines`,
  `test_key_mismatch_quarantines`, `test_undecidable_solver_reply_quarantines`) — verified, no gap.

### TA3 — live promotion runs (solver = gpt-4o-mini fast tier, ~$0.0001/call)

**Run 1** (defective — DISCARDED):

```
DONE: 5 reviewed item(s) -> …/promoted_bank.json (7 quarantined -> eval_capture target=test_item_generator)
```

The pass/fail split diagnosed a real defect **introduced by the ADR-0021 field
split**: `_solver_view` (and `test_item_solver.j2`) showed the solver only
`stem_md` + choices — the passage now lives in `context_html`, so the solver was
answer-guessing blind. Every choices-only-solvable item passed (5) and every
passage-dependent item quarantined (7). Fixed red-first
(`test_solver_view_includes_the_passage`: red `1 failed` → green `31 passed`);
run 1's passes were discarded (earned under a defective gate).

**Run 2** (passage-aware solver — the bank source):

```
DONE: 8 reviewed item(s) -> …/promoted_bank_run2.json (4 quarantined -> eval_capture target=test_item_generator)
```

Coverage: `s-gram 2 · s-org 1 · s-punc 1 · s-rhet 2 · s-sent 1 · s-style 1` —
**6/6 skills (FR-A6 met)**.

### Quarantine adjudication (fixed-or-dropped, never key-adjusted)

Re-adjudication run printed the solver's letters:

```
QUARANTINE: answer_key | ["declared key 'B' != solver 'A'"] | Which choice makes the possessive correct?
QUARANTINE: answer_key | ["declared key 'B' != solver 'C'"] | Which choice repairs the sentence boundary?
QUARANTINE: answer_key | ["declared key 'B' != solver 'A'"] | Which transition best fits what the second sentenc
QUARANTINE: answer_key | ['solver reply undecidable (no clear letter)'] | Which choice trims the wordy opener?
```

| Item | Solver | Adjudication | Outcome |
|---|---|---|---|
| possessive (s-punc) | A | **Item ambiguous** (passage doesn't exclude multiple dogs) — author defect | DROPPED |
| fragment (s-sent) | C | **Declared key correct** (semicolon after an *although*-clause is wrong); fast-tier solver error — the named ADR-0015 accepted risk (no override path, by design) | stays quarantined |
| library transition (s-org) | A | Arguable both ways — weak item | DROPPED |
| wordy opener (s-style) | undecidable ×2 | Deterministic undecidable, correlated with an `input_validation … rejected` guardrail log line — harness-side, not content. Not chased this increment (coverage unaffected); noted as a possible guardrail false-positive on first-party generator traffic | DROPPED |

- **FR-A3/A4:** promoted rows all `reviewed=true`, `generated_by="gpt-4o-mini@<run_id>"`
  (re-stamped; the authoring marker never rides a reviewed row); quarantines
  recorded via `eval_capture target=test_item_generator`.
- **FR-A5:** no CI job added; runs were manual/local via `.env`.

## Reversibility (TV3)

Rebinding the practice `FsrsScheduler` back to the practice `questionRepo` in the
two composition roots and restoring `_dev_seed.ts`'s question/hint exports rolls
the whole serving change back; the bank seed + schema columns are additive.

## Phase B — wiring evidence

- **TB0:** no-op — `InMemoryEngineDb.seedTestItems`/`listReviewedTestItems`/`insertTestItem`
  already existed (the plan's Q1 "missing" finding was a grep artifact; verified by Read).
- **TB1:** `_test_item_bank.ts` generated from run 2's promoted JSON (8 rows,
  JSON-quoted keys deliberately — the provenance detector matches the quoted form).
  `_test_item_bank.test.ts`: parse+reviewed, cascade-provenance format, 6/6 skill
  coverage, seed round-trip — 4 tests green.
- **TB2:** `TestItemQuestionRepo` red (module missing) → green `11 passed` incl. the
  FR-B5 defense-in-depth case (a LYING TestItemRepo fake returning unreviewed rows —
  the adapter filters again), `save()` throws, lossless FR-C4 field-by-field map,
  deterministic pick.
- **TB3:** `drizzle_question_repo.test.ts` — practice repo blind to a reviewed,
  *easier* bank row for the same (subject, skill); `get(ti-gen-*)` null. 2 tests green.
- **TB4:** `questionSource: "practice" | "bank"` option on BOTH composition roots
  (browser + pg parity). Key wiring fact: `openQuizItem` resolves the scheduled id via
  `ports.questionRepo.get`, so the bag's `questionRepo` AND the scheduler bind to the
  bank adapter together. Dev singleton defaults to bank (+`seedTestItemBank`); the e2e
  `__PREACT_E2E_SEED__` override keeps practice wiring (specs' byte-stable question
  fixtures predate the bank — migrating them is deferred). use_quiz FR-B2/B6 red
  `2 failed | 19 passed` → green `25 passed`.
- **TB5:** FR-B4 fail-closed green (`no reviewed question` for an uncovered skill).
- **TB6 (G8):** `DEV_QUESTIONS` + `DEV_HINTS` removed (`_dev_seed.ts` seeds skills +
  states only). Consumers: `drizzle_hint_repo.test.ts` dev-ladder block removed with a
  `G8-OK` comment (repo behavior preserved by the surviving fixture-local tests);
  `tests/components/test_hint_seed_parity.py` DELETED — it pinned the frontend
  DEV_HINTS copy against `components/subject_coach_hints.py::AUTHORED_RUNGS` (ADR-0014
  two-plane drift risk), and the second plane no longer exists; the backend asset is
  the sole source, shape-covered by `test_subject_coach_hints.py`. **Commit message
  must carry `G8-OK: ADR-0021 removed the second hint plane (parity pin retired)`** for
  the merge-time `test_no_test_weakening` ratchet. `e2e/fixtures/preact_learn_corpus.ts`
  needed no change (references `_dev_seed` in comments only; defines its own corpus).
- **TB7:** `_test_item_bank.ts` added to the provenance gate's `_SEED_FILES` + a new
  guard-the-guard test — which CAUGHT a real hole red-first: the detector's 1200-char
  window predated the teaching payload (measured stem→provenance span 1466), so bank
  rows were invisible to the scan. Window widened to 4000 (first-match row-safe);
  `3 passed`.

## Phase V — gates + live preview

```
make check (final): 5181 passed, 52 skipped, 72 deselected, 3 warnings in 119.80s — exit 0
frontend: tsc --noEmit exit 0 · vitest full run: 116 files / 1091 tests passed
tests/architecture/test_test_item_provenance_confinement.py: 3 passed
```

Live `/learn` preview (dev server, bank wiring):
- Dashboard identical (skills + Maya mastery spread retained).
- *Start adaptive session* → served `ti-gen-eb8028a2…` (the promoted colon/list item),
  NOT a dev question — FR-B2 live.
- Submit "B" → Feedback rendered the FULL bank teaching payload: "Exactly right." +
  per-choice list + "Why B is correct: A colon after a complete statement introduces
  the list it promises…" + "The rule: Use a colon — never a semicolon — after a
  complete clause to introduce a list." — FR-C4 live.
- Loop advanced to a SECOND bank item (s-org marathon transition; `context_html`
  underline rendering correct) → Finish → **Session summary: SCORE 1/1**, mastery
  delta, recommended-next. Zero browser console errors.
