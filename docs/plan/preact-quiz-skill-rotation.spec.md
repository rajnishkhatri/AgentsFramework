# Spec — Round-robin skill rotation for the bounded quiz session (Sprint S3.1)

> Acceptance criteria use **EARS**. Failure paths are written first (§3). This spec is
> the *what*; the load-bearing *why* is [ADR-0024](../adr/0024-quiz-skill-rotation-round-robin.md)
> (two ⚠️ Ask-first triggers fire — new cross-port method + new scheduling-order policy; see §5).

**Status:** Implemented (Stage 6, all tasks red→green; §10 evidence) — 2026-07-08
**Owner:** Rajnish Khatri
**Related:** [preact-quiz-target-count.spec.md](preact-quiz-target-count.spec.md) (S3 — the bounded
no-repeat session this refines), [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md) (the
served-ids seam this widens), [ADR-0021](../adr/0021-bank-backed-practice-scheduler.md) (the serve
path), [ADR-0006](../adr/0006-subject-coach-component-protocols.md) (Scheduler #5 / AttemptRepo #3),
[preact-english-coach-engine.spec.md](preact-english-coach-engine.spec.md) (FR-A1/A2/A7 the scheduler
contract).

---

## 1. Goal

Within one bounded quiz session, when the learner finishes (exhausts) a skill, the **next**
item should come from a **different** skill rather than always the same one — the session should
rotate across skills instead of parking on sentence-completion. For a learner practising on
`/learn/quiz`, variety across skills is the felt behaviour; strict weakest-first is not.

## 2. Context

**Observed defect (2026-07-08, user report):** "after completing/finishing & review any of the
skill, the next skill is always sentence completion." Root cause, grounded in the code:

- `FsrsScheduler.next()` is a **read-only** serve walk — S3/FR-13 forbids a `skill_state` write
  during serving ([fsrs_scheduler.ts:111-138](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts)),
  so **mastery is frozen** at its value for the whole session. `review()` is the sole writer and
  its `due_at` push does not re-order *within* a serving walk.
- The pool is sorted **weakest-mastery first**, then `due_at`, then `skill_id`
  ([fsrs_scheduler.ts:101-109](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts)). With
  frozen mastery the order is a **fixed sequence**. The dev seed
  ([_dev_seed.ts:141-146](../../frontend/lib/adapters/engine/_dev_seed.ts)) makes `s-sent` (mastery
  0.61) the perpetual next-weakest once the three *due* skills (`s-punc` 0.28, `s-org` 0.40,
  `s-gram` 0.55) drain — so every FR-10 fall-through lands on `s-sent`.

The S3 no-repeat seam already threads a **caller-owned, session-scoped** served set into `next()`
(`servedIds`, derived from the append-only `attempt` rows —
[use_quiz.ts:122-141](../../frontend/components/quiz/use_quiz.ts)). This spec widens that same seam
to carry the served **skills** (in recency order) and uses them to **re-order the pool** so the
least-recently-served eligible skill is picked first — a rotation policy, layered on top of the
existing weakest-first ordering as the tie-break.

**Premise audit** (the report is itself a hypothesis):

| Premise | Status | Evidence |
|---|---|---|
| "The next skill is *always* sentence-completion" | **VERIFIED (as a consequence, not a hardcode)** | Not hardcoded anywhere; it is the emergent result of frozen-mastery + weakest-first + the seed masteries above. `s-sent` is 4th-weakest and the first of the not-due block. |
| The served seam already carries skill identity | **REFUTED** | `AttemptRepo.servedQuestionIds` / `EngineDb.listSessionQuestionIds` project **only `question_id`** ([attempt_repo.ts:41](../../frontend/lib/ports/engine/attempt_repo.ts), [in_memory_engine_db.ts:227](../../frontend/lib/adapters/engine/db/in_memory_engine_db.ts)) — no skill, no order. True least-recently-served rotation needs a **new** read that joins `attempt → question → skill_id` in recency order. |
| Rotation can reuse `skill_state` to track recency | **REFUTED (would break FR-13)** | Writing "last served" onto `skill_state` during serving violates FR-A2/FR-13 (adaptivity source-of-truth stays pure; serving is read-only). Recency must be **derived** from `attempt`, ephemeral + caller-owned — exactly like `servedIds`. |

## 2.2 Clarify decisions (2026-07-08 — the load-bearing choice)

Two questions were posed. The first answer was re-posed with evidence because it did not solve the
reported defect:

| Question | Decision | Note |
|---|---|---|
| Recency source: skill-of-item-shown vs answered-attempts | **Answered attempts** | Recency = skills with a recorded `attempt` row this session — the exact source `servedIds` already uses. One source of truth; no new shown-but-unanswered plumbing. |
| Rotation strength: strict (rotation primary) vs tie-break vs no-immediate-repeat | **Strict rotation** (re-posed) | The initial pick "rotation as tie-break" was **REFUTED**: the seed masteries are all distinct (0.28/0.40/0.55/0.61/0.74/0.82) so there are **no mastery ties to break** — `s-sent` stays perpetual-next and the bug is unfixed. Strict rotation (least-recently-served as the **primary** sort key) is required to change the observed behaviour, and is what "rotate across skills" asks for. |

**Accepted trade (strict):** rotation outranks mastery, so `next()` may serve a *slightly-less-weak*
eligible skill before a weaker one that was just served. This is a deliberate variety-over-strict-
adaptivity choice (ADR-0024 Consequences). Within-session mastery is frozen anyway (FR-13), so the
loss of adaptive precision *within one session* is small; across sessions `review()` still drives the
weakest-skill focus.

## 3. Functional requirements (EARS)

*Failure paths first (TAP-4).*

- **FR-1.** IF `servedSkillIds` is omitted or empty THEN `Scheduler.next()` SHALL behave exactly as
  today (weakest-mastery → `due_at` → `skill_id` order) — backward-compatible, no rotation.
- **FR-2.** IF every eligible skill has been served at least once THEN `next()` SHALL still rotate —
  ordering the eligible skills by *oldest most-recent-serve first* — and SHALL NOT throw on account
  of rotation (exhaustion is still governed only by the served-**question** set, FR-6).
- **FR-3.** IF the most-recently-served skill is still the globally weakest AND other eligible skills
  exist THEN `next()` SHALL NOT return that same skill again (it goes to the back of the rotation) —
  the direct fix for "always sentence-completion."
- **FR-4.** WHEN `servedSkillIds` is provided THE `Scheduler.next()` SHALL make least-recently-served
  the **PRIMARY** sort key (strict rotation): a skill **absent** from `servedSkillIds` sorts ahead of
  any served skill; among served skills the one whose most-recent serve is **oldest** (nearest the
  tail of the newest-first list) sorts ahead; and **only then** ties are broken by the existing
  weakest-mastery → `due_at` → `skill_id` order.
- **FR-5.** THE `AttemptRepo` SHALL expose `servedSkillIds(sessionId)` returning the distinct skills
  served in that session **newest-first** (most-recently-served skill at index 0), derived from the
  append-only `attempt` rows joined to their questions; it SHALL return `[]` (not throw) for a
  session with no attempts.
- **FR-6.** THE within-session no-repeat guarantee (S3 FR-9/10/11) SHALL be unchanged: `next()` never
  returns a question in `servedIds`, falls through skills on question-exhaustion, and throws
  `EngineNotFoundError` only when **every** eligible skill's reviewed questions are all served.
  Rotation re-orders *which eligible skill is tried first*; it never re-serves a question and never
  changes the exhaustion condition.
- **FR-7.** THE `next()` call SHALL perform **zero** `skill_state` writes when `servedSkillIds`
  (and/or `servedIds`) is supplied — rotation is a pure read policy (FR-13 purity preserved).
- **FR-8.** THE new port method and DB method SHALL be **additive and optional** on every call site:
  existing callers and tests compile and pass unchanged.

## 4. Data model / contracts

No wire-shape change (this is a frontend-only engine; no Python mirror — Rule W2 / schema-baseline
do **not** apply). New **method** signatures only:

- **Port** `AttemptRepo` ([attempt_repo.ts](../../frontend/lib/ports/engine/attempt_repo.ts)):
  `servedSkillIds(sessionId: string): Promise<readonly string[]>` — newest-first, distinct.
- **`EngineDb`** ([engine_db.ts](../../frontend/lib/adapters/engine/db/engine_db.ts)):
  `listSessionSkillIds(sessionId: string): Promise<string[]>` — newest-first, distinct.
- **Port** `Scheduler` ([scheduler.ts](../../frontend/lib/ports/engine/scheduler.ts)):
  `next(subject, learnerId, servedIds?, servedSkillIds?)` — 4th optional param
  `servedSkillIds?: readonly string[]`.

No new column; no dialect-schema change; no migration. `attempt` already stores `question_id` and
`created_at`; both `question` and `test_item` already store `skill_id`. The read resolves the served
`question_id` against **both** tables (a `question` id on the dev/practice path, a `test_item` id on
the ADR-0021 bank path) — see §6 "Bank-served ids".

## 5. Invariants & security boundaries

- **Frontend Ring F-R2 / A1 (SDK confinement):** no SDK touched; `ts-fsrs` stays confined to
  `fsrs_scheduler.ts`. The drizzle join stays in `drizzle_engine_db.ts` (`db/` only), like the
  existing `NOT IN` push-down.
- **Engine FR-A2 / S3 FR-13 (adaptivity purity):** rotation reads only `attempt` rows; **no**
  `skill_state` write on the serve path. `review()` remains the sole writer. This is the invariant
  most at risk and §3 FR-7 pins it with a spy-count test.
- **A2 / FE-AP-2 (no cross-adapter imports):** the scheduler consumes the served skills via its
  existing `QuestionRepo`/caller seam; recency is passed **in** by the caller (`use_quiz`), not
  fetched by the scheduler reaching into a sibling adapter.
- **Backward-compatibility:** all new params optional (FR-1/FR-8) — omission is today's behaviour.

**Two ⚠️ Ask-first triggers → ADR-0024:** (1) a **new cross-port capability**
(`servedSkillIds`/`listSessionSkillIds`, same class as S3's T-b0), and (2) a **new
scheduling-order policy** (round-robin fairness layered over weakest-first) — a design choice that
changes real adaptive behaviour for all learners, not just the demo seed.

## 6. Edge cases

- **First pick of a session** (`servedSkillIds = []`): FR-1 — no rotation; weakest-first as today.
- **Single eligible skill** (a `?focus=` drill): rotation is a no-op — the one skill is always
  chosen until its questions exhaust (then FR-6 throw). Rotation must not throw here.
- **A skill served but now question-exhausted:** it may sort first by recency yet yield `null` from
  `nextReviewed(…, servedIds)`; the walk must **fall through** (FR-6) — rotation order never
  short-circuits the fall-through/exhaustion logic.
- **Duplicate skills in the served list:** `servedSkillIds` is **distinct**; the underlying attempts
  repeat skills, so the DB read must de-dup while keeping the newest occurrence's position.
- **A served skill no longer in the pool** (not due, filtered out): it simply doesn't appear in the
  candidate pool; its presence in `servedSkillIds` is harmless.
- **Bank-served ids (ADR-0021) — the load-bearing one.** The live `/learn` quiz serves
  `TestItemQuestionRepo` over the `test_item` table, so `attempt.question_id` holds a **`test_item`
  id**, not a `question` id. `listSessionSkillIds` MUST resolve skill from **both** id-spaces
  (`question` OR `test_item`, both carry `skill_id`) — resolving only `question` makes rotation
  silently no-op on the exact surface it was built for. The in-memory fake checks both maps; the
  drizzle seam `LEFT JOIN`s both tables and `COALESCE`s the skill. *(Found during implement: the
  bank-backed harness walk parked on `s-punc` while the `question`-seeded unit tests passed — the
  harness caught the id-space gap. Now covered by an explicit bank-item unit test.)*
- **Only the *due* skills rotate.** Rotation reorders the candidate pool, which is the **due** skills
  when any are due (unchanged from today). So a session cycles the due buckets; not-yet-due skills stay
  out until `review()` or time makes them due. This is correct adaptivity — and it is what removes
  `s-sent` (a *future*-due skill in the dev seed) from the perpetual-answer slot.

## 7. Non-functional requirements

- **Determinism (L1):** given the same seed + served history + clock, `next()` is deterministic
  (the tie-break chain is total — mastery → due → id — so no run-to-run drift; FSRS fuzz already OFF).
- **Cost:** one extra session-scoped read per pick (`listSessionSkillIds`), same order of cost as the
  existing `servedQuestionIds` read; both are small session-local joins. No LLM, no network.
- **Reversibility:** omitting `servedSkillIds` at the call site fully reverts the behaviour (FR-1) —
  the rotation is opt-in per call.

## 8. Test plan

Failure-path tests before happy-path. All L1 deterministic, all in `make check` (frontend vitest).

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `fsrs_scheduler.test.ts::next omits servedSkillIds → weakest-first order unchanged` | L1 | yes |
| FR-3 | `fsrs_scheduler.test.ts::finished skill is not served twice in a row (rotates to another bucket)` | L1 | yes |
| FR-2/FR-4 | `fsrs_scheduler.test.ts::all-served → orders by oldest-most-recent-serve; distinct-bucket walk` | L1 | yes |
| FR-6 | `fsrs_scheduler.test.ts::rotation never re-serves a question; exhaustion still throws` | L1 | yes |
| FR-7 | `fsrs_scheduler.test.ts::next(servedSkillIds) performs zero skill_state writes` (spy) | L1 | yes |
| FR-5 | `engine_repos.test.ts::servedSkillIds returns session skills newest-first, distinct, [] when none` | L1 | yes |
| FR-5 | `in_memory_engine_db` behavioral fake conformance (via repo test) | L1 | yes |
| FR-8 | frontend `tsc --noEmit` exit 0 (additive-optional; existing callers/tests untouched) | L1 | yes |
| FR-6 | end-to-end: extend `frontend/scripts/validate_s3_bounded_session.ts` with a rotation check (walk a full session, assert no skill served twice consecutively once >1 skill eligible) | L1 | on-demand (`tsx`) |

## 9. Definition of Done

- [x] All FRs implemented; each has a passing test that was *seen to fail first* (FR-3 red against
      current code — the "always sentence-completion" reproduction — captured at engine, play-loop, AND
      real-bank-harness layers; see §10).
- [x] Touched frontend suites green (`vitest run lib/adapters/engine components/quiz` = 171 passed);
      full root `make check` **not** re-run this pass (Python-side unchanged; the engine is frontend-
      only — the relevant gates are the frontend suites + arch + `tsc`, all run below).
- [x] Invariants in §5 unbroken: `test_engine_port_conformance` + `test_frontend_layering` green
      (isolated); frontend `tsc --noEmit` exit 0; ADR ratchet + no-test-weakening pass.
- [x] **ADR-0024** appended (two ⚠️ triggers) + `index.md` entry + newest-first `log.md` line;
      `decisions.md` untouched (this is ADR-scale, not a 2–4-line note).
- [x] Actual command output pasted (not summarized) — §10.
- [x] `frontend/scripts/validate_s3_bounded_session.{ts,md}` updated with the rotation check (Result:
      22 passed, 0 failed).

## 10. Implementation evidence (Stage 6)

Red→green per task (actual output, not summarized):

- **T-r0/T-r1 (FR-5) red:** `repo.servedSkillIds is not a function` — 3 failed. **green:** `servedSkillIds`
  tests 3→4 passed (incl. the bank-item case added after the harness caught the id-space gap).
- **T-r2 (FR-3/4/2 — the fix) red:** `AssertionError: expected 's-weak' not to be 's-weak'` (the
  literal "always same skill" bug) — 3 failed / 3 passed (FR-1/6/7 pass pre-change, proving
  backward-compat + no-repeat intact). **green:** `fsrs_scheduler.test.ts` **16 passed**.
- **T-r3 (FR-3 wiring) red:** `expected 's-punc' not to be 's-punc'` (play-loop clusters) — 1 failed.
  **green:** `use_quiz.test.ts` **27 passed**.
- **Bank-resolution defect (found by the harness, not unit tests):** the real-bank walk parked on
  `s-punc` (`servedSkills=[]` every pick) because `attempt.question_id` holds a `test_item` id, not a
  `question` id (ADR-0021). Fixed `listSessionSkillIds` to resolve skill from **both** tables
  (in-memory: check both maps; drizzle: `LEFT JOIN` both + `COALESCE`). Locked out by a bank-item unit
  test. Post-fix probe: `s-punc → s-org → s-gram → s-punc → s-org → s-gram` (clean rotation).
- **`tsc` caught a real type error** vitest missed (`stem` vs `stem_md` on `TestItem`) — fixed; full
  frontend `tsc --noEmit` **exit 0**.
- **Full touched-suite gate:** `vitest run lib/adapters/engine components/quiz` → **171 passed** (16
  files). **Arch (isolated):** `test_frontend_layering` 5 passed, `test_engine_port_conformance` green
  (a combined-run flake on a non-S3.1 port import is the known ts-morph under-load artifact — green in
  isolation). **`pytest test_adr_ratchet test_no_test_weakening`** → 1 passed / 1 skipped, 1 passed.
- **E2E harness:** `tsx scripts/validate_s3_bounded_session.ts` → **Result: 22 passed, 0 failed**
  (FR-3 real-bank walk: no consecutive same-skill, 3 distinct skills; FR-1 empty-served → weakest-first).
