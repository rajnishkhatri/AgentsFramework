# Plan — Bounded no-repeat quiz session (Sprint S3)

> The *how*, derived from [preact-quiz-target-count.spec.md](preact-quiz-target-count.spec.md)
> (the *what*) and [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md) (the *why*),
> under the 8 Architecture Invariants + the Frontend Ring rules (F/W/P/A/U families).

**Status:** Draft — 2026-07-08
**Owner:** Rajnish Khatri
**Related:** spec above; ADR-0023; ADR-0006 (ports), ADR-0005 (dual-dialect), ADR-0021 (bank serve path),
ADR-0022 (coverage ratchet + generation pipeline).

---

## 0. Architecture summary

Two capability groups on the frontend on-device engine substrate (all TypeScript; no Python
runtime, no cross-process seam):

- **(a) length** — a nullable `target_count` flows: `content_string` default (30/mode) →
  `SessionRepo.open` → `QuizSession` wire shape → both DB dialects.
- **(b) uniqueness** — a served-ids set flows the *other* way: the `use_quiz` play loop derives
  it from the session's `attempt` rows → `Scheduler.next(…, servedIds)` → `QuestionRepo.nextReviewed(…, excludeIds)`
  → `EngineDb.nextReviewedQuestion(…, excludeIds)` (drizzle `NOT IN` / fake filter).

The dependency arrows stay inward (wire ← ports ← adapters ← composition; components depend on
ports only). No new layer, no new port file (F-R3 respected — optional params on existing ports).

**S3-pre (blocking prerequisite):** grow the reviewed bank to ≥30/skill + raise the coverage
floor, reusing the ADR-0022 pipeline. Must land before the (a)+(b) implement tasks so the
flat-30 uniqueness guarantee is honestly satisfiable.

## 1. File-level touchpoints

### S3-pre — bank growth (offline, gated-on-data) — do FIRST
| File / artifact | Change |
|---|---|
| `scripts/generate_test_items.py` (run) | Generate candidates for the 4 thin skills: rhet +2, style +4, org +6, sent +7 (target ≥30 each). Creds-gated, offline. |
| `components/test_item_generation.py` (cascade) | No change — the existing schema → independent-solver key gate → duplicate cascade verifies the new candidates. |
| `scripts/promote_test_item_seed.py` (run) | Promote the cascade-passed candidates into `docs/plan/coach-item-bank-live.promoted.json`. |
| `docs/plan/coach-item-bank-live.promoted.json` | +19 promoted rows (data). |
| `scripts/emit_test_item_bank.py` (run) | Re-emit `frontend/lib/adapters/engine/_test_item_bank.ts` from the promoted JSON. |
| `frontend/lib/adapters/engine/_test_item_bank.ts` | GENERATED — now 190 items, ≥30/skill. Guarded by the existing provenance-confinement + emit-drift tests. |
| `docs/plan/act-english-coverage-floors.json` | Raise per-skill floor to 30 (rises-only; ADR-0022 ratchet). |
| `tests/architecture/test_syllabus_coverage_ratchet.py` | No change — it enforces the raised floor mechanically. |

