# Tasks — Coach V3 Durable Learner Engine

> Executes [coach-v3-durable-progress.plan.md](coach-v3-durable-progress.plan.md) against
> [coach-v3-durable-progress.spec.md](coach-v3-durable-progress.spec.md) (~60 FRs, 7 tracks;
> **re-approved 2026-07-22 after review rounds 5–6**; ADR-0038 accepted).
> **Regenerated in full (Stage 3, 2026-07-22)** after the Stage-5 replan. This decomposition absorbs:
> the **31-method** surface + per-method disposition incl. 4 **server-only** content writes (FR-A4),
> the **coarse client/loader seam** + 3-hook/scheduler rewiring (FR-A6 revised), **in-adapter**
> idempotency (`.onConflictDoNothing` typed result — FR-A9.1), commit-first **first_try-only**
> scoring (FR-B10), the **multi-source `DO UPDATE` seed + soft-retire** (FR-G1/G2), the **`0000`
> baseline + `migrate_engine.mjs` runner + threads/marker coverage** (FR-F2/F3), the
> **`requireOwnedSession`** ownership guard (FR-A2a), and method #31 `getNewestOpenSession`.
>
> **Red/green TDD per task** — write the test, *watch it fail first*, then implement. Each task ends
> by checking its own pass/fail criterion, mapped 1:1 from the spec's EARS FRs (the §8 test table is
> the backbone). `[P]` = may run in parallel within its phase once its dependency line is satisfied.
> The §8 "In gate?" column decides whether a test runs in `make check`/vitest or is an on-demand probe.
>
> **Sequencing (spec §9a — an ordering constraint, not a schedule):**
> `G + F (prereqs, parallel) → 4 (DDL + new methods) → A (atomic swap, +G3 guard) → C → B / E → D → Z`.
> A is all-or-nothing (FR-A4 atomic surface); C is first in the B/C/E group because it produces the
> completed sessions B must-not-resume (FR-B7) and D summarizes.

**Status:** Regenerated (Stage 3) — 2026-07-22 · **Owner:** Rajnish Khatri
**Frontend test runner:** `cd frontend && pnpm vitest run` (node, seeded `InMemoryEngineDb` or
MSW-mocked BFF). **Arch gate:** `pytest tests/architecture/ -q` + the ts-morph frontend layering
suite. **Persistence probe** (pg seam): on-demand, like `db-persistence-probe.spec`.

---

## Phase 0 — Branch + baseline (no code)

- **T0.1** Branch `feat/coach-v3-durable-engine` off updated `main`; commit the untracked planning
  docs (`coach-v3-durable-progress.{brainstorm,spec,plan,tasks}.md`) + `docs/adr/0038-*` +
  `index.md`/`log.md` entries.
  *Pass:* `git log --oneline -1` on the new branch shows the docs commit; `docs/adr/0038-*` tracked.
- **T0.2** Baseline green BEFORE any edit: `make check` + `pytest tests/architecture/ -q` +
  `cd frontend && pnpm vitest run`. Paste the actual output.
  *Pass:* all green (vitest ts-morph arch-suite 10s-timeout flake: re-run isolated if it trips —
  see memory `frontend-vitest-tsmorph-timeout-artifact`).

---

## Phase G — Server content seed (prerequisite; parallel to F) → FR-G1, G2, G4

> Gates A: a fresh Postgres serves **zero** questions until the reviewed bank is loaded (spec Track-G
> hidden dependency — the 987 items exist ONLY in the in-browser TS seed). The seed is **multi-source
> reconciliation** (review #4): the promoted JSON is **items-only**; the live seed assembles **≥5
> sources** (`composition_engine_browser.ts`). G3 (empty-content guard) is NOT here — it ships
> *with A* (T A.15) so a not-yet-seeded prod degrades honestly.

- **T G.1 (red)** `tests/scripts/test_emit_engine_seed_sql.py`: with a small fixture per source, the
  emitter produces a transactional reconciliation bundle covering **all sources** — `test_item` +
  `skill` + `hint` + `tutorial` + `content_string` + `test_blueprint` — where (a) every insert is
  **`ON CONFLICT … DO UPDATE`** keyed by the table's natural id (NOT `DO NOTHING` — a re-emit of
  changed content must propagate, FR-G2), (b) a row present in pg but dropped from the source is
  **soft-retired** (`reviewed = false`) with **no `DELETE` statement anywhere in the bundle**, and
  (c) the `generated_by` provenance stamp is carried. Watch it fail (no script).
  *Pass:* red for the right reason (ModuleNotFoundError / missing script).
- **T G.2 (green)** `scripts/emit_engine_seed_sql.py` (sibling to `scripts/emit_test_item_bank.py`)
  → emit `frontend/drizzle/seed_engine_content.sql` (applied by the Track-F runner AFTER
  `0000–0004`) from ALL authoritative sources: `test_item` ← `_test_item_bank.ts` (987 items, the
  promoted JSON); `hint` ← `_hint_bank.ts`; `tutorial` + `content_string` ← `seedLessonContent`;
  `skill` ← `seedDevTaxonomy`; `test_blueprint` ← its source. `DO UPDATE` reconciliation +
  **retire-not-delete** (FR-G2 — forced by schema: `attempt.question_id` is `onDelete: "cascade"`,
  `schema.pg.ts:230-231`; a hard DELETE cascades-deletes learner attempt history). Provenance stamp
  satisfies `tests/architecture/test_test_item_provenance_confinement.py`.
  *Pass:* T G.1 green; a re-run emits byte-identical SQL; `make check` green.
- **T G.3 [P]** Row-count evidence (**FR-G1**): emitted upsert count per table == that table's
  source count (987 `test_item` + skill/hint/tutorial/content/blueprint counts read from their
  sources — NOT items-only). **FR-G4** needs no code: assert the bundle touches **no learner write
  table** (`quiz_session`/`attempt`/`skill_state`/`progress_point`).
  *Pass:* per-table counts match; zero statements against learner write tables.

## Phase F — Infra: `DATABASE_URL` + baseline + migration runner (own PR; parallel to G) → FR-F1, F2, F3

> ⚠️ **HIGHEST-RISK TRACK** (plan §3 Track F): the engine schema has **no migration execution path
> today** — `drizzle.config.ts` is threads-only, `drizzle-kit` is not in `package.json`, `0001–0003`
> are hand-authored ALTERs with no runner, and **no migration creates any table** (zero
> `CREATE TABLE`, verified — FR-F2). Binding `DATABASE_URL` also **auto-flips** the thread +
> coach-marker repos to Pg (`server_composition.ts:55`; `marker_repo.ts:14,114`) — FR-F3: the runner
> must cover those tables too, or the ADR-0034 data-stripping hole re-opens.

- **T F.1 [P]** `infra/gcp/cloud-run-frontend.tf`: engine `DATABASE_URL` via Secret Manager,
  **server-side env only** (F-R9 — mirrors `agent-backend-combined`). **FR-F1.** The Terraform bind
  **merges only WITH T F.3's runner wired** (the FR-F3 pairing — bind-without-runner re-opens
  ADR-0034).
  *Pass:* plan review confirms server-side-only secret, no `NEXT_PUBLIC_*` exposure; the PR states
  the bind↔runner pairing. (Infra PR; §8 marks FR-F1 "infra PR".)
- **T F.2 (red→green)** **FR-F2** baseline: `frontend/drizzle/0000_frontend_baseline.sql` — CREATE
  TABLEs for the 12 engine tables **+ `threads`/`thread_messages` + the coach-marker table**
  (FR-F3), generated one-time from `schema.pg.ts` + the thread/marker schemas. **Excludes LangGraph
  checkpoint tables** (the `drizzle.config.ts` invariant). **Red first:** apply `0001` to a fresh
  scratch pg → "relation does not exist" (proves the gap is real). Green: `0000` → `0001–0003`
  apply cleanly.
  *Pass:* fresh pg: `0000→0003` applies; `\d` shows all engine + threads + marker tables;
  checkpoint tables absent.
