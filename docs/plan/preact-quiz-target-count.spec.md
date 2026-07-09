# Spec — Bounded **no-repeat** quiz session: `target_count` + within-session uniqueness (Sprint S3)

> Acceptance criteria use **EARS**. Failure paths are written first (§3). This spec is
> the *what*; the load-bearing *why* is [ADR-0023](../adr/0023-quiz-bounded-session-target-count.md)
> (to be authored at plan time — two ⚠️ Ask-first triggers fire, see §5).

**Status:** Implemented (Stage 6, groups (a)+(b) landed & green; S3-pre deferred) — 2026-07-08

> **S3-pre DEFERRED (human decision 2026-07-08).** The bank-growth prerequisite (S3-pre = +19
> reviewed items + coverage floor → 30) requires the live-LLM generation pipeline
> (`scripts/generate_test_items.py`), whose promoted rows carry an audited `generated_by =
> "<model>@<run_id>"` provenance stamp that `test_test_item_provenance_confinement.py` (ADR-0015
> clause 6) enforces as proof the independent-solver cascade actually ran. Fabricating that stamp
> for hand-authored items would forge the audit trail, so S3-pre is deferred to a real credentialed
> generation run. **The (a)+(b) code is implemented now** — it is correct without the bank growth
> because **FR-11** (end-early-on-exhaustion) is the runtime safety net: when a skill has < 30
> reviewed items the session ends rather than repeating. The coverage floor is therefore **NOT**
> raised to 30 in this pass (that would falsely assert a guarantee the 171-item bank does not meet:
> s-sent 23, s-org 24, s-rhet 28, s-style 26 are all < 30). Flat-30 becomes honest only after S3-pre.
**Owner:** Rajnish Khatri
**Related:** [preact-ui-prototype-parity-gap-matrix.md](preact-ui-prototype-parity-gap-matrix.md) (row Q-6),
[ADR-0006](../adr/0006-subject-coach-component-protocols.md) (SessionRepo #4),
[ADR-0005](../adr/0005-subject-coach-engine-home-and-substrate.md) (dual-dialect substrate),
[preact-english-coach-engine.spec.md](preact-english-coach-engine.spec.md) (FR-D1/D3 the session shape),
ADR-0021 (bank-backed practice scheduler — the serve path this constrains),
ADR-0023 (bounded-session — this spec's *why*).

---

## 2.1 Premise audit (clarify pass — user answers 2026-07-08 changed the scope)

The clarify answers introduced a **no-repeat-within-session** requirement ("all questions
must be unique … 2 different skills must not repeat the same questions … we must not review the
same questions more than once per session"). Auditing that against the code REFUTED a premise
this spec was built on:

| Premise | Status | Evidence |
|---|---|---|
| S3 is "store a count"; the loop already serves distinct items and just needs a length | **REFUTED** | `FsrsScheduler.next()` ([fsrs_scheduler.ts:73](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts)) picks the weakest skill then calls `QuestionRepo.nextReviewed(subject, skillId)`, whose signature ([question_repo.ts:27](../../frontend/lib/ports/engine/question_repo.ts)) takes **no exclusion set**. The same question CAN and WILL be re-served within a session (a drill on one skill re-asks; adaptive re-asks whenever a skill stays weakest). **Uniqueness is a NEW scheduler capability, not a property the field-add unlocks.** |
| A bounded session terminates on its own once `target_count` is stored | **REFUTED** | The reducer ([quiz_screen_reducer.ts:53](../../frontend/components/quiz/quiz_screen_reducer.ts)) tracks `SessionTally {correct,total}` (answered-so-far) but has **no terminal-on-target** — `finish→done` only on manual Finish. Termination = S5's job; S3 storing the number does not create a "done". |
| The corpus can supply 30 unique items per session across skills | **GATED-ON-DATA** | Reviewed `test_item` bank = 171 items: s-gram 39 / s-punc 31 / s-rhet 28 / s-style 26 / s-org 24 / s-sent 23. A **30-item adaptive** session across all 6 skills is satisfiable (171 ≥ 30). A **single-skill drill of 30 unique** is satisfiable for every skill (min 23 ≥ … **NO** — s-sent has 23 < 30). A 30-unique drill on `s-sent`/`s-org` is **impossible** from the current bank. |

**Consequence:** the answers describe a **bounded + no-repeat session engine**, which is
materially larger than S3-as-scoped (a nullable field + per-mode default). Three distinct
capabilities were entangled:
- **(a) the length field** — `target_count` + per-mode default.
- **(b) within-session uniqueness** — a NEW served-ids exclusion seam on the scheduler +
  `QuestionRepo` port.
- **(c) terminal-on-target ("review is finished")** — the visible done-state.

**Human gate decisions (2026-07-08 clarify):**
- **Enlarge S3 = (a) + (b)** — the length field AND within-session uniqueness ship together as
  one spec + ADR-0023 ("bounded no-repeat session"). This spec now covers both.
- **(c) stays S5** — the *visible* "review is finished" done-state + retake remains S5's job;
  S3 makes the serving correct (bounded + never-repeats) and exposes the signals S5 renders.
- **Flat 30 everywhere, gated-on-data** — `target_count` default = **30** for every mode. The
  30-unique **drill** is impossible today for thin skills (s-sent 23, s-org 24), so S3 is
  **gated on a bank-growth prerequisite (S3-pre)**: generate + cascade-promote **+19** reviewed
  `test_item`s (rhet +2, style +4, org +6, sent +7 → every skill ≥ 30) and raise the ADR-0022
  per-skill coverage floor to 30, BEFORE the flat-30 uniqueness guarantee can hold. S3-pre is a
  blocking dependency of the S3 implement phase.

### 2.2 The uniqueness seam (b) — design shape

`FsrsScheduler.next(subject, learnerId)` must learn a **served-ids exclusion set** so it never
returns a `question_id` already served this session. The minimal port-respecting shape:
- `QuestionRepo.nextReviewed(subject, skillId, excludeIds?: readonly string[])` — the reviewed
  gate is unchanged; the repo skips excluded ids and returns `null` when the skill is exhausted
  (the existing null contract already models "no more").
- `EngineDb.nextReviewedQuestion(subject, skillId, excludeIds?)` + `TestItemQuestionRepo` +
  `InMemoryEngineDb` + the live drizzle seam honour the exclusion (a `NOT IN` push-down on the
  live path; a filter on the fake).
- `Scheduler.next(subject, learnerId, servedIds?: readonly string[])` — the served set is owned
  by the **caller** (the session play loop in `use_quiz`), not persisted on `skill_state`, and
  passed in per `next()`. Rationale: served-ids are session-scoped ephemeral state; putting them
  on the durable `skill_state` row would pollute the adaptivity source of truth (FR-A2). The
  attempt table already records what was served, so the loop can derive the set from attempts.
- **Skill exhaustion during adaptive.** If the weakest skill is exhausted (all its reviewed
  items served this session), `next()` falls through to the next-weakest with unserved items —
  the pick logic already sorts a pool; exhausted skills drop out. When ALL skills are exhausted
  before `target_count`, the session ends early (bounded by the union of banks) — the same
  "session finished" terminal S5 renders, reached by exhaustion instead of by count.

---

## 1. Goal

Give a quiz session a **bounded length**: a nullable `target_count` on `QuizSession` that
records how many items the session is meant to serve, with a **per-mode default** (adaptive
gets one length, drill another). `null` means *endless* — the current behaviour — so the
change is backward-compatible. This is the data spine that unblocks S4 (the "Question N / M"
top bar + progress bar) and S5 (the done-state + retake); **S3 stores the number; it does
not yet render or enforce it.**

For: the PreAct English Coach `/learn` learner, who today faces an infinite quiz loop with no
first/last question (gap-matrix row Q-6).

## 2. Context

The quiz loop is infinite **by design** today: `openQuizItem` always calls `scheduler.next()`
([use_quiz.ts:91](../../frontend/components/quiz/use_quiz.ts)) which returns the most-due card
forever ([fsrs_scheduler.ts](../../frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts)),
and `QuizSession` ([engine_entities.ts:199](../../frontend/lib/wire/engine_entities.ts)) has no
length field. The prototype (all three device specs) runs **bounded 10-item sessions** with a
visible first and last question. Closing that gap is the S3→S4→S5 "bounded-session spine"; S3
is the field, sequenced first because S4 and S5 both *read* it.

Two settled brainstorm decisions constrain this spec (gap-matrix §"oracle-derived decisions"):
- **Session length is per-mode** — adaptive vs drill get different N.
- **Backward-compatible** — `null` = endless; existing sessions and callers keep working.

Grounding facts established before drafting (all verified in-tree 2026-07-08):
- The engine wire family (`QuizSession`, `Skill`, …) is **frontend-only** — there is **no
  Python mirror** in `agent_ui_adapter/wire/` and **no entry** in
  `frontend/lib/wire/__python_schema_baseline__.json` (0 hits). So Rule W2 / FE-AP-14 (mirror
  Python + update the baseline) **do not apply** to `target_count`; the wire change is
  TS-Zod-only.
- `schema.pg.ts` and `schema.sqlite.ts` are **parity-guarded** (dual-dialect rule, ADR-0005;
  a `schema.spec` parity test compiles both and fails on drift). `target_count` must be added
  to **both**, column-for-column identical in name/nullability/default intent.
- `SessionRepo.open()` already takes 4 params (`subject, learnerId, mode, focus?`) and
  `OpenSessionArgs` ([use_quiz.ts:46](../../frontend/components/quiz/use_quiz.ts)) already
  carries `focus?` — S3 adds one optional param / field alongside `focus`, the same shape.

## 3. Functional requirements (EARS)

Failure / edge paths first (TAP-4). Two capability groups: **(a)** the length field / default,
**(b)** within-session uniqueness.

### (a) `target_count` field + per-mode default

- **FR-1 (unwanted — invalid target).** IF a caller supplies a `target_count` that is not a
  positive integer (≤ 0, non-integer, `NaN`) THEN the system SHALL reject it at the wire
  boundary (Zod `safeParse` fails) rather than persist a nonsensical length.
- **FR-2 (unwanted — endless preserved).** IF a session is opened with an explicit
  `target_count = null` THEN the system SHALL store `null` and the session SHALL be endless
  (no bound) — the backward-compatible escape hatch.
- **FR-3 (state — backward compat on read).** WHILE reading a persisted session that predates
  this change (legacy row, no `target_count` column value) the system SHALL surface
  `target_count = null`, never throw, never fabricate a number.
- **FR-4 (ubiquitous — the field).** THE SYSTEM SHALL define `target_count` on `QuizSession`
  as a nullable positive integer, present on the wire shape, both DB dialects, and the
  `SessionRepo` open contract.
- **FR-5 (event — default 30 on open).** WHEN a session is opened without an explicit
  `target_count`, THE SYSTEM SHALL resolve the default (**30** for every mode — adaptive, drill,
  review) from a single `content_string`-backed policy source and persist it.
- **FR-6 (event — explicit target wins).** WHEN a caller opens a session WITH a valid explicit
  `target_count`, THE SYSTEM SHALL persist that value and NOT override it with the default.
- **FR-7 (ubiquitous — stored, not recomputed).** THE SYSTEM SHALL treat `target_count` as a
  stored session property set at open and unchanged by `close()` — the score tally is the only
  thing `close()` writes (FR-D3 untouched).
- **FR-8 (invariant — parity).** THE SYSTEM SHALL keep `schema.pg.ts` and `schema.sqlite.ts`
  column-for-column identical for `target_count` (name, nullability, default intent), so the
  dual-dialect parity test passes.

### (b) within-session uniqueness (no-repeat)

- **FR-9 (unwanted — no repeat within a session).** IF a `question_id` has already been served
  in the current session THEN the scheduler SHALL NOT return it again — `next()` returns a
  question whose id is NOT in the caller-supplied served set.
- **FR-10 (event — skill exhaustion falls through).** WHEN the weakest due skill has no unserved
  reviewed items left this session, THE SYSTEM SHALL select the next-weakest skill that still
  has unserved items, rather than repeat or dead-end.
- **FR-11 (unwanted — all skills exhausted).** IF every skill's reviewed items are exhausted for
  the session before `target_count` is reached THEN `next()` SHALL surface "no more items"
  (the existing `null`/not-found contract) so the caller can end the session early — never a
  repeat to pad the count.
- **FR-12 (state — reviewed gate preserved).** WHILE excluding served ids the system SHALL keep
  the reviewed gate intact — an excluded set never causes a `reviewed=false` item to be served
  (FR-B*), and the exclusion is applied *within* the reviewed pool only.
- **FR-13 (ubiquitous — served set is ephemeral, caller-owned).** THE SYSTEM SHALL keep the
  served-ids set session-scoped and passed per-`next()` call — it SHALL NOT be persisted on the
  durable `skill_state` row (FR-A2: skill_state stays the pure adaptivity source of truth).

### Scope boundary

- **FR-14 (invariant — S3 does not render/terminate visibly).** THE SYSTEM SHALL NOT add the
  "Question N / M" bar (S4) or the visible "review is finished" done-state + retake (S5) in S3.
  S3 makes serving bounded + non-repeating and stores `target_count`; the *visible* progress and
  terminal UI are S4/S5. (The scheduler's early "no more items" from FR-11 is a serving signal
  S5 will render, not a new screen in S3.)

## 4. Data model / contracts

**Wire** — `frontend/lib/wire/engine_entities.ts`, `QuizSession` gains:
```ts
target_count: z.number().int().positive().nullable(),
```
(nullable, positive-int; `null` = endless). No Python mirror, no `__python_schema_baseline__`
change (§2 grounding). ⚠️ Ask-first trigger → ADR-0023.

**Port — SessionRepo** — `frontend/lib/ports/engine/session_repo.ts`, `open()` gains a 5th
optional param mirroring `focus?`:
```ts
open(
  subject: string, learnerId: string, mode: SessionMode,
  focus?: string | null,
  targetCount?: number | null,   // omit → default 30; null → endless; value → that value
): Promise<QuizSession>;
```

**Port — QuestionRepo + Scheduler** (the uniqueness seam, ⚠️ new capability → ADR-0023):
```ts
// question_repo.ts — reviewed gate unchanged; skip already-served ids
nextReviewed(subject: string, skillId: string, excludeIds?: readonly string[]): Promise<Question | null>;
// scheduler.ts — served set owned by the caller, passed per call
next(subject: string, learnerId: string, servedIds?: readonly string[]): Promise<NextItem>;
```
Both new params are **optional** → every existing caller/test compiles unchanged; omitting them
is exactly today's behaviour (backward-compatible).

**EngineDb** — `nextReviewedQuestion(subject, skillId, excludeIds?)` gains the optional exclude
set; the live drizzle seam pushes it down (`NOT IN`), the `InMemoryEngineDb` fake filters, and
`TestItemQuestionRepo` forwards it. `insertSession`/`getSession` carry `target_count`;
`patchSessionClose` leaves it untouched (FR-7).

**Component façade** — `OpenSessionArgs` ([use_quiz.ts:46](../../frontend/components/quiz/use_quiz.ts))
gains `readonly targetCount?: number | null;`. `openQuizSession` threads it into
`sessionRepo.open(...)`. The play loop (`openQuizItem`) obtains the served-ids set and passes it
to `scheduler.next(...)`.

**Served-ids source (Stage-4 refinement).** Grounding found **no session-scoped attempt read
today** — `AttemptRepo` exposes only `record()` + `misses(subject, learnerId)` (incorrect
attempts, not the full served set — [attempt_repo.ts:4](../../frontend/lib/ports/engine/attempt_repo.ts)),
`EngineDb` only `listMisses`, and the reducer carries `SessionTally {correct,total}` but **no
served-id history** ([quiz_screen_reducer.ts:53](../../frontend/components/quiz/quiz_screen_reducer.ts)).
So the reload-safe FR-13 contract ("derive served-ids from the append-only attempt rows")
requires a **new read**: `AttemptRepo.servedQuestionIds(sessionId): Promise<readonly string[]>`
+ an `EngineDb.listSessionQuestionIds(sessionId)` seam (a `question_id` projection scoped by
`session_id`, both dialects + fake). `openQuizItem` calls it before `scheduler.next(...)`.
Chosen over the lighter alternative (accumulate served-ids in reducer/loop memory across the
walk — no new engine read, but a mid-session reload loses the set and re-serving becomes
possible) because FR-13's reload-safety was already committed to; the in-memory option is the
fallback only if reload-safety is dropped.

**DB (both dialects, parity-guarded)** — `schema.pg.ts` + `schema.sqlite.ts` `quizSession` both
gain `target_count: integer("target_count")` (nullable, no default). Migration = one nullable
column add per dialect, no backfill.

**Per-mode default policy** — a `content_string` row per mode (keys e.g.
`session.target_count.adaptive` / `.drill` / `.review`, value `"30"`), read via the existing
`ContentRepo` at open. Value stored as the session's `target_count`. This is the *new
abstraction* (policy-as-data) that ADR-0023 governs; it reuses the ADR-0022 `content_string`
plane rather than a new table.

**Bank prerequisite (S3-pre, gated-on-data)** — before the flat-30 uniqueness guarantee holds:
generate + cascade-promote **+19** reviewed `test_item`s via the existing pipeline
(`scripts/generate_test_items.py` → cascade → `scripts/promote_test_item_seed.py` →
`scripts/emit_test_item_bank.py`) so every skill ≥ 30 (rhet +2, style +4, org +6, sent +7), and
raise the ADR-0022 per-skill floor in `docs/plan/act-english-coverage-floors.json` to 30. This
is a **blocking dependency** of the S3 implement phase.

## 5. Invariants & security boundaries

- **F-R8 / Rule A4 (no SDK type escapes the adapter).** `target_count` is a plain wire
  `number | null`; served-ids are plain `readonly string[]`. The Drizzle row→wire mapping + the
  `NOT IN` push-down stay inside the DB adapter. No vendor type crosses the boundary.
- **F-R1 (no domain logic in components).** The default *policy* is data (`content_string`),
  read in the engine layer; the served-ids *set* is derived from the engine's own attempt
  records, not computed in a component. `use_quiz` forwards `targetCount` and passes a served-ids
  array to `scheduler.next` — it holds no scheduling *decision* (which id to skip / which skill
  is next lives in the scheduler). Mirrors how S2 extracted the drill-vs-adaptive decision into
  the pure `resolve_focus_mode.ts` helper.
- **FR-A2 (skill_state is the sole adaptivity source of truth).** Served-ids are ephemeral +
  caller-owned (FR-13) — they are NEVER written to `skill_state`. The scheduler stays the sole
  `skill_state` writer via `review()` only; `next()`'s new param is read-only input.
- **Reviewed gate (FR-B*) preserved (FR-12).** The exclusion set filters *within* the reviewed
  pool; it can never surface a `reviewed=false` item. `TestItemQuestionRepo`'s double reviewed
  gate (ADR-0021) is untouched.
- **Wire kernel purity (Rule W1).** `engine_entities.ts` stays a pure Zod shape.
- **Dual-dialect parity (ADR-0005).** FR-8 — the parity test is the mechanical guard.
- **Determinism (Scheduler contract).** `next()` with a served set stays deterministic given
  (skill_state, served-ids, injected clock) — the exclusion is a pure filter before the existing
  most-due/weakest sort; the `localeCompare` final tie-break already removes store-order
  nondeterminism.
- **ADR-0022 coverage ratchet.** S3-pre raises the per-skill floor to 30 — a rises-only diff;
  the ratchet test mechanically blocks any later lowering.
- **⚠️ Ask-first triggers (→ ADR-0023, ADR.1):** (1) a shared wire/kernel type change
  (`QuizSession`, the frontend analogue of a persisted `trust/models.py` type); (2) a **new
  abstraction / capability** (the served-ids exclusion seam across Scheduler + QuestionRepo +
  EngineDb, and the policy-as-data default). Both covered by the single ADR-0023. S3-pre's bank
  growth + floor raise reuse the ADR-0022 pipeline (no new abstraction) but are a **generation/
  data change** — recorded in ADR-0023's consequences, no separate ADR. No new
  `package.json`/`pyproject.toml` dep; no new graph node; no Python trust-kernel change → no
  re-signing.
- **No security boundary touched** — no secrets, no live-LLM on the request path (generation is
  offline, creds-gated, its output cascade-verified before commit — the ADR-0021/0022 posture),
  no sandbox, no auth.

## 6. Edge cases

- **`target_count = null` (endless).** First-class value, not an absence — FR-2/FR-3. Never
  coerce `null` → `0` (AP-6). Explicit `null` = endless; omitted = default 30 — the port
  distinguishes "arg not passed" (→ default) from "passed `null`" (→ endless).
- **Legacy rows / migration.** A pre-change `quiz_session` row reads back `target_count = null`
  (nullable column, no default). Migration = nullable column add, no backfill.
- **Invalid explicit value** (0, -3, 2.5, NaN). Rejected at the Zod boundary (FR-1); the repo
  does not additionally clamp (the wire parse is the single guard — least machinery).
- **Thin-skill drill (the gated-on-data case).** After S3-pre every skill has ≥ 30 reviewed
  items, so a 30-unique drill is satisfiable for all six. BEFORE S3-pre it is not (s-sent 23,
  s-org 24) — which is exactly why S3-pre blocks the implement phase. FR-11 is the safety net
  even post-S3-pre: if a bank ever dips below 30, the session ends early rather than repeating.
- **All-skills-exhausted before target.** FR-11 — `next()` returns the null/not-found signal;
  the session ends at the union-of-banks bound, not by padding with repeats.
- **Served-ids source of truth.** Derived from the session's `attempt` rows (append-only,
  FR-D2) so a page reload mid-session reconstructs the served set — no separate ephemeral store
  to lose. (The set is *passed* to `next()`; it is not persisted on `skill_state`.)
- **Concurrency.** `open()` is one insert; `target_count` set once, never mutated. Served-ids
  are read per `next()` call; no concurrent-write hazard.

## 7. Non-functional requirements

- **Determinism / cost.** Schema + repo + scheduler-filter change; zero LLM on the serve path,
  zero network. All serve-path tests L1 deterministic. Bank generation (S3-pre) is offline +
  creds-gated + cascade-verified; **no live LLM in CI** (committed emitted bank replayed).
- **Reversibility.** Nullable additive column + optional params = backward-compatible; revert is
  a column drop + param removals. Coverage-floor raise is the one non-trivial-to-revert change
  (the ratchet blocks lowering) — intentional.
- **Latency.** One extra integer column on an insert; one `NOT IN (…served ids…)` predicate on
  the next-question read (bounded by `target_count` ≤ ~30 ids — negligible).

## 8. Test plan

Failure-path tests first. All serve-path tests L1 deterministic, in the frontend unit + arch
suites (`pnpm test` / `pnpm run test:arch` — the frontend CI jobs are the gate; this is a
frontend + offline-generation change, not the Python `make check` path).

| FR | Test | Layer | In frontend CI? |
|----|------|-------|-----------------|
| FR-1 | `engine_entities.test.ts::QuizSession rejects target_count ≤ 0 / non-int / NaN` | L1 | yes |
| FR-2 | `engine_repos.test.ts::open(explicit null) → target_count null (endless)` | L1 | yes |
| FR-3 | `engine_repos.test.ts::getSession on a row without target_count → null` (fake + drizzle) | L1 | yes |
| FR-4 | `engine_entities.test.ts::QuizSession parses a positive-int target_count` | L1 | yes |
| FR-5 | `engine_repos.test.ts::open(no target) → 30 from content_string` (each mode) | L1 | yes |
| FR-6 | `engine_repos.test.ts::open(explicit value) wins over the default` | L1 | yes |
| FR-7 | `engine_repos.test.ts::close() leaves target_count unchanged` | L1 | yes |
| FR-8 | existing `schema` parity test green with the new column on both dialects | L1 (arch) | yes |
| FR-9 | `fsrs_scheduler.test.ts::next(servedIds) never returns an excluded id` | L1 | yes |
| FR-9 | `engine_repos.test.ts::nextReviewed(excludeIds) skips served, honours reviewed gate` | L1 | yes |
| FR-10 | `fsrs_scheduler.test.ts::weakest skill exhausted → falls through to next-weakest unserved` | L1 | yes |
| FR-11 | `fsrs_scheduler.test.ts::all skills exhausted → null/not-found (no repeat)` | L1 | yes |
| FR-12 | `test_item_question_repo.test.ts::exclude never surfaces a reviewed=false item` | L1 | yes |
| FR-13 | `fsrs_scheduler.test.ts::next(servedIds) performs NO skill_state write` (served set is read-only) | L1 | yes |
| FR-9..13 | port-conformance: both `QuestionRepo` + both `EngineDb` seams honour `excludeIds` | L1 (arch) | yes |
| S3-pre | `test_syllabus_coverage_ratchet.py` green at floor 30; bank emit drift-pin green | L1 (arch) | yes |

## 9. Definition of Done

- [ ] **S3-pre (DEFERRED — see Status note):** +19 reviewed `test_item`s promoted (every skill
      ≥ 30) via the live-LLM cascade; bank re-emitted; ADR-0022 per-skill floor raised to 30;
      ratchet + provenance + emit-drift tests green. **Blocked on a credentialed generation run —
      not done in this pass.** Runtime stays correct meanwhile via FR-11 (end-early-on-exhaustion).
- [x] All FRs implemented; each has a passing test *seen to fail first* (red/green). ✓ (§11)
- [x] **(a)** `target_count` on `engine_entities.ts` + both DB dialects (parity green) +
      `SessionRepo.open` + `OpenSessionArgs` + both `EngineDb` seams; default 30 from `content_string`
      (flat-30 fallback). ✓
- [x] **(b)** `excludeIds` on `QuestionRepo.nextReviewed` + `EngineDb.nextReviewedQuestion`
      (drizzle `NOT IN` + fake filter + `TestItemQuestionRepo`); `servedIds` on `Scheduler.next`;
      `use_quiz` play loop derives served-ids from attempts and passes them. ✓
- [x] Served-ids never written to `skill_state` (FR-13, spy = 0 upserts); reviewed gate intact (FR-12). ✓
- [x] Frontend unit + tsc green (**1448/1450**, 2 ts-morph timeout flakes on non-S3 ports; **tsc 0**). ✓
- [ ] ~~Drizzle migration generated for both dialects~~ **N/A** — the engine has no migration
      pipeline (only `thread_store` does; `drizzle-kit` CLI absent; engine store is currently
      `InMemoryEngineDb`). The nullable column is schema-driven and picked up when the Drizzle
      engine store lands; both dialects already carry it identically. See tasks T-a3.
- [x] Invariants in §5 unbroken; Python arch suite **181 passed / 3 skipped**; port-conformance
      green in isolation (55/56, 1 rotating ts-morph timeout). ✓
- [x] **ADR-0023 appended** (status → Accepted) with frontmatter, `index.md` entry, newest-first
      `log.md` line; ADR ratchet **1 passed**. ✓
- [x] Actual command output pasted (not summarized) in the §11 evidence block for each claim. ✓
- [x] **No visible progress bar (S4) / done-state (S5)** added in S3 — FR-14 (git status: no new
      component files). `next()`'s early "no more items" is a serving signal S5 renders later. ✓

---

## 10. Stage-4 analyze (cross-artifact + grounding + baseline)

**Cross-artifact consistency (spec ↔ plan ↔ tasks ↔ ADR-0023 ↔ constitution):** consistent. Every
FR (§3) maps to a plan touchpoint (§1) and a task (T-a*/T-b*/T-pre*) with a 1:1 test (§8/tasks
checklist). No CRITICAL: no invariant violation, no zero-coverage FR, no reference to a
non-existent file/API after the grounding pass.

**Grounding pass (every referenced path/API opened in-session):** `engine_entities.ts:199`
(`QuizSession`), `session_repo.ts` (`open` 4 params today), `scheduler.ts:35` (`next` 2 params),
`question_repo.ts:27` (`nextReviewed`, no exclude), `engine_db.ts` (`nextReviewedQuestion`,
`insertSession`/`getSession`/`patchSessionClose`), `drizzle_engine_db.ts` (`_toSession`,
`nextReviewedQuestion` where-clause), `in_memory_engine_db.ts`, `test_item_question_repo.ts`,
`drizzle_question_repo.ts` (present), `schema.pg.ts`/`schema.sqlite.ts` (`quizSession`, parity),
`use_quiz.ts:46/104` (`OpenSessionArgs`, `openQuizItem`→`scheduler.next`), `attempt_repo.ts:4`
(`record`+`misses` only), `quiz_screen_reducer.ts:53` (`SessionTally`, no served history), the
bank corpus per-skill counts, and the ADR-0021/0022 generation pipeline scripts. **One refinement
surfaced and folded in:** no session-scoped served-ids read exists → added `AttemptRepo.servedQuestionIds`
+ `EngineDb.listSessionQuestionIds` (T-b0) to honor FR-13's reload-safety (see §4 "Served-ids source").

**No new dependency:** no `package.json` / `pyproject.toml` change; `ts-fsrs` + drizzle stay
confined to their adapters. No new graph node; no Python trust-kernel change → no re-signing.

**Baseline (was green before implement):**
- `npx tsc --noEmit` (frontend) → **exit 0** (clean). ✓
- `tests/architecture/test_adr_ratchet.py` → **1 passed** (ADR-0023 satisfies the ratchet). ✓
- `pnpm run test:arch` (frontend F-R1..R9) → **170 passed / 5 files, exit 0**. ✓

---

## 11. Implementation evidence (Stage 6 — sdd-implement, 2026-07-08)

Every task red-watched-fail then green (per-task output pasted below is the summary line vitest
prints; each was run from `frontend/` with the local `./node_modules/.bin/vitest` so the stale
`.claude/worktrees/*` copies don't pollute discovery).

**(a) `target_count` field — DONE**
- **T-a1** wire + dual-dialect parity: `engine_entities.test.ts` red 6/6 → green; parity = identical
  nullable `integer("target_count")` in both `schema.pg.ts` + `schema.sqlite.ts`; `tsc` surfaced the
  7 additive-field construction sites → all carried the field. **4 files / 36 passed, tsc 0.**
- **T-a2** repo default + DB seams: `engine_repos.test.ts` red 4/4 (`expected null to be 30/12`) →
  green; `open()` 5th param resolves 30 from `content_string` (flat-30 fallback when absent),
  explicit value/`null` pass through, `close` leaves it. **22 passed, tsc 0.**
- **T-a3** migration: **N/A** — no engine migration pipeline exists (only `thread_store` has one;
  `drizzle-kit` CLI absent; engine store is `InMemoryEngineDb`). The nullable column is schema-driven,
  picked up when the Drizzle engine store lands. Recorded in tasks §T-a3.
- **T-a4** component façade: `use_quiz.test.ts` red 2/2 (`expected 30 to be 5 / null`) → green;
  `OpenSessionArgs.targetCount` threaded verbatim (undefined→default, null→endless, value→that).
  **24 passed, tsc 0.** Both composition roots (`composition_engine.ts` + `_browser.ts`) wire the
  shared `ContentRepo` into `sessionRepo`.

**(b) within-session no-repeat — DONE**
- **T-b0** served-ids read: `engine_repos.test.ts` red via tsc (method absent) → green;
  `AttemptRepo.servedQuestionIds(sessionId)` + `EngineDb.listSessionQuestionIds` on all seams. **24 passed.**
- **T-b1** port signatures: `excludeIds?`/`servedIds?` added optional to `QuestionRepo.nextReviewed`,
  `EngineDb.nextReviewedQuestion`, `Scheduler.next` + JSDoc → **tsc 0** (existing impls still satisfy).
- **T-b2** DB + repo exclusion: `engine_repos.test.ts` + `test_item_question_repo.test.ts` red 5/5
  (`expected q1 to be q2`, all-excluded not null) → green; drizzle `NOT IN` (skip when empty),
  in-memory filter, both question repos forward. **37 passed, tsc 0.**
- **T-b3** scheduler fall-through + exhaustion: `fsrs_scheduler.test.ts` red 3/3 (FR-9/10/11) → green;
  `next()` walks the weakest-first pool asking `nextReviewed(…, servedIds)`, falls through on null,
  throws `EngineNotFoundError` when all exhausted, zero `skill_state` write (FR-13 spy = 0 upserts).
  **10 passed, tsc 0.**
- **T-b4** play-loop wiring: `use_quiz.test.ts` red 2/2 (`expected q1 to be q2`) → green;
  `openQuizItem` derives served-ids from `attemptRepo.servedQuestionIds(sessionId)` and passes to
  `scheduler.next`; the page threads `sessionId: session.id`. A multi-item walk never repeats.
  **26 passed, tsc 0.** One pre-existing test (`fails closed … no bank item`) legitimately updated:
  the T-b3 exhaustion message changed to "no unserved reviewed question", so its regex tightened from
  `/no reviewed question/` → `/reviewed question/` (still requires a throw about a reviewed question;
  a message-change follow-through, NOT a weakening — G8).

**Full gate (T-g):**
- `./node_modules/.bin/vitest run` (full frontend, jsdom+node) → **1448 passed / 1450**; the **2
  "failures" are `Error: Test timed out in 10000ms`** in `test_port_conformance.test.ts` — the known
  ts-morph-under-load flake ([[frontend-vitest-tsmorph-timeout-artifact]]): the timed-out port
  **rotates** run-to-run (`auth_provider.ts`, then `feature_flag_provider.ts`) and is never an S3 port
  nor an assertion failure. Isolated re-run of that file → **55/56** (one different port times out),
  and the four S3 ports pass. Total run 155s (needs >10s/test under full load).
- `npx tsc --noEmit` (frontend) → **exit 0** (clean).
- **FR-14 (no S4/S5 UI):** `git status` shows **no new component files**; the 24 changed files are
  engine seams + tests + one page-wiring line + two composition wirings; nothing matching
  progress/done/finish. `next()`'s early not-found is a *serving signal* (S5 renders it later), not a
  component.

**Deferred (recorded, not done):** S3-pre bank growth + coverage-floor-30 (blocked on a credentialed
LLM generation run — forging the `<model>@<run_id>` provenance stamp is refused; FR-11 keeps runtime
correct meanwhile). See §Status note + tasks §S3-pre + `decisions.md`.
