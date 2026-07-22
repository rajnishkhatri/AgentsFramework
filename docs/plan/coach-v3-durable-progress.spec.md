# Spec — Coach V3 Durable Learner Engine (Durable Progress + Bounded-30 Quiz)

> EARS acceptance criteria. Failure paths first. This is the *what*; the *why* (D1
> vs D2, D6 shape) lives in the design doc + the ADR raised at plan time.

**Status:** APPROVED (re-approved 2026-07-22 after review rounds 5–6; tasks regenerated same day).
Direction (D1/Shape B) unchanged across all rounds; premises corrected per the plan's Replan log.
**Owner:** Rajnish Khatri
**Related:** [design doc](coach-v3-durable-progress.brainstorm.md) · memory `coach-v3-progress-ephemeral-inmemory` · brainstorm gate decisions DEC-1..DEC-6

---

## 1. Goal

Give the eng-coach **V3** learner-facing quiz **durable, cross-device** progress, and make
practice a **bounded 30-question quiz** that closes to an enriched summary and restarts fresh.
Today the quiz runs on an in-memory DB that is lost on any page reload; nothing a learner does
survives logout or moves to another device.

Outcomes for the learner:
1. Leave mid-session (logout, navigate away, close tab) and **resume where you left off — on any device**.
2. Every attempt (and first-try miss) is **durably recorded** (foundation for later custom lessons).
3. A quiz is **exactly 30 questions**, then a **summary** with a miss breakdown + strong/weak areas.
4. Starting a new quiz begins **fresh at Q1**, preferring questions you **haven't already answered correctly**.

## 2. Context

- **Refuted premise:** the prod quiz runs entirely on a fresh `InMemoryEngineDb` per page load
  (`frontend/lib/composition_engine_browser.ts:96,215-277`) — attempts/sessions/skill_state/misses
  never leave the tab. There is **no durable store wired at all** today (design doc §2).
- **The Postgres layer already exists** (Drizzle repos, `pgEngineDb`, `schema.pg.ts` 12 tables,
  migrations `0001–0003`) but is wired only to the unused server root.
- **Direction (locked): D1** — an `HttpEngineDb` implementing the `EngineDb` surface (29 methods
  today → **31** after this spec's two new methods, per-method disposition incl. server-only
  exclusions — FR-A4)
  (`frontend/lib/adapters/engine/db/engine_db.ts`) calling **new** BFF `/api/engine/*` Route
  Handlers that run `pgEngineDb` server-side. **D6 = Shape B** — the BFF server-side holds
  `DATABASE_URL`, exactly as it already does for threads (`frontend/lib/bff/server_composition.ts`).
- **Selection today** (explore subagent): FSRS picks the weakest/most-due **skill** from durable
  `skill_state`, then the easiest-difficulty reviewed item; **no-repeat is within-session only**,
  so a new session can re-serve prior questions. Misses influence skill-level adaptivity, not
  same-question repeat; only `mode=review` re-serves exact misses.
- **Summary partly exists** (`session_summary_vm.ts`, `SummaryView`): score, mastery-delta, time,
  recommended-next, outcome counts, single misconception. **Missing:** a per-question misses list
  and a strong/weak per-skill panel.

**Constitution backdrop:** the Frontend Ring rules (`frontend/AGENTS.md`, F-R1..F-R9) + the 8
root invariants. Key ones in play: F-R9 (BFF holds no *browser/edge* creds — server-side Route
Handler DB access is allowed, precedent = threads), F-R4/B6 (Route Handlers are composition
adapters), A4/F-R8 (no SDK type escapes the adapter), C1/C2 (composition-root-only adapter naming).

## 3. Functional requirements (EARS)

### Track A — D1 durable engine seam

- **FR-A1 (failure).** IF a BFF `/api/engine/*` request arrives without a valid WorkOS session
  THEN THE SYSTEM SHALL respond `401` and perform no DB read or write.
- **FR-A2 (failure).** IF a client request body names a `learnerId` THEN THE SYSTEM SHALL ignore
  it and derive `learnerId` from the server-verified WorkOS session only (never trust the client).
