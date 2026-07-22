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

## FR → task coverage (1:1 audit)

Every FR in the spec §8 table maps to at least one task above:

| Track | FRs | Tasks |
|---|---|---|
| A | A1, A2, A2a, A3, A4, A5, A6, A7, A8, A9.1, A9.2 | T A.1–A.15, T 4.3 (wire), T 4.4–4.5 (methods + in-adapter idempotency) |
| B | B1, B2, B3, B3a, B3b, B3c, B3-feedback, B4, B5, B6, B7, B8, B9, B10 | T B.1–B.13 |
| C | C1, C1a, C2, C3, C4, C5, C6 | T C.1–C.6 |
| D | D1, D1a, D2, D3, D4, D5 | T D.1–D.4 |
| E | E1, E1a, E2, E3, E4, E5 | T E.1–E.6 (server-side via T A.11) |
| F | F1, F2, F3 | T F.1–F.5 |
| G | G1, G2, G4 | T G.1–G.3, T F.3 (seed always-apply), T Z.1(b)(c) |
| G3 | empty-content guard | T A.15 (ships with A) |
| §4 | parity + 0004 both parts + methods #30/#31 | T 4.1–4.5 |
| §7 | coarse-read chattiness | T A.9 (endpoints), T A.11 (hooks actually reach them) |

**Parallelism summary:** `[P]` tasks run concurrently within their phase once the phase's
dependency line is met. Phases **G ∥ F** (prereqs; T F.1 `[P]` within F). Phase 4 follows (its
`0004` file joins F's runner inventory; the full-inventory run is proven at T Z.1). Phase A is a
hard barrier (atomic swap). Within B: T B.9–B.12 `[P]`. Within C: T C.4, C.6 `[P]`. Within E:
T E.3, E.4, E.6 `[P]`. Within D: T D.3, D.4 `[P]`.