### (a) `target_count` field + default
| File | Change | Rule |
|---|---|---|
| `frontend/lib/wire/engine_entities.ts` | `QuizSession` gains `target_count: z.number().int().positive().nullable()`. | W1 (pure shape) |
| `frontend/lib/ports/engine/session_repo.ts` | `open()` gains 5th param `targetCount?: number \| null`; JSDoc: omit→default, `null`→endless, value→that value. | P3 |
| `frontend/lib/adapters/engine/repos/drizzle_session_repo.ts` | `open()` resolves default via `ContentRepo` when `targetCount === undefined`; builds the row with `target_count`. | A4 |
| `frontend/lib/adapters/engine/db/engine_db.ts` | `insertSession`/`getSession`/`patchSessionClose` types already take `QuizSession`; `SessionClosePatch` unchanged (close never writes target). | — |
| `frontend/lib/adapters/engine/db/schema.pg.ts` | `quizSession`: `target_count: integer("target_count")` (nullable, no default). | ADR-0005 parity |
| `frontend/lib/adapters/engine/db/schema.sqlite.ts` | Same column, identical name/nullability/default intent. | ADR-0005 parity |
| `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` | `_toSession` maps `target_count` (`r.target_count == null ? null : Number(...)`); `insertSession` writes it. | A4 |
| `frontend/lib/adapters/engine/db/in_memory_engine_db.ts` | Fake carries `target_count` through `insertSession`/`getSession`; `patchSessionClose` leaves it. | test fake |
| `frontend/components/quiz/use_quiz.ts` | `OpenSessionArgs` gains `readonly targetCount?: number \| null`; `openQuizSession` threads it into `sessionRepo.open(...)`. | F-R1 (data bag only) |
| content_string seed (dev) — `frontend/lib/adapters/engine/_dev_seed.ts` or the content bundle | Add `session.target_count.adaptive/.drill/.review = "30"` rows so the default resolves in dev. | policy-as-data |

### (b) within-session uniqueness (served-ids)
| File | Change | Rule |
|---|---|---|
| `frontend/lib/ports/engine/question_repo.ts` | `nextReviewed(subject, skillId, excludeIds?: readonly string[])`; JSDoc: excludes served ids, reviewed gate unchanged, `null` when exhausted. | P3 |
| `frontend/lib/ports/engine/scheduler.ts` | `next(subject, learnerId, servedIds?: readonly string[])`; JSDoc: never returns an id in `servedIds`; falls through / returns not-found on exhaustion. | P3 |
| `frontend/lib/adapters/engine/db/engine_db.ts` | `nextReviewedQuestion(subject, skillId, excludeIds?: readonly string[])`. | — |
| `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` | `nextReviewedQuestion` adds a `NOT IN (excludeIds)` predicate (skip when empty). | A4 |
| `frontend/lib/adapters/engine/db/in_memory_engine_db.ts` | `nextReviewedQuestion` filters out `excludeIds` before returning the next reviewed row. | test fake |
| `frontend/lib/adapters/engine/repos/test_item_question_repo.ts` | `nextReviewed` forwards `excludeIds` to `EngineDb.nextReviewedQuestion` (double reviewed gate intact). | A4 / ADR-0021 |
| `frontend/lib/adapters/engine/repos/drizzle_question_repo.ts` | Same forward for the practice `question`-table repo (confirmed present). | A4 |
| `frontend/lib/ports/engine/attempt_repo.ts` | **NEW read** `servedQuestionIds(sessionId): Promise<readonly string[]>` (Stage-4 refinement — no session-scoped attempt read exists today; `misses()` returns incorrect-only). | P3 |
| `frontend/lib/adapters/engine/db/engine_db.ts` | **NEW** `listSessionQuestionIds(sessionId): Promise<string[]>` (a `question_id` projection scoped by `session_id`). | — |
| `frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts` + `in_memory_engine_db.ts` | Implement the session-scoped `question_id` read (drizzle `select question_id where session_id=` / fake filter). | A4 / fake |
| `frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts` | `next()`: after seeding + the most-due/weakest sort, iterate the sorted pool skipping skills whose only unserved reviewed items are gone; call `questions.nextReviewed(subject, chosen.skill_id, servedIds)`; on `null` for the chosen skill, try the next in the pool; return not-found when all exhausted. `review()` unchanged. | FR-9..11, determinism |
| `frontend/components/quiz/use_quiz.ts` | `openQuizItem` calls `attemptRepo.servedQuestionIds(session.id)` then passes the result to `scheduler.next(subject, learnerId, servedIds)`. (`openQuizItem` currently takes only `args` → thread the session id in.) | F-R1 (no decision, just forward) |

