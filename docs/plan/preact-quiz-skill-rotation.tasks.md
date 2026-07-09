# Tasks — Round-robin skill rotation (Sprint S3.1)

> Decomposition of [preact-quiz-skill-rotation.spec.md](preact-quiz-skill-rotation.spec.md) (Approved)
> into atomic, red/green-testable tasks. *Why* = [ADR-0024](../adr/0024-quiz-skill-rotation-round-robin.md).
> Every task: write the test, **watch it fail**, implement, paste passing output (root `AGENTS.md`).

**Status:** Implemented (Stage 6 — all tasks red→green; evidence in spec §10) — 2026-07-08

## Dependency graph

```
T-r0 (served-skill read: EngineDb + both impls)
  └─ T-r1 (AttemptRepo.servedSkillIds port + adapter)
        └─ T-r2 (Scheduler.next servedSkillIds param + strict-rotation pool sort)  ← the fix
              └─ T-r3 (use_quiz.openQuizItem derives + passes servedSkillIds)
T-r4 (validation harness rotation check)  depends on T-r2 (engine) + T-r3 (play-loop mirror)
T-rg (full gate + DoD evidence)           depends on all
```

`T-r0 → T-r1 → T-r2 → T-r3` is a strict chain (each needs the seam below it). `T-r4`/`T-rg` last.

---

## T-r0 — session-scoped served-**skill** read (`EngineDb` + both implementations)

**Files:** `frontend/lib/adapters/engine/db/engine_db.ts` (interface),
`frontend/lib/adapters/engine/db/in_memory_engine_db.ts` (fake),
`frontend/lib/adapters/engine/db/drizzle_engine_db.ts` (live seam).
**FR:** FR-5.

- Add to the `EngineDb` interface: `listSessionSkillIds(sessionId: string): Promise<string[]>` —
  distinct skills served in the session, **newest-first**.
- **in-memory fake:** filter `attempts` by `session_id`, map each `question_id` → its
  `question.skill_id`, order by attempt `created_at` desc, de-dup keeping first (newest) occurrence,
  return skill ids. (Mirror the `listSessionQuestionIds` shape at `in_memory_engine_db.ts:227`.)
- **drizzle seam:** `attempt ⨝ question ON attempt.question_id = question.id`, `WHERE session_id = ?`,
  `SELECT question.skill_id`, `ORDER BY attempt.created_at DESC`; de-dup in JS keeping first. (Mirror
  `listSessionQuestionIds` at `drizzle_engine_db.ts:430`; the join mirrors how `listMisses` scopes.)

**Red:** a repo/db test (in `engine_repos.test.ts`) asserting newest-first + distinct + `[]` when no
attempts — fails (method absent). **Pass/fail:** the fake returns the seeded skills newest-first,
distinct; empty session → `[]`; `tsc` exit 0.

## T-r1 — `AttemptRepo.servedSkillIds` (port + adapter)

**Files:** `frontend/lib/ports/engine/attempt_repo.ts` (port + JSDoc contract),
`frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts` (forward to db).
**FR:** FR-5, FR-8. **Depends:** T-r0.

