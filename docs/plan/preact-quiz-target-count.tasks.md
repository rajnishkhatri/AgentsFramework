# Tasks — Bounded no-repeat quiz session (Sprint S3)

> Stage 3 decomposition of [preact-quiz-target-count.plan.md](preact-quiz-target-count.plan.md).
> Every task is atomic, file-level, red/green-testable, and maps 1:1 to EARS criteria in the
> [spec](preact-quiz-target-count.spec.md) §3. Dependency + parallel markers below.

**Status:** Implemented — 2026-07-08. Groups (a) T-a1/a2/a4 + (b) T-b0..b4 landed & green
(T-a3 N/A — no engine migration pipeline; S3-pre deferred — credentialed generation run). Evidence
in [spec §11](preact-quiz-target-count.spec.md).

---

## Checklist — is every EARS criterion measurable? ("unit tests for English")

| FR | Measurable? | How (the observable) |
|----|-------------|----------------------|
| FR-1 | ✅ | `QuizSession.safeParse({target_count: -1 / 2.5 / NaN})` → `success:false`. |
| FR-2 | ✅ | `open(..., null)` → row `target_count === null`. |
| FR-3 | ✅ | `getSession` on a row inserted without the field → `target_count === null`. |
| FR-4 | ✅ | `QuizSession.safeParse({target_count: 30})` → success; column present in both dialects. |
| FR-5 | ✅ | `open(...)` with no target → `target_count === 30` (from content_string). |
| FR-6 | ✅ | `open(..., 12)` → `target_count === 12` (not 30). |
| FR-7 | ✅ | `close(id, score)` → `target_count` unchanged from open value. |
| FR-8 | ✅ | schema parity test compiles both dialects; column matches. |
| FR-9 | ✅ | `next(..., [servedId])` never returns `servedId`; `nextReviewed(..., [id])` skips it. |
| FR-10 | ✅ | weakest skill exhausted → `next` returns an item from the next-weakest unserved skill. |
| FR-11 | ✅ | all skills exhausted → `next` throws not-found / repo returns `null` (no repeat). |
| FR-12 | ✅ | exclude set never surfaces a `reviewed=false` item. |
| FR-13 | ✅ | `next(..., servedIds)` performs zero `upsertSkillState` calls (spy the fake). |
| FR-14 | ✅ | no new progress-bar/done-state component in the diff (grep + no new render). |

All criteria measurable → no flag-back to the spec.

---

## Dependency graph

```
S3-pre (bank ≥30/skill + floor)  ──BLOCKS──►  T-a* and T-b*  (need flat-30 satisfiable)
                                              (S3-pre also independently landable/committable)

(a) length:            T-a1 ─┬─ T-a2 ─ T-a3 ─ T-a4                (wire → schema → repo/db → façade)
(b) uniqueness:        T-b1 ── T-b2 ── T-b3 ─┐                    (ports → adapters → scheduler)
                       T-b0 ─────────────────┴─ T-b4             (served-ids read ┘→ play loop)
gate:                  T-a*, T-b* ──► T-g (frontend-gate + DoD evidence)
```
`T-a1` and `T-b1` (the two signature/wire tasks) are parallelizable — different files. The
adapter/scheduler tasks within each group are sequential.

---

## S3-pre — bank growth (DEFERRED — blocked on a credentialed generation run)

> **DEFERRED 2026-07-08 (human decision).** T-pre1 needs the live-LLM generator, whose promoted
> rows carry an audited `generated_by = "<model>@<run_id>"` provenance stamp enforced by
> `test_test_item_provenance_confinement.py` (ADR-0015 clause 6). Hand-authoring items + stamping
> them would forge that audit record, so this waits for a real credentialed run. The (a)+(b) code
> below is implemented now; **FR-11** (end-early-on-exhaustion) keeps the runtime correct while the
> bank stays at 171 (4 skills < 30). The coverage floor is deliberately **left un-raised** — see
> T-pre2.

- **T-pre1 — grow the reviewed bank to ≥30/skill. [DEFERRED]** Run `scripts/generate_test_items.py`
  for rhet(+2)/style(+4)/org(+6)/sent(+7); cascade-verify; `promote_test_item_seed.py`;
  `emit_test_item_bank.py`. **Pass:** `_test_item_bank.ts` = 190 items, every skill ≥30; the
  provenance-confinement + emit-drift tests green. **Fail:** cascade rejects → record honest
  partial, iterate (never lower the target). Offline / creds-gated; not in CI.
- **T-pre2 — raise the coverage floor to 30. [DEFERRED — do NOT run until T-pre1 lands].** Editing
  `docs/plan/act-english-coverage-floors.json` per-skill → 30 while the bank is still at 171 would
  make the rises-only ratchet assert a flat-30 guarantee the bank does not meet (dishonest). Raise
  the floor only *after* T-pre1 promotes the +19 items. **Pass (when unblocked):**
  `tests/architecture/test_syllabus_coverage_ratchet.py` green at 30. Maps: spec §DoD S3-pre.

## (a) `target_count` field + default

- **T-a1 — wire + parity [FR-1, FR-4, FR-8].** Add `target_count: z.number().int().positive().nullable()`
  to `QuizSession` (`engine_entities.ts`); add the identical nullable `integer("target_count")`
  column to `schema.pg.ts` + `schema.sqlite.ts`. **Red:** `engine_entities.test.ts` rejects
  ≤0/non-int/NaN + parses 30; parity test. **Pass:** both red tests green; parity green.
  *Parallel with T-b1.*