### Migration
| File | Change |
|---|---|
| `frontend/drizzle/…` (pg) + the sqlite migration dir | `drizzle-kit generate` for BOTH dialects → one `ALTER TABLE quiz_session ADD COLUMN target_count integer` (nullable, no default) per dialect. Applies clean, no backfill. |

## 2. Migration steps (ordered)

1. **S3-pre first.** Run generation → cascade → promote → emit for the +19 items; raise the
   coverage floor to 30; confirm the ratchet + provenance + emit-drift tests are green. (Gate:
   the flat-30 uniqueness guarantee is now satisfiable.)
2. **Wire + schema (a).** Add `target_count` to `engine_entities.ts` + both dialect schemas;
   run the parity test (red→green). `drizzle-kit generate` both dialects.
3. **Port + adapter (a).** `SessionRepo.open` 5th param; drizzle + fake DB seams; the
   `content_string` default resolution in the repo; the dev content rows.
4. **Component façade (a).** `OpenSessionArgs.targetCount` + `openQuizSession` thread-through.
5. **Ports (b).** `excludeIds` on `nextReviewed` + `EngineDb.nextReviewedQuestion`; `servedIds`
   on `Scheduler.next` (signatures + JSDoc first — everything compiles because they're optional).
6. **Adapters (b).** drizzle `NOT IN` + fake filter + `TestItemQuestionRepo`/`DrizzleQuestionRepo`
   forward; `FsrsScheduler.next` exclusion + fall-through + exhaustion.
7. **Component loop (b).** `use_quiz.openQuizItem` derives + passes served-ids.
8. **Gate.** `pnpm test` + `pnpm run test:arch` + `tsc --noEmit` green; migration applies clean.

Each step is red-first per the sdd-implement discipline (write the failing test, then implement).

## 3. Invariants walk (constitution check)

- **#1 dependencies flow downward / F-R1** — components (`use_quiz`) forward data to ports; the
  scheduling *decision* (skip id / next skill) lives in `FsrsScheduler` (adapter), the default
  *value* in `content_string` (data). No domain logic added to a component. ✓
- **#3/#4 framework-agnostic / F-R2** — no new SDK import; `ts-fsrs` stays confined to
  `fsrs_scheduler.ts`; drizzle stays in `db/`. ✓
- **F-R8 / A4** — served-ids are `readonly string[]`, `target_count` is `number|null`; no vendor
  type crosses an adapter boundary. ✓
- **FR-A2** — served-ids never written to `skill_state`; `review()` remains the sole writer. ✓
- **ADR-0005 parity** — `target_count` added to both dialects identically; parity test guards it. ✓
- **ADR-0022 ratchet** — floor raise is rises-only; lowering is mechanically blocked. ✓
- **P1/F-R3** — no new port file; optional params on existing ports (no second implementation to
  justify a new abstraction). ✓
- **Backward compatibility** — every new param optional; nullable column; omission = today's
  behaviour; existing tests compile untouched. ✓
- **⚠️ ADR** — ADR-0023 covers the two triggers; `decisions.md` has the clarify-fork entry. ✓

## 4. Risks & mitigations

- **Generation may not clear the cascade on the first run for thin skills.** Mitigation: S3-pre
  is a bounded, repeatable offline task; an honest partial run is recorded, not a floor
  relaxation (ADR-0022 posture). The FR-11 exhaustion path keeps the runtime correct regardless.
- **`NOT IN` with a large served set.** Bounded by `target_count` (~30 ids) — negligible; the
  fake mirrors the same semantics so the conformance suite covers both.
- **Served-ids derivation cost per `next()`.** One read of the session's attempts (already
  recorded). If it proves hot, cache within the play loop — but not on `skill_state`.
- **Scheduler determinism regression.** The exclusion is a pure pre-filter before the existing
  sort; the `localeCompare` final tie-break already removes store-order nondeterminism. A
  determinism test (FR-9/FR-13) guards it.