- **T F.3 (red→green)** **The runner (DECIDED — review #6-B4):**
  `frontend/scripts/migrate_engine.mjs` (node + `pg`, no `drizzle-kit` dep) — applies
  `frontend/drizzle/0*.sql` in lexicographic order, **one transaction per file**, ledgered in a
  `_frontend_migrations` table (filename + applied_at; skip already-applied); then applies
  `seed_*.sql` **every run** (the seed is idempotent `DO UPDATE` reconciliation — ledgering it
  would skip a re-emit and reintroduce the exact FR-G2 drift).
  *Pass:* run twice on a scratch pg → second run applies **zero** numbered migrations (ledger) but
  re-runs the seed; a mid-file failure rolls back that file's transaction only.
- **T F.4** Deploy integration (DECIDED): the runner executes as a **pre-traffic deploy step**
  (deploy recipe / Cloud Build, same `DATABASE_URL` secret) — **NOT at app boot** (a Cloud Run cold
  start must never race a migration).
  *Pass:* deploy dry-run shows the migrate step ordered before traffic cutover.
- **T F.5** Close the ADR-0034 tombstone:
  `tests/architecture/test_coach_marker_durability_tombstone.py` guards "`DATABASE_URL` bound
  without a runner". With T F.3 landed, update/retire it to assert the **built** path, not a
  now-false premise (G8: a removed `def test_*` needs the justification token; whole-file delete
  needs a stub — memory `dev-tier-stack-retired-adr0031`).
  *Pass:* tombstone updated; `pytest tests/architecture/ -q` green with the runner present.

---

## Phase 4 — Migration 0004 + the two new methods (dual-dialect; before A) → §4, FR-A9.1 (DB half)

> `0004` is **two-part**: (a) `quiz_session.current_question_id` served-pointer; (b)
> `attempt.idempotency_key` + partial unique index. This phase ALSO lands the two new `EngineDb`
> methods (#30 `setSessionCurrentQuestion`, #31 `getNewestOpenSession`) and the in-adapter
> idempotent `insertAttempt`, so Phase A implements `HttpEngineDb` against the **final 31-method
> surface**. Parity is non-negotiable (`schema.parity.test.ts` auto-asserts column-name identity).

- **T 4.1 (red)** Add `current_question_id` + `idempotency_key` to **pg only** first; run
  `schema.parity.test.ts` — watch it go **red** (sqlite missing both columns). The red proof that
  parity is enforced. **§4 parity FR.**
  *Pass:* parity test fails naming both missing sqlite columns.
- **T 4.2 (green)** `frontend/drizzle/0004_durable_progress.sql`:
  `ALTER TABLE quiz_session ADD COLUMN current_question_id uuid;` +
  `ALTER TABLE attempt ADD COLUMN idempotency_key uuid;` +
  `CREATE UNIQUE INDEX attempt_idempotency_uq ON attempt (session_id, question_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;` (the `WHERE` lets legacy NULL-key rows coexist).
  Add both columns to `schema.pg.ts` (`uuid(...)`) **and** `schema.sqlite.ts` (`text(...)`, NOT
  `uuid` — id-row rule) + the same partial unique index in both (mirror `hint_*_uq`,
  `schema.pg.ts:130-133`).
  *Pass:* `schema.parity.test.ts` green; T 4.1 now passes.
- **T 4.3 (green)** Wire entities (`wire/engine_entities.ts`): add
  `current_question_id: z.string().nullable()` to `QuizSession` (`:210-226`); add
  `idempotency_key: z.string().nullable()` to `Attempt` and make it **required on `AttemptInput`**
  (`= Attempt.omit({id, created_at}).required({idempotency_key: true})` or a dedicated object —
  keep the omit-precedent readable). `id`/`created_at` stay engine-assigned.
  *Pass:* tsc green; `AttemptInput` requires the key (compile-time forcing function for
  T A.12 / T B.1).
- **T 4.4 (red→green)** The two new methods, in **all** impls (`drizzle_engine_db.ts`,
  `in_memory_engine_db.ts`, sqlite path): **#30** `setSessionCurrentQuestion(sessionId,
  questionId | null)` (write, on serve — FR-B3a); **#31** `getNewestOpenSession(subject,
  learnerId)` (read — newest `ended_at IS NULL` row; review #6-B2: `listClosedSessionsByLearner`
  **excludes** open rows, `engine_db.ts:113-114`, so no existing method finds a resumable session).
  Pointer surfaces as a **field** on `getSession`/session-returning reads.
  *Pass:* pointer round-trips; `getNewestOpenSession` returns the newest open session and never a
  closed one; green on both dialects.
- **T 4.5 (red→green)** **FR-A9.1 (DB half) — in-adapter idempotent insert:** `insertAttempt` does
  `.onConflictDoNothing({ target: attempt_idempotency_uq })` and returns a **typed result**
  (`inserted` | `already-existed`, re-selecting the stored row on conflict). Signature change
  propagates to all impls; `drizzle_attempt_repo.record` (`:56-72`) passes the key straight through
  (orthogonal to the monotonic `created_at`). **Why in-adapter, not the handler:** `pgEngineDb`
  wraps every op's error as opaque `EngineRepoError` (`drizzle_engine_db.ts:284-286`) — a handler
  `catch` can never see SQLSTATE 23505; precedent `upsertSkillState:660-686`.
  *Pass:* same-key double insert → **ONE** row + typed already-existed; new key → new row. Both
  dialects.

---

## Phase A — HttpEngineDb + BFF /api/engine/* (the atomic swap; +G3 guard) → FR-A1..A9, G3

> **A is all-or-nothing** (FR-A4): one shared `db` builds every `useEngine()` screen's bag, so the
> swap puts dashboard/summary/skill/coach on the network at once. The full **31-method surface per
> the §2 disposition** (coarse carrier | fine-grained route | server-only typed throw) + the coarse
> endpoints + the **coarse client seam** are mandatory, not optional. **Failure-path tests FIRST.**

### A-auth / A-seam (failure paths first)

- **T A.1 (red→green)** **FR-A1**: no WorkOS session → `401`, **no DB read/write**. Red first (no
  handler).
  *Pass:* 401 + a spy proving `pgEngineDb` was never called. In gate.
- **T A.2 (red→green)** **FR-A2**: a client body naming `learnerId` is ignored; the handler derives
  it from the server session (`resolve_learn_identity.ts`).
  *Pass:* handler uses the session-derived id even when the body lies. In gate.
- **T A.3 (red→green)** **FR-A2a mechanism — `requireOwnedSession(engineDb, sessionId, learnerId)`**
  (review #6): the session-scoped `EngineDb` methods take only `sessionId`, so scoping is a
  route-family helper — `getSession(sessionId)` → compare `session.learner_id` to the
  server-derived id → mismatch/absent = `404` **before any dependent read/write runs**. Used by
  `quiz/bootstrap`, `attempt`, `next`, `session/current`, `session/close`, `summary`. Learner-keyed
  methods (`listSkillState`, `listMisses`, `listProgressPoints`, `accuracyRowsBySkill`,
  `getNewestOpenSession`) receive the derived `learnerId` directly — never an id from the request.
  *Pass:* learner A guessing B's session id → 404/empty on **every** session-scoped route, with a
  spy proving no dependent query ran. In gate.
- **T A.4 (red→green)** **FR-A3**: unset engine `DATABASE_URL` → typed `EngineRepoError`, **no**
  silent `InMemoryEngineDb` fallback. `selectEngineDb(env)` diverges from the marker precedent on
  the else-branch (throw, not in-memory).
  *Pass:* unset URL throws typed; no in-memory path. In gate.

### A-surface (the seam + composition)

- **T A.5 (red→green)** `http_engine_db.ts` implements the **full 31 methods** per the §2
  disposition: fetch calls for coarse-carried + fine-grained rows; a **typed
  `EngineRepoError("server-only method")` throw** for the 4 content writes
  (`insertQuestion`/`insertHint`/`insertTestItem`/`insertTestBlueprint` — never a silent success).
  Returns `wire/engine_entities` shapes only (A4/F-R8). **The FR-A4 conformance test asserts the
  disposition table is TOTAL** — every interface method resolves to a route or a typed server-only
  throw. It proves **behavior**, not just TypeScript shape.
  *Pass:* conformance green over all 31; the 4 server-only methods throw typed. In gate.
- **T A.6 (green)** `server_composition.ts`: add a **standalone `engineDb(): EngineDb`** seam
  function mirroring `coachMarkerRepo()` (`:71-77`) — memoized, env-reading, called directly by the
  route handlers; **NOT** a param in `serverPortBag()`/`buildAdapters`. Calls `selectEngineDb(env)`
  (T A.4) → `pgEngineDb(url)`. C1/C2 hold.
  *Pass:* arch layering suite green (only the seam names the concrete DB); handlers call
  `engineDb()`.
- **T A.7 (green)** `composition_engine_browser.ts`: swap the one `db` from `new InMemoryEngineDb()`
  (`:96`) to `new HttpEngineDb(...)` and drop `seedTestItemBank(db)` (`:265` — now server-seeded
  via G). **This single line is the atomic swap.** Behind a **flag** (§6 cutover — shadow → canary,
  coach-v3 flag precedent).
  *Pass:* flag on → `HttpEngineDb`; flag off → `InMemoryEngineDb` (coexist during validation).

### A-endpoints (coarse; guards FR-A4 chattiness)

- **T A.8 (red→green)** Coarse write/hot-path handlers + `wire/` shapes (snake_case, no SDK types):
  `POST /session/open` (the open-write, split so bootstrap stays a pure read),
  `GET /quiz/bootstrap?session=<id>` (pure read: session + item + hints), `POST /attempt`,
  `POST /skill-state`, `GET /next`, `POST /session/current` (served pointer, FR-B3a),
  `POST /session/close` — **server computes the tally: unique-`first_try` numerator /
  unique-resolved denominator, dedup by `question_id`, ignores any client tally** (FR-B10/§6) —
  and `GET /session/active` (backed by **#31 `getNewestOpenSession`** + stored pointer + the same
  server-computed running score).
  *Pass:* each resolves via `pgEngineDb`; bootstrap does no write; `session/current` is the only
  serve-pointer writer; close/active tallies are server-side. In gate.
- **T A.9 (red→green)** **§7 coarse-read** endpoints, one call each (else the atomic swap regresses
  their latency): `GET /dashboard` (5 reads → 1), `GET /summary?session=<id>` (6 reads → 1),
  `GET /skill/[id]` (**5 + N+1** → 1; folds `skillTaxonomy.list` `:47` + 4 parallel `:51-56` + the
  miss-question bodies `:65-66` server-side).
  *Pass:* dashboard/summary/skill each resolve in ONE BFF call (test asserts call count == 1). In
  gate.
- **T A.10 (green)** Fine-grained routes for the disposition's fine-grained rows — `listSkillIds`,
  `getSkillByKey`, `listContentStrings`, `getTestBlueprint`, `listProgressPoints`,
  `listReviewedHints`, `listReviewedTestItems`, `getQuestion`, `getSkillState`,
  `getContentString`, `getTutorial`, + the session-list reads where not coarse-carried. **NO route
  exists for the 4 server-only content writes** (an authenticated-learner content-write endpoint
  would let any learner mutate the bank — FR-A4).
  *Pass:* every fine-grained method callable; a request to any content-write path → 404 (no
  handler); T A.5's typed throw covers the client side. In gate.
- **T A.11 (red→green)** **The coarse client/loader seam + rewiring (FR-A6 revised — review #1):**
  add an `EngineClient` (or per-screen coarse loaders) — `loadDashboard()`,
  `loadSummary(sessionId)`, `loadSkillDetail(skillId)`, `nextItem(sessionId, …)` — each ONE fetch
  to its coarse endpoint, returning `wire/` shapes. Rewire the 3 heavy read hooks —
  `use_dashboard.ts` (`:141-157`), `use_summary.ts` (`:145-153`), `use_skill_detail.ts`
  (`:47`,`:51-56`,`:65-66`) — and the **scheduler entry**: `openQuizItem` (`use_quiz.ts:183-185`)
  calls `GET /next` instead of running `Scheduler.next()` in-browser (the pick moves server-side —
  prerequisite for FR-E eligibility and FR-B9 served-set).
  *Pass:* the 3 hooks + scheduler entry each make ONE loader call (no per-repo fan-out);
  `EngineDb` **write** consumers unchanged (quiz submit path untouched). In gate.

### A-durability semantics (idempotency + retry + optimistic)

- **T A.12 (red→green)** **FR-A9.1 (client + handler halves):** `use_quiz.ts` stamps **one
  `idempotency_key` (UUID) per answer action** (at grade time, not per HTTP attempt) and resends it
  verbatim on retry; a coached retry is a new answer action → new key. The `POST /attempt` handler
  is **thin**: returns the stored `Attempt` from T 4.5's typed result (idempotent 200 whether
  inserted or already-existed) — **no PG-error string-matching** (the adapter already resolved the
  conflict).
  *Pass:* retried same-key POST → 1 row, score not inflated; coached retry → new row. In gate.
- **T A.13 (red→green)** **FR-A9.2** retry/timeout: `HttpEngineDb` retries **idempotent reads**
  with bounded backoff on 5xx/network; **non-idempotent write** fail surfaces per FR-A8 (no silent
  drop). The served-pointer write is the one fire-and-forget exception (degrades to FR-B8).
  *Pass:* transient 5xx read → retried; write fail → error, not dropped. In gate.
- **T A.14 (red→green)** **FR-A5 / A7 / A8**: submit persists the attempt before the interaction
  completes (A5); verdict shown immediately from the deterministic client grader (A7, optimistic);
  write-fail after the optimistic verdict → error state, **no advance** (A8) — hold behind an error
  banner, no rollback-to-unanswered (§6).
  *Pass:* A5 row persisted; A7 verdict instant; A8 write-fail blocks advance. In gate.
- **T A.15 (red→green)** **FR-G3** empty-content guard (ships **with A**): empty content tables →
  explicit "no content available" state, not a broken quiz — de-risks F+G→A (A never ships a broken
  surface even if the seed slips).
  *Pass:* empty pg → "no content" UI, no throw. In gate.

---

## Phase C — Bounded-30 + fresh restart (first in the B/C/E group) → FR-C1..C6

> C is first because auto-close **produces** the completed sessions B must-not-resume (FR-B7) and D
> summarizes. Close-trigger owner: a **page Effect keyed on `progressVm.complete`**, not
> `runQuizSubmit` (plan §3 Track C — `progressVm.complete` at `quiz/page.tsx:585` flips only on the
> 30th **resolution**, already encoding the FR-C1a timing).

- **T C.1 (red→green)** **FR-C1 / C1a**: on `progressVm.complete` becoming true (30th item
  **resolves**, not first-grades) → in one Effect: persist the resolving attempt →
  `POST /session/close` (**server computes the tally** — first_try-only unique semantics, dedup by
  `question_id`, client tally ignored) → navigate to summary. A wrong first answer on Q30 stays in
  the coached loop and closes only on resolution.
  *Pass:* 30th resolves → auto persist+close+route; wrong-Q30 stays coached until resolution. In
  gate.
- **T C.2 (red→green)** **FR-C2**: a session at `target_count`, closed → **completed**; no Q31
  served.
  *Pass:* no 31st question. In gate.
- **T C.3 (green)** **FR-C3**: remove the "Keep practising"/relabel + `QuizDoneBanner` continuation
  in the reviewing branch (`quiz/page.tsx:598-629`, `:751-752`). 30 is a hard stop.
  *Pass:* no "Keep practising" past target. In gate.
- **T C.4 [P] (red→green)** **FR-C4**: new practice after a completed session → **fresh** session
  at Q1 (new `quiz_session` row), never resume the completed one.
  *Pass:* fresh Q1 session. In gate.
- **T C.5 (red→green)** **FR-C5**: pool exhausted before target → graceful close to summary at the
  count reached (convert the `openQuizItem` throws at `use_quiz.ts:219,242,269`).
  *Pass:* exhausted pool → summary, no raw throw. In gate.
- **T C.6 [P] (green)** **FR-C6** scope guard: `target_count = null` still valid for non-default
  callers (computed `mode=review`, drills).
  *Pass:* endless session still opens for a null-target caller. In gate.

---

## Phase B — Cross-device resume (needs A; after C) → FR-B1..B10

> `resumeQuizSession` **signature change** (plan §3 Track B): today `(ports, {sessionId,
> questionId})` with questionId from caller RAM (`readActiveQuiz()`). Post-swap the caller passes
> **only `sessionId`** (or nothing — the server picks the newest open session) and the question
> comes from the server `GET /session/active` response; the caller **stops reading
> `readActiveQuiz()` for position**.

- **T B.1 (red→green)** **FR-B3a** (the load-bearing write): on entering `answering`, durably
  record the served question via `POST /session/current` (was RAM `ActiveQuizPointer.questionId`,
  `quiz/page.tsx:284-314`). Serve-time, not submit-time. Body carries no learnerId (FR-A2);
  ownership via `requireOwnedSession` (T A.3).
  *Pass:* open Q4, no submit → `current_question_id == Q4` durably. In gate.
- **T B.2 (red→green)** **FR-B3a-nonblock**: the pointer write is **fire-and-forget** — its failure
  does NOT block the serve; worst case is a stale resume position, never a broken serve (§7 NFR).
  *Pass:* forced pointer-write failure → question still renders. In gate.
- **T B.3 (red→green)** **FR-B1 / B3 / B3b**: mount with an open session → `GET /session/active`
  (backed by **#31 `getNewestOpenSession`**) returns the stored `current_question_id` + the
  server-computed running score; resume lands on the stored question, **not** a scheduler re-pick.
  `resumeQuizSession` takes the question from the server response (signature change above).
  *Pass:* resume lands on the stored question, not a re-derived one. In gate.
- **T B.4 (red→green)** **FR-B3c**: pointer advances to the newly served question on next serve;
  cleared (NULL) on close.
  *Pass:* pointer tracks serves; NULL after close. In gate.
- **T B.5 (red→green)** **FR-B3-feedback / pointer-attempt disagreement** (§6): resume **advances**
  (not re-show) for **any recorded attempt** — (a) first-try correct [resolving], AND (b) first-try
  wrong still in the coached loop [**non-resolving** attempt row]; only a **zero-attempt** served
  question is re-shown. Predicate = "any attempt row exists", NOT "a resolving attempt exists".
  *Pass:* both (a) and (b) advance; zero-attempt re-shows. In gate.
- **T B.6 (red→green)** **FR-B8** (NULL-pointer fallback): NULL `current_question_id` → re-derive
  via a scheduler pick **scoped by FR-B9 (exclude answered) + FR-E1 (content-fresh)**; the pick
  never returns an already-answered question; zero attempts → first scheduled question. FR-B3b is
  NOT violated (it forbids re-deriving only when a *non-NULL* pointer exists).
  *Pass:* NULL pointer → scoped scheduler pick, never an answered question. In gate.
- **T B.7 (red→green)** **FR-B9** (served-set — **owned by the `/next` handler server-side**, §6;
  supersedes the old client-side `openQuizItem→servedQuestionIds→Scheduler.next` path the T A.11
  rewiring replaced): the handler reconstructs the served set from the session id (`NOT IN`
  attempted) at pick time; **the client never materializes a served-set**, so resume inherits
  no-repeat for free. Q1–Q29 answered → resume → next ∉ {Q1..Q29}.
  *Pass:* a resumed session never re-serves an answered question. In gate.
- **T B.8 (red→green)** **FR-B10** (running score — **commit-first semantics, corrected review
  #3**): `GET /session/active` computes **server-side**: numerator = unique questions resolved
  `first_try`; denominator = unique resolved questions. A **coached-correct does NOT bump the
  numerator** (matches the live reducer exactly — `quiz_screen_reducer.ts:434`:
  `bumpCorrect = resolution === "first_try"`). Session row score is 0 while open
  (`schema.pg.ts:209-210`); never client-re-tallied; `session/close` computes the same (T A.8).
  *Pass:* resumed score == live commit-first tally for the same attempt history (incl. a
  coached-correct case that must NOT bump it); no client re-count. In gate.
- **T B.9 [P] (red→green)** **FR-B2**: resumable = **newest** `ended_at IS NULL`, no time expiry;
  an older open session still resumes.
  *Pass:* newest open chosen. In gate.
- **T B.10 [P] (red→green)** **FR-B5**: stored question id no longer resolves → **fresh** session,
  no fabricated progress (covers the served-pointer too).
  *Pass:* stale id → fresh session, no phantom score. In gate.
- **T B.11 [P] (red→green)** **FR-B6**: `?mode=review` / `?focus=<skill>` → the requested fresh
  session, not resume.
  *Pass:* deep-link honored as fresh. In gate.
- **T B.12 [P] (green)** **FR-B7**: a **completed** session is never a resume candidate
  (`getNewestOpenSession` only sees `ended_at IS NULL`).
  *Pass:* completed session skipped by the resume selector. In gate.
- **T B.13 (probe)** **FR-B4** (cross-device): resume reads by learnerId, device-agnostic — the
  full-stack persistence probe (seeded pg): device-2 resumes device-1's open session.
  *Pass:* on-demand probe output pasted. §8 marks L2 on-demand.

---

## Phase E — Content-fresh eligibility (needs A + G) → FR-E1..E5

> Layering, NOT replacement (plan §3 Track E): eligibility is a **prefer/filter layer** on the same
> `excludeIds` channel the scheduler already threads (`fsrs_scheduler.ts:159-182`); FSRS still picks
> the weakest/most-due skill. **Runs server-side in the `/next` handler** (the T A.11 scheduler
> rewiring is the prerequisite — a client-side already-correct set can't be durably computed).
> **E is inert until A + G land** (FR-E4 hard dependency).

- **T E.1 (red→green)** **FR-E4** projection: a durable cross-session read projection over
  `attempt` — the set of question ids whose **latest** attempt (by `created_at`) is
  `correct===true`, per-learner (inverse of `listMisses`). No `skill_state` write. Computed
  server-side in the `/next` handler.
  *Pass:* projection returns already-correct ids; no write path touched. In gate.
- **T E.2 (red→green)** **FR-E1 / E1a**: extend the scheduler's exclude set with the E4
  already-correct ids so the pick **prefers** not-yet-correct items; layered over FSRS + the
  within-session no-repeat (both still apply).
  *Pass:* a question answered-correct last session is excluded from the preferred pool; FSRS skill
  pick + within-session no-repeat unchanged. In gate.
- **T E.3 [P] (red→green)** **FR-E2**: missed questions (latest attempt not `correct===true` —
  incorrect OR walked-through) **stay eligible**.
  *Pass:* a walked-through / incorrect question remains selectable. In gate.
- **T E.4 [P] (red→green)** **FR-E1 coached-vs-walked edge**: coached-correct (`correct=true,
  resolution=coached`) leaves the preferred pool; walked-through (`correct=false`) stays — the
  single `correct===true` predicate handles both, no resolution-aware special case.
  *Pass:* coached-correct excluded, walked-through kept, by the one predicate. In gate.
- **T E.5 (red→green)** **FR-E3** fallback: not-yet-correct pool exhausted → normal FSRS full-bank
  adaptive (allow correctly-answered back in); no new ordering.
  *Pass:* empty preferred pool → full-bank FSRS. In gate.
- **T E.6 [P] (green)** **FR-E5**: `mode=review` (serve exact past misses) unchanged; eligibility
  applies to the default adaptive mode only.
  *Pass:* review mode still serves exact misses. In gate.

---

## Phase D — Enriched summary (needs C + A) → FR-D1..D5

> Summary partly exists (`session_summary_vm.ts`, `SummaryView`). NEW = a per-question misses list
> + a strong/weak per-skill panel. Rows come from the coarse `GET /summary` response (T A.9/A.11) —
> **FR-D3 scope (review #6): the panels are client PROJECTION of server-supplied attempt rows
> (permitted); only the headline score is server-authoritative** (FR-B10/close). Reuse
> `countSessionOutcomes` group-by-question (§6 dedup).

- **T D.1 (red→green)** **FR-D1 / D1a**: misses list = each question in **this session**
  (`listSessionAttempts` rows, NOT global `misses()`) whose resolving attempt was incorrect OR
  walked-through, identifiable (stem/skill). Walked-through counts as a miss (D1a) even though it
  resolves.
  *Pass:* this-session incorrect + walked-through appear; a later-cleared miss still shows in its
  own session's summary. In gate.
- **T D.2 (red→green)** **FR-D2 / D3**: strong/weak panel projected from **this session's**
  attempts grouped by the question's `skill_id` (correct/total per skill) — **not** the last-N
  `accuracyBySkill` API (untouched for skill-detail). The headline score renders the
  server-supplied value; the panels project the server-supplied rows (projection ≠ re-tally).
  *Pass:* panel matches this-session per-skill tally; headline == server value; `accuracyBySkill`
  untouched. In gate.
- **T D.3 [P] (red→green)** **FR-D4**: zero-miss completed session → explicit "clean sweep" empty
  state, not a broken/absent section.
  *Pass:* zero-miss → clean-sweep state. In gate.
- **T D.4 [P] (red→green)** **FR-D5**: a skill with no on-skill attempts is **omitted** from
  strong/weak, never fabricated as 0% (AP-6).
  *Pass:* no-attempt skill absent, not 0%. In gate.

---

## Phase Z — Persistence probe + gate close → §9 Definition of Done

- **T Z.1 (probe)** End-to-end against a fresh pg (on-demand, like `db-persistence-probe.spec`):
  **(a)** `migrate_engine.mjs` runs the full inventory — `0000` baseline (engine + threads +
  marker) → `0001–0004` → seed reconciliation — on an empty database; **(b)** per-table seed counts
  match sources (FR-G1); **(c)** a re-emit with one CHANGED row → the stored row is UPDATED, and a
  DROPPED row → `reviewed=false` with its attempt history intact (FR-G2 retire-not-delete);
  **(d)** submit → attempt row in pg (FR-A5); **(e)** cross-device resume (FR-B4, T B.13).
  *Pass:* probe output pasted verbatim; **engine persistence proven end-to-end at least once**
  (spec DoD — currently unproven).
- **T Z.2** Full gate: `make check` + `pytest tests/architecture/ -q` +
  `cd frontend && pnpm vitest run` all green (F-R9, F-R4, A4/F-R8, C1/C2,
  `schema.parity.test.ts`, the ADR-0034 tombstone as updated by T F.5).
  *Pass:* all green; actual output pasted (not summarized — spec DoD).
- **T Z.3** DoD close-out: every FR has a test seen to fail first (red/green); ADR-0038 linked from
  the code seams (`http_engine_db.ts`, `server_composition.ts engineDb()`); `index.md`/`log.md`
  current.
  *Pass:* §9 checklist fully ticked; ADR ratchet (`test_adr_ratchet.py`) green (0038 present for
  the `/api/engine/*` + `http_engine_db.ts` seam).

---

## Phase R — Reconvergence (Stage-5 replan, 2026-07-23) → code-review findings 1–9

> **Trigger:** the end-to-end code review (`coach-v3-end-to-end-code-review.canvas.tsx`, verdict
> REJECT) found 2 Critical, 4 High, 3 Medium findings across the shipped phases. **Routing:** 2
> findings (5, 7) are minor scope additions → spec updated first (FR-G2a + §6 per-question
> resolution-order tie-break, see `coach-v3-durable-progress.spec.md`); the other 7 are
> implementation/test gaps against existing FRs. **This phase is append-only** — the existing
> Phase 0/G/F/4/A/B/C/D/E/Z tasks stay as committed; Phase R layers fixes on top. **Red/green TDD
> per task.** Ordered by merge risk (Critical → High → Medium), matching the canvas's recommended
> convergence order. Each task ends by checking its own pass/fail criterion.

- **T R.1 (red→green) [CRITICAL] — Close the EngineDb dispatcher IDOR (finding 1; FR-A2a, FR-A2).**
  `frontend/app/api/engine/db/[method]/route.ts` currently substitutes learner IDs for only seven
  read methods and never calls `requireOwnedSession`, so one learner can target another's
  session/state. Centralize per-method authorization in the dispatcher: (a) force every embedded
  `learner_id` field to the server-derived id (ignore any client-supplied one); (b) for every
  session-scoped method (`insertSession`'s `learner_id`, `insertAttempt`'s session→learner,
  `upsertSkillState`, `setSessionCurrentQuestion`, `getSession`, `listSessionAttempts`,
  `patchSessionClose`, etc.), resolve the session id → load the session → `requireOwnedSession`
  before dispatch; (c) add cross-learner tests for **every** session-scoped method (learner A
  guessing B's session id → 404/empty, with a spy proving no dependent query ran).
  *Pass:* cross-learner isolation holds on all session-scoped dispatcher methods; spy proves no
  dependent query on mismatch. In gate. **DONE 2026-07-23** — `frontend/app/api/engine/db/[method]/route.ts`
  forces the server-derived `learnerId` (`learnerIdFromClaim`, line 74) and calls
  `requireOwnedSession(db, sessionId, learnerId)` before every session-scoped dispatch (line 119);
  cross-learner isolation covered by `frontend/app/api/engine/db/[method]/route.test.ts`.

- **T R.2 (red→green) [CRITICAL] — Make Cloud SQL migration/runtime connectivity deployable
  (finding 2; FR-F1, FR-F3).** `scripts/deploy_gcp.sh` passes a `/cloudsql` Unix-socket DSN to
  Node without starting Cloud SQL Proxy, and `infra/gcp/cloud-run-frontend.tf` lacks the socket
  volume/mount + `cloudsql.client` grant. (a) Run `migrate_engine.mjs` through Cloud SQL Proxy or
  a connector-enabled job (the `database-url` secret must be `postgresql://…` for `pg`, not
  `postgresql+asyncpg://…`); (b) add the frontend Cloud Run socket volume/mount + least-privilege
  `cloudsql.client` IAM; (c) deploy dry-run shows the migrate step ordered before traffic cutover
  AND able to reach the database.
  *Pass:* migrate step connects + applies on a staging deploy; runtime opens the DB. Infra PR.
  **DONE 2026-07-23** — `infra/gcp/cloud-run-frontend.tf` adds the Cloud SQL socket volume/mount +
  least-privilege `cloudsql.client` IAM; `scripts/deploy_gcp.sh` runs `migrate_engine.mjs` through
  `cloud-sql-proxy` with a `postgresql://…` URL normalized by `frontend/lib/adapters/db/node_pg_url.ts`
  (`toNodePgConnectionString`); guarded by `tests/architecture/test_frontend_cloudsql_connectivity.py`.

- **T R.3 (red→green) [HIGH] — Enforce `target_count` server-side; prevent Q31 (finding 3; FR-C2).**
  If item 30 resolves but close fails or the page reloads first, the open session resumes through
  `/next` and neither resume nor `/next` compares the server tally with `target_count`, so Q31 can
  be shown and submitted. (a) In `/next`: if the session's server-computed `score_total >=
  target_count` (and `target_count != null`), return a "session complete" signal (no item) instead
  of a next question; (b) in durable resume (`GET /session/active`): same boundary check — a
  session at target is treated as complete (close it / route to summary), never resumed into a
  31st serve; (c) add a page-level final guard. Test an open session whose server `score_total`
  already equals `target_count`.
  *Pass:* no Q31 served after a failed close or reload; boundary enforced in both `/next` and
  resume. In gate. **DONE 2026-07-23** — `frontend/app/api/engine/next/route.ts` returns a
  `session_complete` signal (no item) when `isAtTargetCount(session.target_count, tally.score_total)`
  (lines 16,40,43); `frontend/lib/bff/engine_tally.ts` adds `isAtTargetCount` + `commitFirstTally`;
  `frontend/components/quiz/use_quiz.ts` adds `QuizResumeExhaustedError` + a `closingSessionRef`
  page-level guard so a failed close / reload cannot serve Q31.

- **T R.4 (red→green) [HIGH] — Seed generation fails closed on empty/drifted sources (finding 5;
  FR-G2a — new).** `scripts/emit_engine_seed_sql.py` currently emits a blanket `reviewed=false`
  update when a source is empty, retiring the entire bank without destructive intent. (a) The
  emitter tracks a per-source row-count ratchet (ledgered from the previous reconciliation); (b)
  if a source is empty OR its count regresses below the ledgered value, abort the transaction
  closed — emit NO `reviewed=false` blanket update — and surface a typed error; (c) an explicit
  `--force-empty-<source>` operator flag is the only override (documented destructive intent).
  *Pass:* empty/regressed source → abort, no blanket retire; `--force-empty` overrides; ratchet
  test green. In gate. **DONE 2026-07-23** — `scripts/emit_engine_seed_sql.py` tracks a per-source
  row-count ratchet against `frontend/drizzle/seed_engine_content.counts.json` and aborts closed
  (typed `SeedSourceFailClosedError`, no blanket `reviewed=false`) on empty/regression unless
  `--force-empty-<source>` is passed; `frontend/lib/adapters/engine/_session_policy_seed.ts`
  carries the seed-source policy.

- **T R.5 (red→green) [HIGH] — Wire the durable-engine flag into the production bundle (finding 6;
  FR-A4, §6 cutover).** `NEXT_PUBLIC_FF_DURABLE_ENGINE` is build-time but the Docker build and
  Terraform don't provide it, so the deployed browser stays on `InMemoryEngineDb`. (a) Add the
  flag as a Docker build arg + Terraform deployment var (build-time, since `NEXT_PUBLIC_*` is
  inlined at build); OR (b) document the intentional OFF rollout and build a dedicated flag-on
  image for the full-stack gate. Setting the var only in a remote Playwright command cannot
  change the compiled bundle — that path is rejected.
  *Pass:* deployed bundle honors the flag; flag-on build reaches `HttpEngineDb`. Infra/build PR.
  **DONE 2026-07-23** — `frontend/Dockerfile.frontend` accepts `NEXT_PUBLIC_FF_DURABLE_ENGINE` as a
  build-arg; `infra/gcp/{cloud-run-frontend.tf,variables.tf,data.tf,terraform.tfvars.example}` wire
  `enable_durable_engine` → the build-arg; `infra/gcp/policies/cloud_run.rego` admits the var;
  `tests/architecture/test_durable_engine_build_flag.py` enforces the Docker↔Terraform pairing.

- **T R.6 (red→green) [HIGH] — Replace Phase Z's DB-only claim with a passing authenticated
  full-stack probe (finding 4; DoD §9).** `probe_engine_persistence.mjs` steps d/e use raw SQL
  INSERT/SELECT, bypassing `HttpEngineDb`, BFF auth, ownership, and adapter idempotency; the
  Playwright companion has no pasted successful run and can false-pass when only the session id
  changes. (a) Rewrite steps d/e to go through `HttpEngineDb` + BFF + auth cookie (or move the
  proof entirely into the Playwright `engine-persistence-probe.spec.ts`); (b) actually run the
  Playwright spec against a seeded pg + authenticated browser and paste the verbatim output; (c)
  the spec must assert the attempt is listable by the server AND a second browser context (shared
  auth) resumes the same learner's open session. Until green, the DoD "end-to-end persistence"
  tick stays conditional (§9.2).
  *Pass:* authenticated full-stack submit + cross-context resume run pasted verbatim; the DoD
  conditional tick is re-ticked. On-demand (L2). **DONE 2026-07-23** — see spec §9.3.

- **T R.7 (red→green) [MEDIUM] — Unify per-question dedup semantics (finding 7; §6 tie-break —
  clarified).** The headline tally keeps the first resolving row while summary outcomes/panels
  keep the latest; same-`created_at` rows are ambiguous in Postgres. Extract ONE
  `resolvingAttemptForQuestion(attempts)` helper (greatest `created_at`, ties by greatest `id`)
  and use it in `lib/bff/engine_tally.ts`, `lib/translators/session_summary_vm.ts`, misses, and
  `lib/bff/engine_eligibility.ts` (`projectAlreadyCorrectQuestionIds`). Add a same-timestamp
  tie test proving all four consumers agree.
  *Pass:* tally/summary/misses/eligibility agree on a same-`created_at` pair; one helper, no
  per-consumer divergence. In gate. **DONE 2026-07-23** — `lib/translators/resolving_attempt.ts`
  shared by tally / summary outcomes / session misses / eligibility; cross-consumer same-ts
  tie test in `resolving_attempt.test.ts`.

- **T R.8 (red→green) [MEDIUM] — Extract the 4 duplicated seed sources from canonical TS modules
  (finding 8; FR-G1).** `scripts/emit_engine_seed_sql.py` copies skills/tutorials/content
  strings/blueprints into Python constants, so source changes silently diverge between in-browser
  and Postgres content. (a) Extract from the canonical TS modules (`seedDevTaxonomy`,
  `seedLessonContent`, blueprint source) at emit time, OR (b) add an architecture test enforcing
  exact parity (counts + natural-id sets) between the Python constants and the TS sources.
  *Pass:* no silent drift; either single-source-of-truth extraction or a parity gate that fails
  on divergence. In gate. **DONE 2026-07-23** — shared JSON under
  `frontend/lib/adapters/engine/seed_sources/` loaded by the emitter defaults and by
  `_dev_seed.ts` / `_lesson_seed.ts` / `_session_policy_seed.ts` / `_blueprint_seed.ts`;
  gate `tests/architecture/test_engine_seed_source_parity.py`.

- **T R.9 (red→green) [MEDIUM] — Add focused integration tests for core production seams (finding
  9; §8).** The green suite does not exercise dispatcher ownership (covered by T R.1's tests),
  close-route tally + pointer clearing, coarse summary hydration, migration replay/rollback
  ledger behavior, or partial-index `insertAttempt` through real Postgres. Add: (a) close-route
  tally + `current_question_id` NULL-on-close test; (b) coarse `GET /summary` hydration test; (c)
  `migrate_engine.mjs` replay (second run applies zero numbered, re-runs seed) + mid-file rollback
  test on scratch pg; (d) same-key `insertAttempt` through real Postgres → one row, typed
  already-existed.
  *Pass:* each integration test green on scratch pg / BFF. In gate (a–c); on-demand (d, scratch pg).
  **DONE 2026-07-23** — (a) `session/close/route.test.ts` (server `commitFirstTally` +
  `setSessionCurrentQuestion(..., null)`); (b) `summary/route.test.ts` (coarse bag, each
  read once); (c) `migrate_engine.integration.test.ts` (replay skip + mid-file ROLLBACK on
  scratch pg); (d) `pg_insert_attempt.integration.test.ts` (`ENGINE_PG_INTEGRATION=1`);
  gate `tests/architecture/test_durable_engine_integration_seams.py`. `migrate_engine.mjs`
  exports `runMigrate` + `ENGINE_DRIZZLE_DIR` for fixture dirs.

- **T R.10a (red→green) — Repair the adapter conformance catalogue (Stage-4 finding; R.10 decomposition).**
  `frontend/tests/architecture/test_adapter_conformance.test.ts` flags
  `frontend/lib/adapters/db/node_pg_url.ts` as an unmapped orphan (not in `PAIRS`, not in the
  intentional-omission list). `node_pg_url.ts` is a pure URL-normalization utility (no port
  interface, like the existing `pg_thread_repo.ts` factory omission) — add it to the intentional
  omission list with its `node_pg_url.test.ts` coverage rationale. No new abstraction, no port pair.
  *Pass:* `test_adapter_conformance.test.ts` green; the orphan list documents the omission. In gate.
  **DONE 2026-07-23** — added `lib/adapters/db/node_pg_url.ts` to the intentional-omission list in
  `frontend/tests/architecture/test_adapter_conformance.test.ts` (pure URL-normalization utility,
  no port interface; covered by `node_pg_url.test.ts`). Red first (orphan reported), then green
  (32/32 passed).

- **T R.11 (red→green) [HIGH] — Align `/next` + `listAlreadyCorrectQuestionIds` with the §6 tie-break (subagent finding 1; FR-E1, §6).**
  T R.7 unified the resolving-attempt order for tally/summary/misses/eligibility in TS, but the
  production `/next` path still selects the "latest attempt" via `created_at`-only SQL, so a
  same-millisecond concurrent-device pair is ambiguous on the hot path. (a) Make the
  already-correct projection (`listAlreadyCorrectQuestionIds` / the eligibility SQL) resolve per
  question by greatest `created_at`, ties broken by greatest `id` — the same order
  `resolvingAttemptForQuestion` defines; (b) add a same-timestamp tie test proving `/next`'s
  eligibility agrees with the tally/summary/misses consumers.
  *Pass:* `/next` eligibility uses the §6 order; same-ts tie agrees across all four consumers. In gate.
  **DONE 2026-07-23** — added the `id` tie-break to the `NOT EXISTS` predicates in
  `drizzle_engine_db.ts` `listAlreadyCorrectQuestionIds` + `listMisses`
  (`later.created_at > … OR (later.created_at = … AND later.id > …)`); the in-memory twin's
  `compareAttemptsNewestFirst` now tie-breaks by greatest `id` (removed the dead insertion-order
  `attemptSeq`); `durable_progress_methods.test.ts` proves `listAlreadyCorrectQuestionIds` +
  `listMisses` agree with `projectAlreadyCorrectQuestionIds` on a same-ms tie; corrected the
  `engine_repos.test.ts` assertion (§6 greatest-id order, not newest-inserted). 34 files / 261 tests
  green; tsc clean.

- **T R.12 (red→green) [HIGH] — Reject writes on closed sessions; transactional close (subagent finding 3; FR-C1/C2, §6).**
  The close tally is non-transactional today and writes (`insertAttempt`, `setSessionCurrentQuestion`,
  `upsertSkillState`) are still accepted on a session whose `ended_at` is set, so a late write after
  close can re-open a completed session's counts. (a) The close handler wraps the tally + the
  `patchSessionClose` + the `setSessionCurrentQuestion(..., null)` clear in ONE transaction; (b)
  session-scoped write handlers reject (409/404) when the loaded session's `ended_at IS NOT NULL`
  (enforced via `requireOwnedSession`'s session row, which is already loaded — no extra query).
  *Pass:* a post-close attempt/pointer/skill-state write is rejected; close is atomic. In gate.
  **DONE 2026-07-23** — `lib/bff/engine_guard.ts` adds `conflict()` (409) +
  `requireOwnedOpenSession` (404 on mismatch, 409 when `ended_at != null`, no extra query);
  `attempt` + `session/current` + `session/close` routes use it (a re-close is rejected,
  not re-tallied); the served-pointer clear is folded INTO `patchSessionClose` as one
  atomic UPDATE (drizzle + in-memory twins) so a partial apply can never leave a session
  half-closed (FR-B3c). Red first (4 closed-session/atomic assertions failed), then green
  (28 files / 239 tests); tsc + lints clean.

- **T R.13 (red→green) [HIGH] — Pool sharing / connection budget vs Cloud SQL `max_connections` (subagent finding 2; FR-F1, §7 NFR).**
  Cloud SQL `max_connections=50` vs multiple uncapped `pg` pools (engine + threads + marker + probe)
  can exhaust the budget under concurrency. (a) Share/cap the engine `pg` pool size from config
  (env-driven `ENGINE_PG_POOL_MAX`, bounded default); (b) document the per-service pool budget so the
  sum across frontend pools stays under `max_connections`. No new abstraction — a config knob + a note.
  *Pass:* engine pool size is bounded + configurable; documented budget holds under the documented
  concurrency. In gate. **DONE 2026-07-23** — `lib/adapters/db/node_pg_url.ts` adds a bounded
  `pgPoolMax(env, defaultMax)` (reads `ENGINE_PG_POOL_MAX`, clamps to [1, 20], default 5); wired
  into all three frontend pools (`drizzle_engine_db`, `pg_thread_repo`, `marker_repo`);
  `infra/gcp/cloud-run-frontend.tf` sets `ENGINE_PG_POOL_MAX="5"` (3 × 5 = 15 ≤ 50). Red first
  (`pgPoolMax is not a function`), then green (6/6 + 92 adapter tests); tsc + lints clean.
  Budget recorded in `docs/adr/decisions.md`.

- **T R.14 (red→green) [MEDIUM] — Deploy guard: flag ↔ image digest; commit counts ledger + seed_sources (subagent finding 2; FR-A4/§6 cutover, FR-G1).**
  The build-time durable flag can diverge from the Terraform `enable_durable_engine` var (a flag-off
  image deployed with the var on, or vice versa), and the seed counts ledger + `seed_sources/` are
  off-CI / untracked. (a) Add a deploy-time guard asserting the deployed image was built with the flag
  matching `enable_durable_engine` (digest/label check); (b) commit `seed_engine_content.counts.json`
  + the `seed_sources/*.json` so the parity gate (`test_engine_seed_source_parity.py`) runs in CI.
  *Pass:* flag↔var mismatch fails the guard; counts ledger + seed sources tracked. In gate.
  **DONE 2026-07-23** — `frontend/Dockerfile.frontend` runner stage now re-declares
  `ARG NEXT_PUBLIC_FF_DURABLE_ENGINE` and bakes `LABEL org.agentsframework.ff_durable_engine=$NEXT_PUBLIC_FF_DURABLE_ENGINE`
  (ARGs don't cross FROM, so the runner re-declares it; the label is the deploy-time witness of what
  was built). `scripts/deploy_gcp.sh` adds `assert_frontend_image_flag_matches_tfvars` — reads the
  PINNED `frontend_image` digest + `enable_durable_engine` from tfvars, `docker inspect`s the label
  (local image first, pull fallback for standalone `phase_frontend`), fails on mismatch — and
  `phase_frontend` calls it BEFORE `tofu_gate` (traffic is LATEST 100% on apply). `git add`-ed
  `frontend/drizzle/seed_engine_content.counts.json` + `seed_sources/{skills,tutorials,content_strings,blueprints}.json`
  so `test_engine_seed_source_parity.py` runs in CI. Red first (5 failing: no label, no guard fn,
  guard not reading pinned image, guard not inspecting label, guard not before apply), then green
  (7/7 new + 19/19 cluster with T R.5 build-flag + T R.8 parity + 267/267 architecture+infra+emitter);
  `bash -n scripts/deploy_gcp.sh` clean.

- **T R.15 (red→green) [MEDIUM] — Strengthen probe (pointer + score) + `EngineClient` GET retry (subagent finding 4; FR-A9.2, DoD §9).**
  The Phase R.6 probe proves session id + attempt count, not the resume position (`current_question_id`)
  or the server-computed score; `EngineClient` coarse GETs lack the FR-A9.2 retry the `HttpEngineDb`
  row-level reads have. (a) Extend the authenticated probe to assert the served pointer + the
  `session/active` running score match the submitted history; (b) give the coarse `EngineClient` GETs
  the same bounded-backoff retry the row-level `HttpEngineDb` reads use (idempotent reads only).
  *Pass:* probe asserts pointer + score; coarse GETs retry transient 5xx. In gate / on-demand (probe).
  **DONE 2026-07-23** — `frontend/e2e/full-stack/engine-persistence-probe.spec.ts` now asserts (a) the
  served pointer (`current_question_id`) matches the attempted question AND `running_score` matches
  the submitted history (one first_try-correct → `score_correct=1, score_total=1`), on device-1 AND on
  the cross-context device-2 resume (proving pointer + tally are durable, not RAM-local);
  `frontend/lib/adapters/engine/engine_client.ts` `getJson` now retries transient 5xx / network errors
  with bounded backoff (3 attempts, 25ms × attempt — same constants as `HttpEngineDb.call`); 4xx
  surfaces immediately; POSTs never retry (non-idempotent). Red first (3 retry tests failed: no retry
  on 5xx, no retry on network error, 1 attempt instead of 3), then green (9/9 engine_client + 240/242
  engine+bff cluster); tsc + lints clean.

- **T R.10c (gate) — Final convergence gate (DoD §9).** `make check` +
  `pytest tests/architecture/ -q` + `cd frontend && pnpm vitest run` + persistence probe (T R.6/R.15)
  + the routed reviewer (`.cursor/skills/code-review`). Paste verbatim output (not summarized).
  *Pass:* all green; routed reviewer verdict ≥ MERGE-READY; the §9.2 conditional persistence tick
  is re-ticked to `[x]`. (R.10b — the TAP-4 reviewer-warning disposition — is recorded in
  `decisions.md`, not a code task; the warnings are heuristic noise, not uncovered acceptance paths.)
  **DONE 2026-07-23** — gate green: `make check` 5376 passed/50 skipped; `pytest tests/architecture/`
  254 passed/2 skipped; `pnpm vitest run` bulk 2164 passed + architecture 189 passed (8 prior
  timeouts were parallelism-induced at the 10s default, all pass in isolation / with
  `--testTimeout=60000`); authenticated Playwright persistence probe 1 passed (pointer + score
  durable, cross-device); routed reviewer verdict **approve** (109 files reviewed, 0 criticals, 2
  non-blocking TAP-4 warnings on pre-existing infra test files — R.10b disposition recorded in
  `decisions.md`). Two test-infra fixes landed during the gate (both G9-justified, test-only):
  (1) `scratch_engine_pg.ts` now confirms a real host-side `pg.Client` TCP connect (not just
  in-container `pg_isready`) before declaring ready — Docker Desktop's port-forward proxy lagged the
  unix-socket readiness, causing `ECONNRESET`; (2) the T R.15 (a) probe now calls
  `POST /api/engine/session/current` (the only FR-B3a pointer writer) after `/next`, mirroring
  `use_quiz.ts`, so `current_question_id` is durable and asserted on both devices. §9.3 updated
  with the T R.15 strengthened run; §9.2 persistence tick re-confirmed `[x]`.

---

## FR → task coverage (1:1 audit)

Every FR in the spec §8 table maps to at least one task above:

| Track | FRs | Tasks |
|---|---|---|
| A | A1, A2, A2a, A3, A4, A5, A6, A7, A8, A9.1, A9.2 | T A.1–A.15, T 4.3 (wire), T 4.4–4.5 (methods + in-adapter idempotency), **T R.1 (A2a dispatcher)**, **T R.5 (A4 flag wiring)** |
| B | B1, B2, B3, B3a, B3b, B3c, B3-feedback, B4, B5, B6, B7, B8, B9, B10 | T B.1–B.13, **T R.3 (B/C boundary)**, **T R.7 (B10 tie-break)** |
| C | C1, C1a, C2, C3, C4, C5, C6 | T C.1–C.6, **T R.3 (C2 server-side hard stop)** |
| D | D1, D1a, D2, D3, D4, D5 | T D.1–D.4, **T R.7 (D3 tie-break)**, **T R.9 (summary hydration test)** |
| E | E1, E1a, E2, E3, E4, E5 | T E.1–E.6 (server-side via T A.11), **T R.7 (E1 tie-break)** |
| F | F1, F2, F3 | T F.1–F.5, **T R.2 (F1/F3 Cloud SQL wiring)**, **T R.9 (migration replay test)** |
| G | G1, G2, **G2a**, G4 | T G.1–G.3, T F.3 (seed always-apply), T Z.1(b)(c), **T R.4 (G2a fail-closed)**, **T R.8 (G1 source parity)** |
| G3 | empty-content guard | T A.15 (ships with A) |
| §4 | parity + 0004 both parts + methods #30/#31 | T 4.1–4.5, **T R.9 (partial-index insertAttempt via real pg)** |
| §7 | coarse-read chattiness | T A.9 (endpoints), T A.11 (hooks actually reach them), **T R.9 (coarse summary hydration test)** |
| §6 | per-question resolution-order tie-break | **T R.7** |
| DoD §9 | end-to-end persistence + full gate | T Z.1–Z.3, **T R.6 (authenticated full-stack probe)**, **T R.15 (probe pointer+score)**, **T R.10c (rerun gate)** |
| A (flag) | A4 build-arg ↔ Terraform var | **T R.5**, **T R.14 (deploy guard)** |
| A (conformance) | adapter catalogue parity | **T R.10a (PAIRS omission)** |
| E (prod path) | E1 tie-break on the `/next` hot path | **T R.11** |
| C (concurrency) | C1/C2 transactional close + closed-session reject | **T R.12** |
| F (NFR) | F1 pool budget vs `max_connections` | **T R.13** |

**Parallelism summary:** `[P]` tasks run concurrently within their phase once the phase's
dependency line is met. Phases **G ∥ F** (prereqs; T F.1 `[P]` within F). Phase 4 follows (its
`0004` file joins F's runner inventory; the full-inventory run is proven at T Z.1). Phase A is a
hard barrier (atomic swap). Within B: T B.9–B.12 `[P]`. Within C: T C.4, C.6 `[P]`. Within E:
T E.3, E.4, E.6 `[P]`. Within D: T D.3, D.4 `[P]`. **Phase R** is sequential by merge risk:
R.1 → R.2 → R.3 → R.4 → R.5 → R.6 → R.7 → R.8 → R.9 → R.10a → R.11 → R.12 → R.13 → R.14 → R.15 → R.10c,
EXCEPT R.4/R.5/R.8 may run in parallel with R.2 (independent infra/seed surfaces) once R.1 lands
(R.1 is the trust-seam gate — nothing in R should merge before it). R.6 depends on R.2 + R.5 (needs
deployable Cloud SQL + a flag-on bundle). R.11/R.12/R.13/R.14/R.15 are the Stage-5 subagent-finding
fixes (R.11 depends on R.7's helper; R.12 on R.3's boundary; R.15 on R.6's probe). R.10a is the
conformance-catalogue repair (unblocks the gate). R.10c is the final gate after R.10a + R.11–R.15.