- Port: add `servedSkillIds(sessionId: string): Promise<readonly string[]>`; document (contract #6):
  distinct skills served this session **newest-first**, derived from `attempt` (append-only), never
  persisted on `skill_state` (FR-13 twin of `servedQuestionIds`), `[]` (not throw) when none.
- Adapter: `servedSkillIds` → `this.db.listSessionSkillIds(sessionId)`, wrapped in the existing
  `translate("servedSkillIds", err)` error path (mirror `servedQuestionIds` at
  `drizzle_attempt_repo.ts:60`).

**Red:** `engine_repos.test.ts` calls `attemptRepo.servedSkillIds(session.id)` over the fake and
asserts the recency order + distinctness — fails (method absent). **Pass/fail:** matches the db read;
`[]` for an attempt-less session; port-conformance still green.

## T-r2 — `Scheduler.next` gains `servedSkillIds` + **strict-rotation** pool sort *(the fix)*

**Files:** `frontend/lib/ports/engine/scheduler.ts` (signature + contract),
`frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts` (pool re-sort).
**FR:** FR-1, FR-2, FR-3, FR-4, FR-6, FR-7. **Depends:** T-r1.

- Port: `next(subject, learnerId, servedIds?, servedSkillIds?)` — 4th optional param
  `servedSkillIds?: readonly string[]` (newest-first). Document 2b: strict rotation — least-recently-
  served is the **primary** key; omitted/empty → today's weakest-first (FR-1); read-only (FR-7).
- Adapter `next()`: after building `pool` (currently sorted mastery → due → id at
  `fsrs_scheduler.ts:101-109`), when `servedSkillIds` is non-empty compute a **recency rank** per
  skill and sort by it FIRST:
  - rank = index of `skill_id` in `servedSkillIds` (newest-first) → a *higher* index = served longer
    ago = should come sooner; a skill **absent** from the list = never served = highest priority.
    Concretely: `rank(skill) = servedSkillIds.includes(skill) ? servedSkillIds.indexOf(skill) : +∞`,
    sort **descending by rank** (∞ first, then largest index … down to index 0 = most-recent last).
  - tie-break chain **unchanged** and applied only after rank: `mastery → due_at → skill_id`.
  - the existing fall-through loop (`for (const candidate of pool)` at `fsrs_scheduler.ts:125`) and the
    `EngineNotFoundError` exhaustion throw are **untouched** (FR-6): rotation only changes pool order.
- Update the block comment (the "seeded-due invariant" note) to also state the rotation ordering.

**Red (the reproduction):** a scheduler test seeding all 6 skills due (distinct masteries, like the dev
seed) + a `servedSkillIds` whose head is the current weakest → assert `next()` does **NOT** return that
weakest skill (FR-3). Run against current code → **fails** (weakest-first returns it). This is the
"always sentence-completion" bug captured as a failing test. Also red: FR-1 (omit → order unchanged),
FR-7 (spy: zero `upsertSkillState`).
**Pass/fail:** FR-1 order identical to pre-change when `servedSkillIds` omitted; FR-3 finished skill not
returned while another eligible skill exists; FR-4 never-served sorts ahead of served, oldest-served
ahead of newest; FR-6 no re-served question + exhaustion still throws; FR-7 spy count 0; `tsc` 0.

## T-r3 — play loop derives + passes `servedSkillIds`

**Files:** `frontend/components/quiz/use_quiz.ts` (`openQuizItem`).
**FR:** FR-3 (end-to-end), FR-8. **Depends:** T-r2.

- In `openQuizItem` (currently derives `servedIds` at `use_quiz.ts:126-130`), when `sessionId` is
  present ALSO derive `const servedSkillIds = await ports.attemptRepo.servedSkillIds(sessionId)` and
  pass it as the 4th arg to `ports.scheduler.next(subject, learnerId, servedIds, servedSkillIds)`.
  Omit both when `sessionId` is absent (unchanged single-pick path).

**Red:** `use_quiz.test.ts` — a session walk over a bank-backed fake asserting no skill is served twice
consecutively once >1 skill is eligible; fails before wiring (scheduler never receives recency).
**Pass/fail:** the play loop rotates; the `sessionId`-absent path is byte-for-byte unchanged; `tsc` 0.

## T-r4 — extend the S3 validation harness with a rotation check

**Files:** `frontend/scripts/validate_s3_bounded_session.ts` (+ mirror the step in the `.md` runbook).
**FR:** FR-3/FR-6 (observable). **Depends:** T-r2, T-r3.

- Add a `validateRotation()` block: open an adaptive session, walk N picks recording the served skill
  each time (resolve via `questionRepo.get(questionId).skill_id`), assert **no two consecutive picks
  share a skill** while ≥2 skills still have unserved items, and that ≥3 distinct skills appear across
  the walk. Mirror `openQuizItem`'s new `servedSkillIds` derivation (as the harness already mirrors the
  `servedIds` one).
- Add the matching manual step to `validate_s3_bounded_session.md` (§2B expand: "the fell-through skill
  differs each time — not always sentence-completion").

**Pass/fail:** harness prints the rotation check green; total count rises (was 19).

## T-rg — full gate + DoD evidence

**FR:** all. **Depends:** all.

- `make check` (root) + `(cd frontend && ./node_modules/.bin/vitest run lib/adapters/engine
  components/quiz)` for the touched suites + `pytest tests/architecture/ -q`.
- Frontend `tsc --noEmit` exit 0 (FR-8 additive-optional proof).
- Engine port-conformance (`tests/architecture/test_engine_port_conformance.test.ts` — registers
  `AttemptRepo` and `Scheduler`, ADR-0006/P7) green; the frontend-ring `test_port_conformance.test.ts`
  is a separate suite and is unaffected (known ts-morph under-load flake tolerated per
  [[frontend-vitest-tsmorph-timeout-artifact]] — confirm via isolated re-run if it trips).
- Paste actual output into the spec §Implementation-evidence block; flip spec + ADR-0024 Status to
  Implemented/Accepted; tick §9 DoD.

---

## Pass/fail summary (1:1 EARS map)

| Task | FRs | Verified by |
|------|-----|-------------|
| T-r0 | FR-5 | fake+db newest-first/distinct/empty; `tsc` 0 |
| T-r1 | FR-5, FR-8 | `servedSkillIds` recency+distinct; conformance green |
| T-r2 | FR-1,2,3,4,6,7 | reproduction red→green; FR-1 order unchanged; FR-7 spy 0; FR-6 no re-serve + throw |
| T-r3 | FR-3, FR-8 | play-loop walk no consecutive repeat; absent-path unchanged |
| T-r4 | FR-3, FR-6 | harness rotation check green |
| T-rg | all | `make check` + arch + `tsc` 0 + evidence pasted |