- **FR-A2a (authorization — cross-learner isolation, failure).** IF an authenticated learner A
  requests a resource owned by a different learner B (a session id, attempt set, or summary that
  resolves to B's `learnerId`) THEN THE SYSTEM SHALL NOT return B's data — every engine read is
  scoped by the **server-derived** `learnerId`, so a resource keyed to another learner resolves to
  empty/`404`, never a cross-learner leak. This is **beyond FR-A2**: A2 stops the client from
  *claiming* to be B; A2a stops A (honestly authenticated as A) from *reading* B's rows by guessing
  a session id. **Mechanism (review #6 — the DB surface can't do this alone):** the session/attempt
  methods accept only `sessionId` (`getSession(id)`, `listSessionAttempts(sessionId)`,
  `patchSessionClose(id, …)`, `setSessionCurrentQuestion(sessionId, …)`, `insertAttempt(a)`) — no
  `learnerId` parameter — so scoping is enforced by an **ownership guard in the route family**: a
  shared `requireOwnedSession(engineDb, sessionId, learnerId)` helper that loads the session via
  `getSession`, compares its `learner_id` to the server-derived `learnerId`, and returns `404` on
  mismatch **before** any dependent read or write runs. Handlers that need the session row anyway
  (bootstrap, active, summary, close) pay no extra query. Learner-keyed methods
  (`listSkillState`, `listMisses`, `listProgressPoints`, `accuracyRowsBySkill`,
  `getNewestOpenSession`) are scoped by passing the server-derived `learnerId` directly.
- **FR-A3 (failure).** IF the engine `DATABASE_URL` is unset in the BFF server environment THEN
  THE SYSTEM SHALL fail the engine route with a server error surfaced as a typed `EngineRepoError`
  — it SHALL NOT silently fall back to an in-memory store that loses data.
- **FR-A4 (revised — review #6).** THE SYSTEM SHALL implement the **full `EngineDb` surface** behind
  the `HttpEngineDb` → BFF `/api/engine/*` → `pgEngineDb` path with an **explicit per-method
  disposition**: every method is mapped to exactly one of (a) a **coarse endpoint carrier**, (b) a
  **fine-grained per-method route**, or (c) a **server-only exclusion** — `HttpEngineDb` implements
  (c) methods by throwing a typed `EngineRepoError("server-only method")`, never by silently
  succeeding. *(Surface size: **29 methods today + 2 new** = **31**: `setSessionCurrentQuestion`
  (write, FR-B3a) and `getNewestOpenSession(subject, learnerId)` (read, FR-B1/B2 — review #6-B2:
  `getSession(id)` needs an id the cross-device client doesn't have, and `listClosedSessionsByLearner`
  **explicitly excludes** `ended_at IS NULL` rows (`engine_db.ts:113-114`), so no existing method can
  find the resumable session). The pointer **read** remains a *field* on the session shape.)*
  **Server-only exclusions (content-integrity):** the four content writes — `insertQuestion`,
  `insertHint`, `insertTestItem`, `insertTestBlueprint` (`engine_db.ts:83,97,102,106`) — SHALL NOT be
  exposed as HTTP endpoints: post-swap no browser call site invokes them (the seed moved server-side,
  Track G), and an authenticated-learner content-write endpoint would let any learner mutate the bank.
  A blanket "every unfolded method gets a handler" policy is therefore rejected. Rationale for full
  surface: the bag swap is **atomic** (one shared `db` instance for every `useEngine()`
  screen — `composition_engine_browser.ts:96`), so a partial surface breaks non-quiz screens on
  load. Verified: a quiz-only set (15 methods) leaves `listClosedSessionsByLearner`,
  `listSessionAttempts`, `getTutorial`, `accuracyRowsBySkill` unimplemented → **progress, summary,
  and skill-detail hard-fail** (un-caught reads) and **dashboard's trust rail goes dark**. Only
  coach survives. The gap beyond quiz is 4 methods; all are thin row-level reads.
- **FR-A5.** WHEN the learner submits a graded answer THE SYSTEM SHALL durably persist the attempt
  row (incl. `correct`, `resolution`, `used_hint`, `elapsed_ms`) to Postgres before the submit
  interaction is considered complete.
- **FR-A6 (revised — review issue #1).** THE SYSTEM SHALL keep the `EnginePortBag`/`EngineDb`
  consumer contract unchanged for the **quiz + write paths** (quiz page, the 13 repos, coach) — those
  swap on the `EngineDb` implementation only. **The 3 heavy read hooks (`use_dashboard`,
  `use_summary`, `use_skill_detail`) AND the scheduler entry SHALL be rewired to call coarse
  loaders**, because swapping only the `EngineDb` instance leaves them fanning out per-repo (e.g.
  `use_summary.ts:145-153` calls **6 repos** via `Promise.all`) — the coarse `/dashboard`/`/summary`/
  `/skill`/`/next` endpoints are **not** `EngineDb` methods, so nothing routes those repo calls into
  one endpoint automatically. *(Original FR-A6 "all call sites unchanged" was refuted at review: it
  held for row-level `EngineDb` consumers but not for multi-repo read hooks or the client-side
  `FsrsScheduler.next()`.)* Introduce a thin **coarse client/loader seam** (an `EngineClient` port
  above `EngineDb`, or per-screen coarse loaders) the read hooks call. Rationale for the change over
  "fine-grained first": accepting per-method HTTP for the read screens is the exact §7 chattiness
  regression the coarse endpoints exist to prevent. Every screen still becomes network-backed at swap
  time (FR-A4); the read screens reach the network through the coarse seam, not port-for-port.
- **FR-A7 (NFR-linked).** WHILE an answer is being persisted THE SYSTEM SHALL display the verdict
  immediately from the deterministic client grader (optimistic), and SHALL reconcile if the
  server write fails.
- **FR-A8 (failure).** IF a durable write fails after the optimistic verdict is shown THEN THE
  SYSTEM SHALL surface an error state and SHALL NOT advance as though progress were saved.
- **FR-A9 (idempotency + retry — durability correctness, not polish).** For a spec whose entire
  purpose is durable writes, the write seam SHALL have defined idempotency and retry semantics:
  1. **Attempt POST idempotency (mechanism finalized — review rounds 2-5).** THE SYSTEM SHALL make
     `POST /api/engine/attempt` idempotent for a single graded answer — a client retry after a network
     blip SHALL NOT create a second attempt row for the same answer. **Mechanism: a client-supplied
     `idempotency_key` (one UUID per answer action, resent verbatim on retry) enforced by a partial
     unique index `(session_id, question_id, idempotency_key)`, with the idempotent insert handled
     INSIDE the DB adapter** — `insertAttempt` does `.onConflictDoNothing()` on that index and returns
     a typed already-existed result. **The BFF handler SHALL NOT catch a PostgreSQL unique-violation**,
     because `pgEngineDb` wraps every operation's error as an opaque `EngineRepoError`
     (`drizzle_engine_db.ts:284-286`) — SQLSTATE 23505 is not recoverable at the handler (review issue
     #5). *(The natural-key `(session_id, question_id, created_at)` option is rejected: `created_at` is
     server-assigned — `AttemptInput` omits it — so a retried POST carries nothing to match on; see the
     plan §6 decision.)* Rationale: without idempotency, retry → two rows for one answer → the FR-B10
     running tally + close tally inflate. This is the same double-count root as §6 concurrent-device
     duplicates; the dedup-by-`question_id` tally (§6) is the read-side backstop, this is the
     write-side fix.
  2. **`HttpEngineDb` retry/timeout policy.** THE SYSTEM SHALL retry **idempotent reads** with
     bounded backoff on transient failure (5xx/network), and SHALL surface **non-idempotent write**
     failures per FR-A8 (error + no advance) rather than silently dropping them. Rationale: FR-A8
     covers only the submit path; a transient 5xx on `skill-state` upsert or the served-pointer
     write that the client silently drops is a durability loss — the exact failure this spec exists
     to prevent. (The served-pointer write is the one exception: it is fire-and-forget by design —
     §7 / FR-B3a — and its failure degrades to FR-B8, not an error state.)

### Track B — Cross-device resume (incomplete sessions only)

- **FR-B1.** WHEN the quiz screen mounts for an authenticated learner with a resumable session
  THE SYSTEM SHALL resume that session at the learner's last position with the running score,
  instead of opening a fresh session.
- **FR-B2.** THE SYSTEM SHALL define a *resumable* session as the learner's **newest** session
  with `ended_at IS NULL`, with **no time-based expiry**.
- **FR-B3.** THE SYSTEM SHALL restore **position (which question) + score (correct/total) only**;
  the current question itself is re-loaded by id (no unsubmitted-selection or mid-coached-loop
  restore in this spec).
- **FR-B3-feedback (mid-feedback abandonment — v1 scope decision).** IF the learner leaves while
  the current item is in the **feedback/coaching phase** (already graded, reading the verdict or in
  the coached loop) THEN on resume THE SYSTEM SHALL treat that item as **answered and advance to the
  next served question** — it SHALL NOT restore the feedback screen, the verdict, or the coached
  loop. Rationale: the durable surface is exactly `current_question_id`; the RAM pointer's transient
  `phase`/`verdict`/`answeredLetter` are **intentionally not persisted** in v1 (keeps the resume
  seam a single column, per §4). The trade is bounded and honest: **no attempt row or score is
  lost** — only the transient feedback view — and the learner re-encounters the skill through FSRS.
  (Restoring feedback/coaching state is deferred; it would widen the durable **resume surface** beyond
  the single pointer column — `0004`'s second column, `idempotency_key`, is idempotency state, not
  resume state. Noted in §10.)
- **FR-B3a (served pointer — the load-bearing write).** WHEN a question is **served** to the
  learner (enters the `answering` phase) THE SYSTEM SHALL durably record it as the session's
  *current served question* — on serve, **not** on submit. Rationale: position is **not** derivable
  from `attempt` rows alone — a learner who opens Q4 and leaves before submitting has no attempt
  row for Q4, yet must resume **at Q4**, not at a freshly re-derived next-question. Today this
  lives only in the RAM `ActiveQuizPointer.questionId` (written by `quiz/page.tsx:284-314` on
  entering `answering`/`reviewing`); it must become durable.
- **FR-B3b.** THE SYSTEM SHALL make `GET /api/engine/session/active` return the session's stored
  *current served question* as the resume position — it SHALL NOT re-derive position by asking the
  scheduler for the next unserved item (which could hand back a different question than the one the
  learner was looking at).
- **FR-B3c.** WHEN the served pointer's question is later resolved (submitted/walked-through) and
  the next question is served THE SYSTEM SHALL advance the pointer to the newly served question;
  WHEN the session closes THE SYSTEM SHALL clear it.
- **FR-B4.** WHEN a learner logs in on a different device THE SYSTEM SHALL resume the same
  incomplete session, because resume state is read from Postgres keyed by the WorkOS `learnerId`.
- **FR-B8 (NULL-pointer resume fallback — the failure path FR-B3b acknowledges).** IF a resumable
  session's `current_question_id` is **NULL** (the fire-and-forget served-pointer write failed per
  §7, OR a pre-`0004` row predates the column) THEN THE SYSTEM SHALL **re-derive** the resume
  position by invoking the scheduler for a next-pick, **scoped by FR-B9 (exclude the session's
  already-answered questions) and FR-E1 (content-fresh eligibility)**; IF the session has **zero**
  attempts THEN this yields the session's first scheduled question (session start). **Scope note —
  FR-B3b is NOT violated:** FR-B3b forbids re-deriving when a *non-NULL* pointer exists (honor the
  stored id; do not throw it away and re-pick). FR-B8 is the *absent*-pointer case — there is no
  stored id to honor, and "next question" is **not derivable from `listSessionAttempts` alone**
  (attempts record what was *answered*, and there is no `next_question_id` column anywhere), so a
  scheduler pick is the only way to produce a position. The FR-B9/FR-E1 scoping is what keeps that
  pick from re-serving an answered question. Rationale: §7 permits the pointer write to fail;
  without a scheduler-backed fallback the acknowledged NULL failure path is unimplementable.
- **FR-B9 (served-set reconstruction on resume — no-repeat regression fix).** WHEN a session is
  resumed THE SYSTEM SHALL reconstruct the within-session **served set** from the session's durable
  attempt history (the set of `question_id`s in `listSessionAttempts`) — OR scope the scheduler's
  next-pick to exclude them (`NOT IN` the session's attempted question ids) — so the no-repeat
  guarantee (FR-9/10/11, FR-E1a) survives reload. Rationale: `servedIds` is a client-RAM set today
  (`use_quiz.ts`) that dies on reload; a learner who answered Q1–Q29, left, and resumed would have
  an empty RAM served set, letting the scheduler re-hand an already-served question (e.g. Q15) as
  "next." Post-durable-swap this is a real regression the RAM set masked. (Served-but-unsubmitted
  items have no attempt row, so the `current_question_id` pointer — FR-B3a — covers the one in-flight
  question the attempt-derived set misses.)
- **FR-B10 (running-score reconstruction on resume — commit-first semantics, corrected review #3).**
  WHEN a session is resumed THE SYSTEM SHALL compute the running score **server-side in the
  `GET /api/engine/session/active` response** to **match the live commit-first tally exactly**:
  - **numerator = count of unique questions resolved `first_try`** (resolution == `first_try`),
  - **denominator = count of unique resolved questions** (questions with a resolving attempt).

  It SHALL NOT count coached-correct or walked-through toward the numerator, and SHALL NOT re-tally on
  the client. **Rationale (load-bearing):** under commit-first (prod default), the live reducer bumps
  `correct` **only** on `first_try` (`quiz_screen_reducer.ts:434`: `bumpCorrect = resolution ===
  "first_try"`) — a coached-correct answer is resolved but NOT scored. Counting all resolving-correct
  attempts (the earlier draft) would make the **resumed** score higher than the same session's **live**
  score — a resume showing the wrong number. `quiz_session.score_correct`/`score_total` are written
  **on close only** (`schema.pg.ts:209-210`, default 0 while open), so the running score is derived
  from attempts, grouped by `question_id` (unique), with the `first_try`-only numerator. `POST
  /session/close` computes the **same** server-side and ignores any client-provided tally. This
  extends the FR-D3 "never re-tally on the client" discipline to resume AND close.
- **FR-B5 (failure).** IF the resumable session's stored question id no longer resolves (e.g.
  content removed) THEN THE SYSTEM SHALL open a fresh session rather than error — honest recovery,
  never fabricate progress.
- **FR-B6 (failure).** IF a deep-link requests a specific mode (`?mode=review` or `?focus=<skill>`)
  THEN THE SYSTEM SHALL honor that intent and open the requested fresh session, not resume.
- **FR-B7.** THE SYSTEM SHALL NOT resume a **completed** session (see FR-C2) — a completed session
  is never a resume candidate.

### Track C — Bounded-30 quiz + fresh restart

- **FR-C1.** WHEN the 30th (target-th) item of a bounded session **resolves** THE SYSTEM SHALL —
  in one automatic flow, without a "Keep practising"/"See summary" wait — persist the resolving
  attempt, close the session (set `ended_at` + the stored score tally), and route to the summary
  screen. Auto-close + navigate, not show-banner-and-wait.
- **FR-C1a (commit-first interaction — the load-bearing timing).** THE SYSTEM SHALL trigger the
  auto-close on the 30th item's **resolution**, NOT on its first graded submit. Under commit-first
  (prod default), a wrong first answer on the 30th item opens the coached loop (retry / hint /
  walk-through) and the item resolves later (`first_try` | `coached` | `walked_through`). Closing
  on the first *grade* would yank a learner who missed Q30 to the summary **mid-coaching**; the
  session SHALL stay open through the coached loop and close only when the 30th item resolves.
  (Resolution signals already exist at the page: `coachedConfirm`, `escape_taken`, a correct
  submit — `quiz/page.tsx:456,477,496`; `progressVm.complete` is gated on `gradedTotal`, and a
  retry does not increment it.)
- **FR-C2.** THE SYSTEM SHALL treat a session whose graded count has reached its `target_count`
  and been closed as **completed** — no 31st question is served in that session.
- **FR-C3.** THE SYSTEM SHALL NOT offer a "Keep practising" continuation of the same **default
  adaptive practice** session past the target (30 is a hard stop) — removing today's
  relabel-and-continue behavior at `frontend/app/(coach)/learn/quiz/page.tsx:607-632`.
- **FR-C6 (scope guard).** THE SYSTEM SHALL retain the endless-session *capability* in the model
  (`target_count = null`, `session_repo.ts` three-way semantics) for other callers (e.g. computed
  `mode=review` counts, explicit drills) — this spec bounds the **default practice path** to 30,
  it does NOT retire endless sessions globally.
- **FR-C4.** WHEN the learner starts a new practice session after a completed one THE SYSTEM SHALL
  open a **fresh session beginning at position 1** (a new `quiz_session` row), never resume the
  completed one.
- **FR-C5 (failure).** IF the bounded session's servable pool is exhausted before reaching the
  target (fewer eligible questions than `target_count`) THEN THE SYSTEM SHALL close the session
  gracefully to the summary at the count reached — it SHALL NOT throw a raw error to the learner
  (fixes the current `openQuizItem` throw at `use_quiz.ts:219,242,263`).

### Track D — Enriched summary

- **FR-D1.** WHEN the summary renders for a completed session THE SYSTEM SHALL show a **misses
  list**: each question in **this session** whose resolving attempt was **incorrect OR
  walked-through**, identifiable to the learner (stem/skill), in addition to the existing outcome
  counts. **Scope = this session's attempts** (`listSessionAttempts`), NOT the global
  `attemptRepo.misses()` (which is outstanding-across-history; a miss cleared later must still
  appear in the summary of the session it happened in).
- **FR-D1a.** THE SYSTEM SHALL count a **walked-through** item as a miss for the list even though
  its resolving attempt eventually ends the item — a walked-through item was never independently
  solved (resolution = `walked_through`, `correct=false`).
- **FR-D2.** THE SYSTEM SHALL show a **strong vs. weak areas** panel derived from **this session's**
  per-skill accuracy, **projected from `listSessionAttempts`** (group the session's attempts by the
  question's `skill_id`, tally correct/total per skill). It SHALL NOT use the existing
  `accuracyBySkill` API for this panel, because that is scoped to the **last N sessions (default
  6)** — a different question than "how did I do per skill *in this session*". (`accuracyBySkill`
  stays untouched for its existing skill-detail trend use.) No new schema.
- **FR-D3 (scope clarified — review #6).** THE SYSTEM SHALL derive the **headline score** and the
  **content-fresh eligibility** server-side from stored session/attempt data, and SHALL NOT re-tally
  the score on the client. **Presentational panels (misses list, strong/weak) MAY be projected on the
  client from server-supplied attempt rows** — projection (group/label already-fetched rows) is not
  re-tallying (recomputing the authoritative score). The distinction: the *headline number* the
  learner is judged by is server-authoritative (FR-B10 / close tally); the *panels* re-shape rows the
  server already returned. This is why `session_summary_vm.ts` computing the panels is compliant while
  a client recomputation of `score_correct` would not be.
- **FR-D4 (edge).** IF a completed session has zero misses THEN THE SYSTEM SHALL render the misses
  list as an explicit empty/"clean sweep" state, not a broken or absent section.
- **FR-D5 (edge).** IF per-skill accuracy is undeterminable for a skill (no on-skill attempts)
  THEN THE SYSTEM SHALL omit that skill rather than fabricate a 0% (AP-6: undecidable → omit).

### Track E — Content-fresh eligibility (avoid answered-correctly)

- **FR-E1.** WHEN selecting a question for a session THE SYSTEM SHALL prefer questions the learner
  has **not already answered correctly** in any prior session, computed per-learner from durable
  attempt history. **The exclusion predicate is: latest attempt for that question has
  `correct === true`.** This cleanly includes **coached-correct** (resolving attempt is
  `correct=true, resolution=coached`) and excludes **walked-through** (`correct=false,
  resolution=walked_through`) — a walked-through item was never independently solved, so it STAYS
  eligible (consistent with FR-D1a and FR-E2). **"Latest" is by `created_at`** across the question's
  attempt history; the coached loop produces multiple rows per question, so the resolving (newest)
  row is the one that decides eligibility. (A same-millisecond tie from concurrent-device inserts is
  theoretically possible and negligible; if belt-and-suspenders is wanted, break ties by row id —
  plan-time, not an FR.)
- **FR-E1a (layering — not a replacement).** THE SYSTEM SHALL apply eligibility as a **prefer/
  filter layer around** the existing FSRS skill pick, NOT a replacement for it: FSRS still chooses
  the weakest/most-due skill and the easiest-difficulty item; eligibility narrows *which* items
  within that pick are drawn. The **within-session `servedIds` no-repeat still applies on top**
  (FR-9/10/11) — a session never re-serves its own already-served question regardless of eligibility.
- **FR-E2.** THE SYSTEM SHALL keep questions the learner has **missed** (latest attempt not
  `correct===true` — includes incorrect and walked-through) eligible, so weak items recur.
- **FR-E3 (fallback).** IF the not-yet-correct eligible pool is exhausted THEN THE SYSTEM SHALL
  fall back to **normal FSRS adaptive selection over the full reviewed bank** (allow correctly-
  answered questions back in), i.e. today's scheduler behavior — no new ordering.
- **FR-E4.** THE SYSTEM SHALL implement eligibility as a **durable cross-session read projection**
  over the append-only `attempt` history — the set of question ids whose latest attempt is
  `correct===true` (roughly the *inverse* of outstanding misses), per-learner, across sessions. No
  new write path, no `skill_state` mutation (mirrors how `misses()` is derived). **This is only
  honorable once Track A (durable engine) + Track G (server content) are live** — the ephemeral
  in-memory store cannot compute a cross-session/cross-device correct-history, so E1 has a hard
  dependency on A + G.
- **FR-E5.** THE SYSTEM SHALL leave the explicit `mode=review` behavior (serve exact past misses)
  unchanged; content-fresh eligibility applies to the default adaptive mode.

### Track F — Infra (D6, own PR)

- **FR-F1.** THE SYSTEM SHALL provision the engine `DATABASE_URL` to the frontend Cloud Run
  service (`infra/gcp/cloud-run-frontend.tf`) via Secret Manager, server-side only — never exposed
  to the browser bundle (F-R9). *(Tracked here for completeness; delivered as its own infra PR.)*
- **FR-F2 (baseline migration — review #6-B1, failure-first).** THE SYSTEM SHALL create the engine
  schema from a **baseline migration** before applying `0001–0004`: **no existing migration creates
  any table** (verified — `drizzle/0001–0003` contain zero `CREATE TABLE`, ALTERs only), so a fresh
  Postgres fails at `0001` ("relation does not exist") before any seed runs. The runner's inventory
  and order is: `0000_engine_baseline.sql` (CREATE TABLEs for the 12 engine tables, generated
  one-time from `schema.pg.ts`) → `0001–0004` → content-seed reconciliation (Track G).
- **FR-F3 (the `DATABASE_URL` side effect — review #6-B1 amplifier, failure).** IF `DATABASE_URL` is
  bound to the frontend service THEN the thread and coach-marker repos **auto-switch to Postgres**
  (`selectThreadRepo` — `server_composition.ts:55`; `selectCoachMarkerRepo` — `marker_repo.ts:14,114`)
  — THE SYSTEM SHALL therefore ensure the threads + coach-marker tables are also created/migrated by
  the same runner **before** the bind, or the ADR-0034 tombstone hole opens (Pg on un-migrated tables
  silently strips data). Binding the engine URL is NOT engine-scoped; the runner covers **all
  frontend-owned tables**, excluding LangGraph checkpoint tables.

### Track G — Server-side content seeding (prerequisite for Track A)

> **Hidden dependency (verified 2026-07-22).** The reviewed bank (**987 items** — `grep -c '"id":'`
> on `_test_item_bank.ts`; the "171" in `frontend/scripts/validate_s3_bounded_session.ts:69,448`
> is a STALE pre-Gen2 comment, worth a cleanup) + taxonomy + hints + lessons + content strings
> exist ONLY as a hardcoded TS array seeded into `InMemoryEngineDb` at runtime
> (`frontend/lib/adapters/engine/_test_item_bank.ts` → `seedTestItemBank` →
> `composition_engine_browser.ts:265`). Migrations are `ALTER TABLE` only — **zero INSERTs**. A
> fresh Postgres has EMPTY content tables, so the durable engine can serve **no questions** until
> the bank is loaded server-side. This gates Track A. (The 987-vs-171 distinction only affects when
> FR-E3's content-fresh-exhaustion fallback triggers — at 987 it is a rare correctness path, not a
> common one.)

- **FR-G1 (multi-source — corrected review #4).** THE SYSTEM SHALL load the reviewed content bank
  into the engine Postgres before the durable engine serves learners, from **all authoritative
  sources**, NOT the item JSON alone. Verified: the live seed is assembled from **≥5 separate
  sources** — `test_item` (`_test_item_bank.ts`, the 987-item promoted JSON), `hint` (`_hint_bank.ts`),
  `tutorial`/`content_string` (`seedLessonContent`), `skill` (`seedDevTaxonomy`), and `test_blueprint`
  — surfaced via `composition_engine_browser.ts` (`seedTestItemBank`/`seedHintBank`/`seedLessonContent`/
  `seedDevTaxonomy`). The emitter/seed mechanism SHALL enumerate every one; an items-only emitter
  leaves taxonomy/hints/tutorials/content/blueprints empty and the engine serves broken items.
- **FR-G2 (reconciliation, not insert-only — corrected review #4).** THE SYSTEM SHALL keep the seeded
  Postgres content **in sync with** the promoted sources of truth via **transactional upsert /
  reconciliation** (`ON CONFLICT DO UPDATE`, keyed by each table's natural id), NOT `ON CONFLICT DO
  NOTHING` — the latter ignores *changed* content, so a re-emit of a corrected item/hint/tutorial
  would silently fail to propagate (the exact drift FR-G2 exists to prevent). **Removal behavior
  (decided — review #6): RETIRE, never hard-DELETE.** A row dropped from the source is soft-retired
  (`reviewed = false` — it stops being servable because selection filters on `reviewed`), NOT deleted:
  `attempt.question_id` carries `onDelete: "cascade"` (`schema.pg.ts:230-231`), so a hard DELETE of a
  question **cascades-deletes the learner's attempt history** — destroying the exact durable record
  this spec exists to keep. The schema forces retire; it is not a style preference.
- **FR-G3 (failure).** IF the engine content tables are empty when a learner opens a session THEN
  THE SYSTEM SHALL surface an explicit "no content available" state — it SHALL NOT present an
  empty or broken quiz as though content existed.
- **FR-G4.** THE SYSTEM SHALL leave the learner *write* tables (`quiz_session`, `attempt`,
  `skill_state`, `progress_point`) starting empty per learner — these are populated by activity,
  not seeded (correct/expected, not a gap).

## 4. Data model / contracts

- **No new tables. TWO new nullable columns** in migration `0004` (corrected — plan rounds 2-4;
  earlier drafts said "one"): (1) **`quiz_session.current_question_id`** (nullable uuid) — the durable
  *current served question* pointer for resume (FR-B3a), 1:1 with a session, cleared on close, the
  durable replacement for RAM `ActiveQuizPointer.questionId`; (2) **`attempt.idempotency_key`**
  (nullable uuid) + a **partial unique index** `(session_id, question_id, idempotency_key) WHERE
  idempotency_key IS NOT NULL` — the atomic attempt-idempotency guarantee (FR-A9.1; the `WHERE` lets
  legacy NULL-key rows coexist). Reuses the other 12 engine tables unchanged; `attempt.resolution`
  (migration `0003`) already carries the first-try-miss signal.
- **Dual-dialect parity (non-negotiable).** The engine rule is that pg and sqlite schemas stay
  **column-identical** (`schema.parity.test.ts`). So `0004` is not just the pg `ALTER`: the plan
  MUST add the same `current_question_id` column to **`schema.sqlite.ts`** AND to the `QuizSession`
  wire entity (`wire/engine_entities.ts`), or the parity test fails and the in-memory/unit path
  drifts from pg. (The sqlite path is what the Vitest unit suite runs against — see §8.)
- **`EngineDb` gains exactly TWO new methods** (count history: "~31" → 30 at review #2 → **31** at
  review #6, each corrected against the interface): (1) `setSessionCurrentQuestion(sessionId,
  questionId)` (write, on serve — FR-B3a); (2) `getNewestOpenSession(subject, learnerId)` (read —
  FR-B1/B2; required because `getSession(id)` needs an id the cross-device client doesn't have and
  `listClosedSessionsByLearner` excludes open rows, `engine_db.ts:113-114`). The pointer **read** is a
  *field* on the session shape, not a method. So: 29 existing + 2 new = **31**, implemented in all
  three impls (`drizzle_engine_db`, `in_memory_engine_db`, sqlite path). (`insertAttempt` also gains
  the in-adapter `.onConflictDoNothing()` idempotency behavior per FR-A9.1 — a behavior change to an
  existing method, not a new one.)
- **New HTTP wire contracts** for `/api/engine/*` — request/response shapes for the coarse
  (D2-shaped) endpoints. Because the swap is atomic (FR-A4), the endpoint set must cover **read**
  screens too, not just quiz submit — otherwise dashboard/summary/progress fan out chattily or
  break. Proposed coarse set (finalized at plan time):
  - **Quiz (write + hot-path):**
    - `POST /api/engine/session/open` → `insertSession`, returns the session id (**the open-write,
      split out so bootstrap is a pure read** — corrected review #2: a `GET` that opens a session
      would be a side-effecting GET, the smell the plan fixed for `session/current`).
    - `GET  /api/engine/quiz/bootstrap?session=<id>` → session + current item + hint ladder, **pure
      read** (the session already exists — open or resume).
    - `POST /api/engine/attempt` → persists an attempt (idempotent via the in-adapter
      `.onConflictDoNothing()` on `idempotency_key`, FR-A9.1), returns the stored `Attempt`.
    - `POST /api/engine/skill-state` → upserts skill_state (Scheduler write path).
    - `GET  /api/engine/next` → next scheduled item honoring content-fresh eligibility (FR-E).
    - `POST /api/engine/session/close` → close with tally (FR-C1).
  - **Resume:** `GET /api/engine/session/active` → newest open session + its stored
    `current_question_id` (FR-B3b). Plus the **serve-time write**: the served pointer is updated
    when a question enters `answering` — either folded into `GET /api/engine/next` /
    `quiz/bootstrap` responses' side-effect, or a dedicated `POST /api/engine/session/current`
    (finalized at plan time). This is an **extra write on the serve hot path** (see §7).
    **Preference (plan-time):** a dedicated `POST /api/engine/session/current` keeps REST honest —
    no side-effecting `GET`. Folding the write into the `next`/`bootstrap` serve response saves a
    round-trip but makes those GETs mutate; choose the POST unless the round-trip cost measurably
    hurts (§7 says the pointer write is fire-and-forget, so the extra call is off the render path).
  - **Reaching the coarse read endpoints (review #1 — load-bearing):** these endpoints are NOT
    `EngineDb` methods, so swapping only the `EngineDb` instance does NOT route the read hooks' repo
    calls into them — the hooks (`use_summary.ts:145-153` calls 6 repos) would fan out per-repo.
    A **coarse client/loader seam** (an `EngineClient` port above `EngineDb`, or per-screen coarse
    loaders) is required; the 3 read hooks + the scheduler entry are rewired to call it (FR-A6 revised).
  - **Dashboard/progress (read, coarse):** `GET /api/engine/dashboard` → session history
    (`listClosedSessionsByLearner`) + skills + skill_state + misses in one call (today 5 separate
    reads at `use_dashboard.ts:143-156`).
  - **Summary (read, coarse):** `GET /api/engine/summary?session=<id>` → session + attempts +
    skill_state + skills + misses (today **6** parallel reads at `use_summary.ts:145-153`:
    `get`, `listSkillState`, `list`, `misses`, `servedQuestionIds`, `listForSession`).
  - **Skill-detail (read, coarse):** `GET /api/engine/skill/<id>` → tutorial + skill_state +
    misses + accuracy in one call.
  These are **new** and must forward no SDK types (A4/F-R8); shapes live in `wire/`.
  - **Fine-grained fallback:** the full `EngineDb` surface (FR-A4) is still callable — the coarse
    endpoints are the hot-path optimization; any method not folded into a coarse call routes to a
    thin per-method handler so no screen surprise-fails (the anti-chattiness discipline, §7).
- **`learnerId`** is the WorkOS `user.id`, re-derived server-side (`resolve_learn_identity.ts`);
  never accepted from the client body.
- **No trust-kernel type change** → no re-signing trigger.

## 5. Invariants & security boundaries

| Invariant / rule | How it holds |
|---|---|
| **F-R9** (BFF no cloud creds) | `DATABASE_URL` lives **server-side** in the Route Handler / `serverPortBag()`, never the browser/edge bundle — the established threads precedent. Browser bundle keeps only public config. |
| **F-R4 / B6** (Route Handlers are composition adapters) | `/api/engine/*` handlers do auth → derive learnerId → call `pgEngineDb`; no domain `if` logic. |
| **A4 / F-R8** (no SDK type escapes) | `HttpEngineDb` returns `wire/engine_entities` shapes; `pg`/Drizzle stays inside the server adapter. |
| **C1 / C2** (composition-root-only) | A **standalone `engineDb()` seam function** (corrected review #2 — mirrors `coachMarkerRepo()` at `server_composition.ts:71`, NOT a param inside `serverPortBag()`, which returns a thread/chat `PortBag`); it calls `selectEngineDb(env)` → `pgEngineDb`. No other file names the concrete engine DB. |
| **A2 (client-supplied identity)** | learnerId re-derived server-side (FR-A2), never trusted from the client. |
| **New abstraction (G1)** | `HttpEngineDb` is a new adapter — the plan/ADR states what it buys (durable cross-device engine via the existing seam) and the rejected simpler thing (D3 resume-snapshot; direct D2 rewrite). |
| **New BFF route family + server-engine seam (⚠️ Ask-first)** | Raises an ADR at plan time (new cross-process data surface). |

## 6. Edge cases

- **Concurrent devices:** same learner answering on two devices against one open session — last
  durable write wins; resume reads newest state. (Multi-device *simultaneous* play is not a target
  use case; must not corrupt, but no merge logic required.)
  - **Duplicate attempts:** two devices each submitting the same Q5 create two `attempt` rows for
    the same `(session, question)`. This is **tolerated in history** (append-only, no corruption),
    but the stored score tally (`score_correct`/`score_total`) could **double-count** if both
    writes land. Plan-time choice (§10): the close tally **dedups by `question_id`** (count each
    question once — the honest fix), OR accepts the bounded over-count as v1 slop. **Prefer the
    dedup** — the summary already derives per-question outcomes from `listSessionAttempts` grouped
    by `question_id` (`countSessionOutcomes` in `session_summary_vm.ts:70`), so the same
    group-by-question is the natural tally source and avoids the double-count at its root.
- **Optimistic verdict vs. failed write** (FR-A8): grade shown, write fails → error state, no advance.
- **Served-but-unsubmitted resume** (FR-B3a): learner opens Q4, leaves before submit → no attempt
  row exists, yet resume must land on Q4 via the stored `current_question_id`, not a scheduler
  re-pick. This is the case position-from-attempts alone gets wrong.
- **Stale question id on resume** (FR-B5): the stored `current_question_id` no longer resolves →
  fresh session, no fabricated progress (FR-B5 covers this for the served-pointer too).
- **NULL served pointer on resume** (FR-B8): pointer write failed (§7 fire-and-forget) or pre-`0004`
  row → resume position **re-derived via a scheduler pick scoped by FR-B9 (exclude answered) +
  FR-E1 (content-fresh)** — "next" is not derivable from attempts alone (no `next_question_id`
  column), so the scheduler is the only source; the scoping keeps it from re-serving an answered
  question. Zero attempts → first scheduled question. Distinct from FR-B5 (stale-but-*present* id):
  FR-B8 is the *absent* id case, and distinct from FR-B3a/FR-B3b which honor a *present* pointer
  without re-deriving.
- **Served-set lost on reload** (FR-B9): RAM `servedIds` dies on reload; without reconstruction the
  scheduler re-serves an already-answered question. Rebuilt from attempt history on resume.
- **Running score not on the open session row** (FR-B10): `score_correct`/`score_total` are 0 until
  close, so resume tallies from attempts server-side.
- **Retried submit** (FR-A9.1): network blip → client resubmit → idempotent, one attempt row, no
  score inflation (write-side twin of the §6 concurrent-device duplicate case).
- **Pointer/attempt disagreement:** if `current_question_id` points at a question that *does* have
  **any recorded attempt** (a row in `attempt` for this session + question — resolving OR not),
  resume advances to the next served question rather than re-showing it. The predicate is **"any
  recorded attempt exists," NOT "a *resolving* attempt exists"** — this is load-bearing: a first-try
  **wrong** answer still in the coached loop has a *non-resolving* attempt row, and per
  FR-B3-feedback the learner must **advance**, not be re-shown the mid-coaching question. Only a
  question with **zero** attempt rows (served-but-never-submitted, FR-B3a) is re-shown.
- **Exhausted pool mid-session** (FR-C5): graceful close to summary at count reached.
- **Zero-miss completed session** (FR-D4): explicit clean-sweep state.
- **Skill with no on-skill attempts** (FR-D5): omit from strong/weak panel (AP-6), never 0%.
- **Content-fresh pool empty** (FR-E3): fall back to full-bank FSRS adaptive.
- **Coached-correct vs walked-through eligibility** (FR-E1): coached-correct (`correct=true`) leaves
  the preferred pool; walked-through (`correct=false`) stays — the `correct===true` predicate
  handles both without a resolution-aware special case.
- **E1 before durable store:** eligibility cannot be honored on the in-memory store (no
  cross-session correct-history) — E1 is inert until Track A + G land (hard dependency, FR-E4).
- **Legacy in-flight session** at cutover: no durable rows exist pre-launch → first mount opens a
  fresh session (no phantom resume).

## 7. Non-functional requirements

- **Latency:** every answer submit + next now involves a server round-trip (inherent to durable
  cross-device). Mitigated by **optimistic verdict** (FR-A7) + **one-ahead lookahead** prefetch
  (DEC-5) for the *next* question. No fixed p50 target set this spec; measure post-cutover.
- **Determinism:** grading stays deterministic and identical client/server (safe optimistic UI).
- **Reversibility:** D1 keeps the `EngineDb` seam, so a later D2 refactor moves call sites, not data.
- **No live LLM** on any path here (pure data plumbing) — nothing new on the CI hot path.
- **Chattiness:** the API is designed **coarse (D2-shaped)** — hot paths (`bootstrap`, `attempt`,
  `next`, `session/active`) AND read screens (`dashboard`, `summary`, `skill`) are single calls,
  not port-for-port fan-out (§4). This matters because the atomic swap (FR-A4) puts *every*
  `useEngine()` screen on the network at once, so the read screens' multi-read loads
  (dashboard ~5, summary 6) must collapse to one call each or their latency regresses visibly.
- **Optimistic-UI rollback (plan-time detail):** FR-A7/A8 fix the FR level — write-fail → error +
  no advance. Whether the shown verdict *rolls back to "unanswered"* vs. holds behind an error
  banner is a plan-time UX decision, not an FR (noted in §10).
- **Served-pointer write cost (FR-B3a):** the durable served pointer adds one write per question
  *served* (not just per submit). It is non-blocking to the render (fire-and-forget, like today's
  RAM `setActiveQuiz`) — a failed pointer write must NOT block the learner from seeing the
  question; worst case is a slightly stale resume position, never a broken serve. If folded into
  the `next`/`bootstrap` response it costs no extra round-trip.

## 8. Test plan

Failure-path tests before happy-path. Frontend tests are Vitest (node, seeded `InMemoryEngineDb`
or MSW-mocked BFF); the pg seam is proven by a full-stack persistence probe (manual/on-demand,
like the existing `db-persistence-probe.spec`).

| FR | Test | Layer | In gate? |
|----|------|-------|----------|
| FR-A1 | `frontend/.../api/engine/*.test` — no session → 401, no DB touch | L1 | yes |
| FR-A2 | handler ignores client `learnerId`, uses session id | L1 | yes |
| FR-A2a | learner A's session cannot READ learner B's session/attempts (cross-learner isolation, not just body-id-ignore) → empty/404 | L1 | yes |
| FR-A3 | unset `DATABASE_URL` → typed error, no in-memory silent fallback | L1 | yes |
| FR-A4 | `HttpEngineDb` satisfies `EngineDb` (30-method conformance); write/quiz call sites unchanged | L1 | yes |
| FR-A6 (coarse seam) | the 3 read hooks + scheduler entry call the coarse client/loader (NOT per-repo fan-out); `EngineDb` write consumers unchanged | L1 | yes |
| §7 coarse-read | dashboard/summary/skill each resolve in ONE BFF call (guards the FR-A4 atomic-swap chattiness regression — read screens must not fan out port-for-port) | L1/L2 | yes (unit) |
| FR-A5 | submit → attempt row persisted (against seeded pg in probe; mocked in unit) | L1/L2 | yes (unit) |
| FR-A9.1 | retried attempt POST (same `idempotency_key`) → ONE row via in-adapter `.onConflictDoNothing()` (NOT a handler PG-error catch), score not inflated; coached retry (new key) → new row | L1 | yes |
| FR-A9.2 | transient 5xx on idempotent read → retried w/ backoff; non-idempotent write fail → FR-A8 error, not silent drop | L1 | yes |
| FR-A7/A8 | optimistic verdict shown; write-fail → error state, no advance | L1 | yes |
| FR-B1/B3 | mount with open session → resume at position + score | L1 | yes |
| FR-B3a | served-but-unsubmitted (open Q4, no submit) → `current_question_id` written on serve | L1 | yes |
| FR-B3b | active read returns stored current question, not a scheduler re-pick | L1 | yes |
| FR-B3c | pointer advances on next serve; cleared on close | L1 | yes |
| FR-B3a-nonblock | pointer write FAILURE does not block the serve — question still renders; worst case = stale resume position, never a broken serve (§7 NFR) | L1 | yes |
| FR-B3-feedback | resume advances (not re-show) for **any recorded attempt**: (a) first-try correct [resolving], AND (b) first-try wrong still in coached loop [**non-resolving** attempt row]; only zero-attempt is re-shown | L1 | yes |
| §4 parity | `schema.parity.test.ts`: `current_question_id` present in BOTH pg + sqlite (and `QuizSession` wire) | L1 | yes |
| FR-B2 | newest `ended_at IS NULL` chosen; old open session still resumes | L1 | yes |
| FR-B4 | resume reads by learnerId (device-agnostic) — persistence probe | L2 | on-demand |
| FR-B8 | NULL `current_question_id` → re-derive via scheduler pick SCOPED by FR-B9 (exclude answered) + FR-E1 (content-fresh); the pick never returns an already-answered question; zero attempts → first scheduled question | L1 | yes |
| FR-B9 | resume rebuilds served-set from attempt history → scheduler does NOT re-serve an already-answered question (Q1–Q29 answered, resume, next ≠ any of Q1–Q29) | L1 | yes |
| FR-B10 | resume running score = server-side **unique-first_try / unique-resolved** (commit-first), NOT all-resolving-correct; matches the live reducer tally exactly (a coached-correct does NOT bump the resumed numerator); session row score is 0 while open; not client-re-tallied | L1 | yes |
| FR-B5 | stale question id → fresh session, no fabricated score | L1 | yes |
| FR-B6 | `?mode=review`/`?focus=` → fresh, not resume | L1 | yes |
| FR-B7 | completed session never resumed | L1 | yes |
| FR-C1/C2 | 30th item resolves → auto persist+close+route to summary; no Q31 | L1 | yes |
| FR-C1a | wrong first answer on Q30 → stays in coached loop, closes only on resolution (not first grade) | L1 | yes |
| FR-C3 | no "Keep practising" past target | L1 | yes |
| FR-C4 | new practice after completed → fresh Q1 session | L1 | yes |
| FR-C5 | pool exhausted mid-session → graceful summary, no throw | L1 | yes |
| FR-C6 | endless `target_count=null` still valid for non-default callers | L1 | yes |
| FR-D1 | misses list from THIS session's attempts (not global misses()) | L1 | yes |
| FR-D1a | walked-through item appears in the misses list | L1 | yes |
| FR-D2 | strong/weak panel projected from this-session listSessionAttempts (not last-N accuracyBySkill) | L1 | yes |
| FR-D3 | summary values from stored data, no re-tally | L1 | yes |
| FR-D4 | zero-miss → clean-sweep empty state | L1 | yes |
| FR-D5 | no-attempt skill omitted, not 0% | L1 | yes |
| FR-E1 | exclude latest correct===true; coached-correct excluded, walked-through kept | L1 | yes |
| FR-E1a | eligibility layers over FSRS pick; within-session servedIds still applies | L1 | yes |
| FR-E2 | misses (incorrect + walked-through) stay eligible | L1 | yes |
| FR-E3 | pool empty → FSRS full-bank fallback | L1 | yes |
| FR-E4 | eligibility is a cross-session read-only projection (no skill_state write); depends on A+G | L1 | yes |
| FR-E5 | `mode=review` unchanged | L1 | yes |
| FR-F1 | Terraform: frontend service gets `DATABASE_URL` secret (plan review) | n/a | infra PR |
| FR-G1 | seed loads ALL sources (items+skills+hints+tutorials+content+blueprints) into pg; per-table row counts match each source (not items-only) | L2 | on-demand |
| FR-G2 | re-emit of a CHANGED row → durable store UPDATED (`ON CONFLICT DO UPDATE`, not DO NOTHING); dropped-source row → soft-retired `reviewed=false`, NEVER hard-deleted (FK cascade would destroy attempt history); no drift | L2 | on-demand |
| FR-G3 | empty content tables → explicit "no content" state, not broken quiz | L1 | yes |
| FR-G4 | write tables start empty per learner (expected) | L1 | yes |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test that was *seen to fail first* (red/green).
- [ ] `make check` green (lint + format-check + pyright/tsc + test).
- [ ] `tests/architecture/` green — F-R9, F-R4, A4/F-R8, C1/C2 unbroken (frontend layering gate).
- [ ] ADR appended for the new BFF engine-route family + server-engine seam (⚠️ Ask-first); the
      `HttpEngineDb` new-abstraction (G1) states what it buys + the rejected simpler options.
- [ ] Engine persistence proven end-to-end at least once (persistence probe against seeded pg) —
      durability is currently unproven (design doc §4).
- [ ] Actual command output pasted (not summarized) for the verification claims.

---

## 9a. Track sequencing (carries into the plan/task ordering)

Derived from the FR-level dependencies (not a schedule, an ordering constraint):

```
G (seed content) + F (DATABASE_URL wiring)   ── prerequisites, parallel to each other
        │
        ▼
A (HttpEngineDb full surface + BFF /api/engine/*)   ── the atomic swap; nothing durable before it
        │   └── G3 (empty-content guard) lands WITH A — a defensive path, not seeded data, so a
        │       not-yet-seeded prod shows an honest "no content" state instead of a broken quiz.
        │       This de-risks the F+G→A ordering: A never ships a broken surface even if seed slips.
        ▼
B / C / E   ── all need A's durable seam (E also needs G per FR-E4)
        │   └── within this group, C is first: bounded-30 auto-close PRODUCES the completed
        │       sessions that B must-not-resume (FR-B7) and D summarizes.
        ▼
D (enriched summary)   ── consumes the durable session/attempt data C closes and A writes
```

Notes:
- **A is all-or-nothing** (FR-A4 atomic swap): the full `EngineDb` surface + a place for content
  (G) must land together, or non-quiz screens break. B (resume) is a *capability* that can be the
  first user-visible feature, but it cannot ship on a partial durable bag.
- **G3 before a full prod seed** is the key insight — the empty-state guard is cheap, defensive,
  and removes the "seed must be 100% done before A ships" coupling.

## 10. Open items to resolve at plan time

- **Cutover/flagging: RESOLVED (plan §6).** Flag-gated (shadow → canary), coach-v3 flag precedent.
- **Seed data in prod: RESOLVED → Track G.** Verified: the bank exists ONLY in the in-browser TS
  seed; a fresh Postgres has empty content tables and can serve no questions. Track G (FR-G1..G4)
  now owns this prerequisite. **Mechanism + timing RESOLVED (plan §6, review #4/#6):** multi-source
  SQL emitter with `ON CONFLICT DO UPDATE` reconciliation + retire-not-delete; runs alongside Track A,
  decoupled by the G3 empty-content guard; ordered after the FR-F2 baseline migration.
- **Coarse endpoint set: RESOLVED (plan §5).** `session/open` + pure-read `bootstrap`, `attempt`,
  `next`, `session/current`, `session/active`, `session/close`, `skill-state`; reads `dashboard`,
  `summary`, `skill/[id]`; per-method disposition incl. the four server-only content writes (FR-A4).
- **Optimistic-UI rollback UX: RESOLVED (plan §6).** Hold behind an error banner; no
  rollback-to-unanswered.
- **Concurrent-device duplicate-attempt tally: RESOLVED (plan §6).** Close tally dedups by
  `question_id` (reuses the `countSessionOutcomes` group-by), with the FR-B10 first_try-only
  numerator; server-side, client tallies ignored.
- **Attempt-POST idempotency mechanism (FR-A9.1): RESOLVED (plan §6 dec-4, review #2/#5).** Client
  `idempotency_key` + partial unique index, idempotent insert **in the DB adapter**
  (`.onConflictDoNothing()`). Natural-key `(session_id, question_id, created_at)` **rejected**:
  `created_at` is server-assigned so a retry can't match it; and `pgEngineDb` wraps errors opaquely so
  a handler can't catch the unique-violation. No longer open.
- **Served-set reconstruction shape (FR-B9): RESOLVED (plan §6).** Scope the scheduler query
  `NOT IN` the session's attempted ids, owned by the `next` handler server-side; `session/active`
  does not return a served-set.
- **Feedback-phase restore (deferred, post-v1):** FR-B3-feedback locks v1 to *advance-to-next* on
  mid-feedback abandonment (durable surface = one column). A later increment could persist
  `phase`/`verdict`/`answeredLetter` to restore the feedback/coached screen exactly — that widens
  `0004` beyond one column and the served-pointer write path, so it is out of this spec's scope.
- **Ship ordering within the atomic swap:** see §9a. The `EngineDb` swap is all-or-nothing
  (FR-A4); B (resume) is the first user-visible capability but can't ship on a partial durable bag.
  G3 (empty-content guard) lands with A so the seed timing (SQL emitter vs. data-migration; before
  vs. alongside A) stays decoupled from A shipping — a not-yet-seeded prod degrades honestly.