- **T-a2 — repo default + DB seams [FR-2, FR-3, FR-5, FR-6, FR-7].** `SessionRepo.open` 5th param
  `targetCount?`; `DrizzleSessionRepo.open` resolves default 30 via `ContentRepo` when omitted,
  passes explicit value/`null` through; `drizzle_engine_db._toSession`/`insertSession` +
  `in_memory_engine_db` carry the field; `patchSessionClose` leaves it. Add the dev
  `content_string` rows. **Red:** `engine_repos.test.ts` — open(no target)→30, open(12)→12,
  open(null)→null, getSession(legacy)→null, close leaves it. **Pass:** all green. *Depends: T-a1.*
- **T-a3 — migration [FR-8]. [N/A — no engine migration pipeline exists].** GROUNDING
  CORRECTION (found at implement time): the engine schemas (`schema.pg.ts`/`schema.sqlite.ts`)
  have **no** drizzle-kit migration set — `drizzle.config.ts` manages only the `thread_store`
  tables (threads/thread_messages/coach_session_marker), `drizzle-kit` CLI is not installed, and
  there is no engine migration directory or `CREATE TABLE`/`migrate` call. The engine store today
  is `InMemoryEngineDb` (composition falls back to it with no `DATABASE_URL`); the Neon/on-device
  Drizzle engine store is schema-driven (tables built from the `pgTable`/`sqliteTable` defs) and
  not yet instantiated. The additive **nullable** column is therefore picked up automatically when
  that store lands — nothing to generate now. **When the engine gains a migration pipeline**, the
  one-line `ALTER TABLE quiz_session ADD COLUMN target_count integer` (nullable, no backfill) is
  the migration; both dialects already carry the column identically (T-a1). *Depends: T-a1.*
- **T-a4 — component façade [FR-5/6 wiring].** `OpenSessionArgs.targetCount` + `openQuizSession`
  thread-through. **Red:** `use_quiz.test.ts` — opening with a targetCount reaches
  `sessionRepo.open` with it; omitting → default resolves. **Pass:** green. *Depends: T-a2.*

## (b) within-session uniqueness

- **T-b0 — session-scoped served-ids read [FR-13, Stage-4 refinement].** Add
  `AttemptRepo.servedQuestionIds(sessionId)` + `EngineDb.listSessionQuestionIds(sessionId)`;
  implement in `drizzle_attempt_repo`/`drizzle_engine_db` (`select question_id where session_id=`)
  + `in_memory_engine_db` (filter). **Red:** `engine_repos.test.ts` — after N recorded attempts
  in a session, `servedQuestionIds(sessionId)` returns exactly those N question ids (and none
  from another session). **Pass:** green. *No dep; parallelizable. Blocks T-b4.*
- **T-b1 — port signatures [FR-9, FR-12 contract].** `excludeIds?` on `QuestionRepo.nextReviewed`
  + `EngineDb.nextReviewedQuestion`; `servedIds?` on `Scheduler.next`; JSDoc contracts. **Red:**
  a compile-level/conformance test asserting the new optional params exist and default to
  today's behaviour. **Pass:** everything compiles (optional params); conformance green.
  *Parallel with T-a1.*
- **T-b2 — DB + repo adapters [FR-9, FR-12].** drizzle `nextReviewedQuestion` `NOT IN` predicate
  (skip when empty); `in_memory` filter; `TestItemQuestionRepo` (+ `DrizzleQuestionRepo` if
  present) forward `excludeIds`. **Red:** `engine_repos.test.ts` / `test_item_question_repo.test.ts`
  — exclude skips served, never surfaces `reviewed=false`. **Pass:** green. *Depends: T-b1.*
- **T-b3 — scheduler exclusion + fall-through + exhaustion [FR-9, FR-10, FR-11, FR-13].**
  `FsrsScheduler.next(…, servedIds)`: filter the sorted pool, call `nextReviewed(…, servedIds)`,
  fall through to the next-weakest on `null`, return not-found when all exhausted; zero
  `skill_state` write. **Red:** `fsrs_scheduler.test.ts` — never returns an excluded id;
  exhausted-weakest→next skill; all-exhausted→not-found; no upsert on `next`. **Pass:** green.
  *Depends: T-b2.*
- **T-b4 — play-loop derives served-ids [FR-9 e2e wiring, FR-13].** `use_quiz.openQuizItem`
  calls `attemptRepo.servedQuestionIds(session.id)` and passes to `scheduler.next`. **Red:**
  `use_quiz.test.ts` — a multi-item walk never re-serves a question id; served set grows from
  attempts. **Pass:** green. *Depends: T-b0, T-b3, T-a4.*

## Gate

- **T-g — full gate + DoD evidence [FR-14 + all].** `pnpm test` + `pnpm run test:arch` +
  `tsc --noEmit` green; migration applies clean; grep confirms no S4 progress-bar / S5 done-state
  component added (FR-14). Paste actual command output into spec §10. **Pass:** all green, evidence
  pasted, spec Status → Implemented. *Depends: all T-a*, T-b*, T-pre*.*

---

## Notes

- **Backward-compat is the safety net:** every new param optional, column nullable → the whole
  change is additive; existing tests should stay green *without edits* (a G8 signal — if many
  existing tests need rewriting, stop and justify).
- **S3-pre is committable on its own** (bank + floor) ahead of the code, keeping the diff for the
  (a)+(b) work smaller and the generation provenance in its own commit.
- **No live LLM in CI** anywhere in S3 — generation is offline; the committed bank is replayed.
