# Plan — Coach V3 Durable Learner Engine

> The *how* for [coach-v3-durable-progress.spec.md](coach-v3-durable-progress.spec.md) (~58 FRs,
> 7 tracks, APPROVED 2026-07-22). Architecture + file-level touchpoints + migration steps, derived
> from the clarified spec AND the constitution (root 8 invariants + Frontend Ring F-R1..F-R9). The
> *why* for the load-bearing choices lives in **ADR-0038** (raised by this plan; §7 below).

**Status:** APPROVED (re-approved 2026-07-22 after review rounds 5–6) + ADR-0038 accepted; tasks
regenerated same day. The **Replan log** below records what rounds 5–6 changed and why.

> ## Replan log — 2026-07-23 (Stage 5, post-implementation code review)
> The end-to-end code review (`coach-v3-end-to-end-code-review.canvas.tsx`, verdict REJECT) found
> 2 Critical, 4 High, 3 Medium findings across the shipped phases. Direction (D1/Shape B) is
> **unchanged**. Routing: 2 findings are minor scope additions → spec change (Stage 2) → back
> through tasks (Stage 3); 7 are implementation/test gaps against existing FRs → new fix tasks.
> **Phase R (Reconvergence)** appended to `tasks.md` with T R.1–R.10, ordered by merge risk.
>
> 1. **Critical — EngineDb dispatcher IDOR (finding 1, FR-A2a/A2).** The fine-grained
>    `/api/engine/db/[method]` dispatcher substitutes learner IDs for only seven read methods and
>    never calls `requireOwnedSession`, so one learner can target another's session/state. Fix
>    (T R.1): centralize per-method authorization — force embedded `learner_id` to the
>    server-derived id, resolve session ids, `requireOwnedSession` before every session-scoped
>    dispatch, cross-learner tests for each.
> 2. **Critical — Cloud SQL migration/runtime connector (finding 2, FR-F1/F3).** The deploy host
>    passes a `/cloudsql` socket DSN to Node without Cloud SQL Proxy; the frontend service lacks
>    the socket volume/mount + `cloudsql.client` grant; the `database-url` secret is in
>    `+asyncpg` format (incompatible with `pg`). Fix (T R.2): run migration through Cloud SQL Proxy
>    or a connector-enabled job, add the volume/mount + IAM, fix the secret format.
> 3. **High — Q31 can be served (finding 3, FR-C2).** A failed close or reload lets the open
>    session resume through `/next`, which never compares the server tally to `target_count`. Fix
>    (T R.3): enforce the boundary in `/next` AND durable resume; page-level final guard.
> 4. **High — Phase Z overstates end-to-end durability (finding 4, DoD §9).** The probe's
>    submit/resume steps use raw SQL (bypassing `HttpEngineDb` + BFF + auth + ownership); the
>    Playwright companion has no pasted green run. Fix (T R.6): rewrite steps d/e through the real
>    app layers and paste a verbatim green Playwright run. DoD "end-to-end" tick downgraded to
>    **conditional** until R.6 passes (spec §9.2).
> 5. **High — Empty source can wipe the reviewed bank (finding 5, FR-G2a — NEW).** A corrupt/empty
>    promoted source drives a blanket `reviewed=false` update, retiring all servable content with
>    no destructive intent. **Scope change → spec:** new FR-G2a (fail-closed on empty/regressed
>    source unless `--force-empty-<source>`; per-source count ratchet). Fix (T R.4).
> 6. **High — No durable-engine flag in the production bundle (finding 6, FR-A4/§6).**
>    `NEXT_PUBLIC_FF_DURABLE_ENGINE` is build-time but Docker/Terraform don't pass it; deployed
>    browsers stay on `InMemoryEngineDb`. Fix (T R.5): add the build arg + deployment var, OR
>    document intentional OFF + build a flag-on image for the gate.
> 7. **Medium — Inconsistent per-question dedup (finding 7, §6 tie-break — clarified).** Tally
>    keeps first-resolving, summary keeps latest; same-`created_at` rows ambiguous. **Scope
>    change (minor) → spec:** §6 "Per-question resolution order" = greatest `created_at`, ties by
>    greatest `id`, reused by FR-B10/D1/D2/E1. Fix (T R.7): one `resolvingAttemptForQuestion`
>    helper across all four consumers.
> 8. **Medium — Seed emitter duplicates 4 sources in Python (finding 8, FR-G1).** Skills/tutorials/
>    content/blueprints are copied into Python constants, so TS source changes drift. Fix (T R.8):
>    extract from canonical TS at emit time, or add a parity architecture test.
> 9. **Medium — Core production seams lack integration tests (finding 9, §8).** Dispatcher
>    ownership, close-route tally + pointer clearing, coarse summary hydration, migration
>    replay/rollback, partial-index `insertAttempt` through real pg are untested. Fix (T R.9).
>
> **Phase R ordering:** R.1 (trust seam) first — nothing in R merges before it. R.2/R.4/R.5/R.8 may
> parallelize (independent infra/seed surfaces) once R.1 lands. R.6 depends on R.2 + R.5. R.10 is
> the final gate. Existing Phase 0/G/F/4/A/B/C/D/E/Z tasks stay as committed; Phase R is
> append-only. Spec additions: FR-G2a + §6 per-question resolution-order tie-break (both
> propagated backwards before the task list, per Stage-5 routing).
>
> ## Replan log — 2026-07-23 (Stage 5, post-R.1–R.9 three-lane subagent review)
> The post-implementation review (BFF trust / DB-deploy / client-runtime lanes) found Phase R
> closed the dispatcher IDOR and landed most reconvergence, but merge was still blocked by 5
> residual risks. **No spec change** (all are implementation/infra/NFR gaps against existing FRs);
> the approved decomposition appends R.10a + R.11–R.15 + R.10c to `tasks.md` (R.10 split into
> R.10a catalogue repair + R.10c final gate; R.10b = TAP-4 disposition in `decisions.md`, not code):
> 1. **R.10a — adapter conformance catalogue:** `node_pg_url.ts` orphan in `PAIRS` (the one real
>    gate red). 2. **R.11 — `/next` eligibility tie-break:** prod path still `created_at`-only SQL;
>    align with the §6 `id` tie-break from R.7. 3. **R.12 — closed-session reject + transactional
>    close:** late writes after close re-open counts; close tally is non-transactional. 4. **R.13 —
>    pool budget:** uncapped `pg` pools vs Cloud SQL `max_connections=50`. 5. **R.14 — deploy guard:**
>    flag ↔ image digest can diverge; counts ledger + seed_sources off-CI. 6. **R.15 — probe strength
>    + coarse GET retry:** probe proves id+count, not pointer/score; `EngineClient` GETs lack
>    FR-A9.2 retry. R.11 depends on R.7; R.12 on R.3; R.15 on R.6; R.10c is the final gate.

> ## Replan log — 2026-07-22 (Stage 5, review round 5)
> Six issues found at pre-implementation review, all validated against code. Direction (D1/Shape B)
> is **unchanged**; these correct *premises within it*. Routing: #1 + #3 change FRs → spec change →
> back through Stage 2 (spec → plan → ADR → tasks), one human gate.
>
> 1. **Coarse API was unreachable (design error).** Swapping only the `EngineDb` instance leaves the
>    read hooks (`use_summary.ts:145-153` calls **6 repos** via `Promise.all`) fanning out per-repo;
>    the coarse `/dashboard`/`/summary`/`/next` endpoints — which are **not** `EngineDb` methods — are
>    never invoked. `FsrsScheduler.next()` also runs client-side, so server-owned `/next` eligibility
>    can't apply without a call-site change. **Resolution (decided with Rajnish): a coarse
>    client/loader seam** the read hooks call; **FR-A6 relaxed** from "all call sites unchanged" to
>    "EngineDb consumers unchanged; the 3 heavy read hooks + the scheduler entry rewired to coarse
>    loaders." This is a real call-site change — the atomic-swap-with-zero-call-site-change premise was
>    wrong for the read screens.
> 2. **Spec carried stale pre-plan decisions** (never back-propagated after plan rounds 2–4): §4
>    "one column" (→ two), FR-A9/§10 natural-key option (→ removed), side-effecting `bootstrap`
>    (→ `POST /session/open` + pure-read bootstrap), `selectEngineDb` in `serverPortBag()` (→ standalone
>    `engineDb()`), method count "~31" (→ **30**: 29 existing + 1 new method; the pointer read is a
>    *field* on `getSession`, not a second method).
> 3. **FR-B10 running-score contradicted commit-first (correctness).** `quiz_screen_reducer.ts:434`:
>    under commit-first, `bumpCorrect = resolution === "first_try"` — only **first-try** correct counts,
>    NOT all resolving-correct. My FR-B10 ("count of resolving-correct attempts") would make a resumed
>    score **higher** than the live score. Fix: server computes **unique questions resolved `first_try`
>    / unique resolved questions**, and `/session/close` computes the same server-side, ignoring any
>    client tally.
> 4. **Seed couldn't satisfy FR-G2.** The promoted JSON is **items-only** (987, verified flat list); the
>    live seed is assembled from **5 sources** (`_test_item_bank`, `_hint_bank`, `seedLessonContent`,
>    `seedDevTaxonomy`, blueprints). `ON CONFLICT DO NOTHING` ignores changed content → drift. Fix: the
>    emitter must enumerate **every** authoritative source and do transactional **upsert/reconciliation**
>    (`ON CONFLICT DO UPDATE`), with defined update/removal behavior.
> 5. **Idempotency handler couldn't catch the unique-violation.** `pgEngineDb` wraps every op's error as
>    `EngineRepoError(stringified)` (`drizzle_engine_db.ts:284-286`), so SQLSTATE 23505 is lost. Fix:
>    move the idempotent insert **into the DB adapter** — `insertAttempt` uses `.onConflictDoNothing()`
>    on `attempt_idempotency_uq` (the `upsertSkillState:660` precedent) and returns a typed
>    already-existed result; the handler never string-matches a PG error.
> 6. **Cross-artifact:** FR-D3 "never re-tally on client" vs. panels computed in `session_summary_vm.ts`
>    → scope to "headline score + eligibility are server-derived; presentational panels may project from
>    server-supplied rows." Track B must carry the pointer-vs-attempt disagreement (§6). ADR-0034
>    migration-runner tombstone must be closed by Track F. ADR index/log still say "proposed" + "one
>    column" → update. Tasks inherit all of the above → regenerate after spec+plan land.
**Owner:** Rajnish Khatri
**Spec:** [coach-v3-durable-progress.spec.md](coach-v3-durable-progress.spec.md) · **Design:** [coach-v3-durable-progress.brainstorm.md](coach-v3-durable-progress.brainstorm.md)

---

## 1. Architecture in one picture

The whole feature turns on **one seam swap**: the browser today builds its `EnginePortBag` from a
fresh `InMemoryEngineDb` per page load; we make that `db` instance a network-backed `HttpEngineDb`
that calls new BFF `/api/engine/*` Route Handlers, which run the already-built `pgEngineDb`
(`drizzle_engine_db.ts`) server-side against Postgres. The `EngineDb` **write/row-level consumers**
— the 13 repos, `use_quiz.ts`'s submit path — are unchanged; the **3 heavy read hooks + the scheduler
entry are rewired** to a coarse client seam (FR-A6 as revised at review round 5 — the original "every
screen unchanged" claim was refuted; see the Replan log and the next paragraph).

```
 BROWSER                          BFF (Node Route Handler, server-side)      POSTGRES
 ┌──────────────────────┐        ┌────────────────────────────────────┐    ┌──────────┐
 │ useEngine() screens   │        │ /api/engine/* handlers             │    │ 12 engine│
 │  quiz / dashboard /   │        │  1. WorkOS session verify (401)    │    │  tables  │
 │  summary / skill /    │        │  2. derive learnerId server-side   │    │ +0004 col│
 │  coach                │        │  3. scope every query by learnerId │    │          │
 │        │              │        │  4. call pgEngineDb (Drizzle/pg)   │    │          │
 │  EnginePortBag        │        └────────────────────────────────────┘    └──────────┘
 │        │              │  HTTPS (WorkOS cookie)      ▲  DATABASE_URL server-side (Shape B,
 │  db: HttpEngineDb ────┼────────────────────────────┘  threads precedent — F-R9 holds)
 │        ▲              │
 │  (was: InMemoryEngineDb, seeded per load) │
 └──────────────────────┘
```

**The atomic swap (FR-A4):** one shared `db` builds the whole bag, so replacing it puts *every*
`useEngine()` screen's **write/row-level** path on the network at once. `HttpEngineDb` implements the
**full 31-method** `EngineDb` surface (29 today + 2 new methods: `setSessionCurrentQuestion`
+ `getNewestOpenSession`; the pointer read is a *field*, not a method — corrected review #2).

**But the read screens don't reach the coarse endpoints through `EngineDb` (review #1 — design fix).**
The coarse `/dashboard`/`/summary`/`/skill`/`/next` endpoints are **not** `EngineDb` methods, and the
read hooks call *several repos* (`use_summary.ts:145-153` = 6 repos via `Promise.all`), so swapping
only the `db` instance leaves them fanning out per-repo — the coarse endpoints are never invoked. So
this plan adds a **coarse client/loader seam** the 3 read hooks + the scheduler entry call, and
**FR-A6 is relaxed**: `EngineDb` write/quiz consumers unchanged; those 4 read paths rewired. See Track
A "coarse read seam" below.

---

## 2. The EngineDb surface (what HttpEngineDb must implement)

The clean network seam is `frontend/lib/adapters/engine/db/engine_db.ts` — **29 methods** today
(`ReadableEngineDb.listSkillState` + 28 on `EngineDb`; 8 writes, 21 reads — verified by count against
the interface), **+2 new = 31** (#30 `setSessionCurrentQuestion`, #31 `getNewestOpenSession` — review
#6-B2: `listClosedSessionsByLearner` *excludes* `ended_at IS NULL` rows, `engine_db.ts:113-114`, so no
existing method finds the resumable session). **Every row has exactly one disposition** (FR-A4
revised): a coarse carrier, a fine-grained route `/api/engine/db/<method>`, or **SERVER-ONLY** —
`HttpEngineDb` throws a typed `EngineRepoError("server-only method")` for rows 7, 9, 11, 13
(`insertQuestion`/`insertHint`/`insertTestItem`/`insertTestBlueprint`): post-swap no browser call site
invokes them (seed moved server-side), and exposing authenticated-learner content-write endpoints
would let any learner mutate the bank. Table (rows 1–29 existing; 30–31 added by `0004`):

| # | Method | R/W | Carried by endpoint |
|---|---|---|---|
| 1 | `listSkillState(subject, learnerId)` | R | dashboard, summary, skill |
| 2 | `listSkills(subject)` | R | dashboard, summary |
| 3 | `getSkillByKey(subject, key)` | R | bootstrap |
| 4 | `listSkillIds(subject)` | R | bootstrap |
| 5 | `nextReviewedQuestion(...)` | R | next / bootstrap |
| 6 | `getQuestion(id)` | R | bootstrap, next |
| 7 | `insertQuestion(q)` | W | (seed — Track G) |
| 8 | `listReviewedHints(...)` | R | bootstrap (hint ladder) |
| 9 | `insertHint(h)` | W | (seed) |
| 10 | `listReviewedTestItems(subject)` | R | (seed/verify) |
| 11 | `insertTestItem(item)` | W | (seed) |
| 12 | `getTestBlueprint(id)` | R | bootstrap |
| 13 | `insertTestBlueprint(bp)` | W | (seed) |
| 14 | `insertSession(s)` | W | bootstrap (open) |
| 15 | `getSession(id)` | R | session/active *(now returns pointer — §4)* |
| 16 | `patchSessionClose(id, patch)` | W | session/close *(FR-C1 — already exists!)* |
| 17 | `listClosedSessionsByLearner(...)` | R | dashboard |
| 18 | `insertAttempt(a)` | W | attempt *(idempotent — FR-A9.1)* |
| 19 | `listMisses(subject, learnerId)` | R | dashboard, summary, skill |
| 20 | `listSessionQuestionIds(sessionId)` | R | next (served-set — FR-B9) |
| 21 | `listSessionAttempts(sessionId)` | R | summary, resume (FR-B10), served-set |
| 22 | `listSessionSkillIds(sessionId)` | R | summary |
| 23 | `accuracyRowsBySkill(...)` → `SkillAccuracyRow[]` | R | skill |
| 24 | `getSkillState(...)` | R | next, skill |
| 25 | `upsertSkillState(state)` | W | skill-state *(retry — FR-A9.2)* |
| 26 | `getContentString(...)` | R | bootstrap |
| 27 | `listContentStrings(...)` | R | bootstrap |
| 28 | `getTutorial(subject, skillId)` | R | skill |
| 29 | `listProgressPoints(subject, learnerId)` | R | dashboard, skill |
| **30** | **`setSessionCurrentQuestion(sessionId, questionId \| null)`** | **W** | **session/current (NEW — FR-B3a)** |
| **31** | **`getNewestOpenSession(subject, learnerId)`** | **R** | **session/active (NEW — FR-B1/B2; newest `ended_at IS NULL` row for the learner)** |
| **+** | **pointer field on `getSession` return (`QuizSession.current_question_id`)** | **R** | **session/active (FR-B3b — a field, not a method)** |

**Note:** `patchSessionClose` (#16) already provides the close-with-tally write FR-C1 needs — no new
close method. The two genuinely new `EngineDb` methods are #30 (`setSessionCurrentQuestion`) and #31
(`getNewestOpenSession`); the pointer read is an added **field** on the existing `getSession`/
`QuizSession` shape, NOT a method. So the count is **29 + 2 = 31** (corrected review #2 — an earlier
draft's "+1 → 30" wrongly omitted `getNewestOpenSession`, and the still-earlier "+2 → ~31" wrongly
counted the pointer *field* as a second method; the table lists both #30 and #31 as methods, so 31 is
correct). `insertAttempt` also gains in-adapter `.onConflictDoNothing()` idempotency (FR-A9.1) — a
behavior change to an existing method, not a new one.

---

## 3. Track-by-track file touchpoints

Ordered per spec §9a: **G+F → A (with G3) → C → B/E → D**. Each track = one or a few PRs.

### Track G — server content seed (prerequisite; ADR-0038 §G part)

| File | Change |
|---|---|
| new `scripts/emit_engine_seed_sql.py` (sibling to `scripts/emit_test_item_bank.py`) | Emit a SQL bundle for **all ≥5 authoritative sources** (corrected review #4 — the promoted JSON is **items-only**, 987 rows): `test_item` ← `_test_item_bank.ts`/`coach-item-bank-live.promoted.json`; `hint` ← `_hint_bank.ts`; `tutorial`+`content_string` ← `seedLessonContent`; `skill` ← `seedDevTaxonomy`; `test_blueprint` ← its source. An items-only emitter leaves taxonomy/hints/tutorials empty → engine serves broken items. Carry the `generated_by` provenance stamp that `test_test_item_provenance_confinement.py` enforces. |
| `frontend/drizzle/000?_seed_*.sql` OR a run-once seed script | The emitted inserts use **`ON CONFLICT DO UPDATE`** (transactional reconciliation, keyed by each table's natural id), **NOT `DO NOTHING`** (review #4 — `DO NOTHING` ignores changed content, failing FR-G2). Rows dropped from source are **soft-retired** (`reviewed=false`), never hard-deleted — the `attempt.question_id` FK cascade would destroy learner history (§6). |
| `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` | (No change — the existing `insert*` methods already write these tables; the seed uses raw upsert SQL.) |

G4 (learner write tables start empty) needs no code — it is the default.

### Track F — DATABASE_URL + engine migration runner (own infra PR — ⚠️ HIGHEST-RISK TRACK)

> **This is not "add a Terraform secret."** Grounding found the engine schema has **no migration
> execution path at all**: (a) `frontend/drizzle.config.ts` is scoped **exclusively to threads** — an
> inclusive whitelist of only `threads` + `thread_messages`, pointing at
> `lib/adapters/thread_store/db/schema.ts`; it does **not** see the engine tables. (b) `drizzle-kit`
> (the migration CLI) is **not in `package.json`** — migrations `0001-0003` are hand-authored ALTER
> files with **no runner that applies them**. So the threads precedent does NOT cover the engine
> schema (different `tablesFilter`, different schema file). Track A's durability is blocked on this.

| File | Change |
|---|---|
| `infra/gcp/cloud-run-frontend.tf` | Add `DATABASE_URL` via Secret Manager, **server-side env only** (F-R9 — mirrors `agent-backend-combined`; the frontend has none). |
| **Engine migration runner (DECIDED — review #6-B4, no more "options")** | **A plain SQL runner: `frontend/scripts/migrate_engine.mjs`** (node + `pg`, no `drizzle-kit` dep), executing each `frontend/drizzle/*.sql` in lexicographic order, one transaction per file, tracked in a `_frontend_migrations` ledger table (filename + applied_at; skip already-applied). **Inventory + order (FR-F2):** `0000_frontend_baseline.sql` (NEW — CREATE TABLEs for the 12 engine tables **+ threads + coach-marker tables**, generated one-time from `schema.pg.ts` + the thread/marker schemas; verified NO existing migration creates any table — `0001-0003` are ALTER-only, zero `CREATE TABLE`) → `0001–0004` → the Track-G seed reconciliation SQL. Excludes LangGraph checkpoint tables (the `drizzle.config.ts` invariant). **Why threads/marker too (FR-F3):** binding `DATABASE_URL` auto-flips `selectThreadRepo` (`server_composition.ts:55`) and `selectCoachMarkerRepo` (`marker_repo.ts:14,114`) to Pg — un-migrated their tables = the ADR-0034 data-stripping hole. |
| **Deploy integration (DECIDED)** | The runner executes as a **pre-traffic deploy step** in the deploy-gcp flow (before the new revision takes traffic, same `DATABASE_URL` secret): `node frontend/scripts/migrate_engine.mjs` — invoked from the deploy recipe/Cloud Build, NOT at app boot (a Cloud Run cold start must never race a migration). The `DATABASE_URL` Terraform bind (FR-F1) merges only WITH the runner wired — that pairing is what closes the ADR-0034 tombstone honestly. |
| **Close the ADR-0034 migration-runner tombstone (review #6)** | ADR-0034 left a tombstone (`tests/architecture/test_coach_marker_durability_tombstone.py`) that goes **red** if `DATABASE_URL` is bound *without* a migration runner (the "Pg on un-migrated table strips answers forever" hole). Track F's runner (above) is exactly what closes it — when the engine `DATABASE_URL` binds, the runner must exist, so the tombstone flips from "green = guarding an unbuilt path" to "the path is built + migrated." Track F must update/retire that tombstone as part of landing the runner (G8 whole-file-delete needs a stub — see memory `dev-tier-stack-retired-adr0031`), NOT leave it asserting a now-false premise. |

### Track A — HttpEngineDb + BFF /api/engine/* (the atomic swap; ADR-0038 §A part)

| File | Change |
|---|---|
| `frontend/lib/adapters/engine/db/http_engine_db.ts` (NEW) | Implements the full `EngineDb` (**31 methods** — 29 + `setSessionCurrentQuestion` + `getNewestOpenSession`) per the §2 disposition: fetch calls to `/api/engine/*` for coarse/fine-grained rows, a typed `EngineRepoError("server-only method")` throw for the 4 content writes. Returns `wire/engine_entities` shapes only (A4/F-R8 — no `pg`/Drizzle type escapes). Retry/timeout policy per **FR-A9.2** (retry idempotent reads w/ backoff; surface non-idempotent write fails per FR-A8). |
| `frontend/lib/adapters/engine/**` — **coarse read seam (NEW — review #1)** | `HttpEngineDb` is row-level; the coarse `/dashboard`/`/summary`/`/skill`/`/next` endpoints are NOT `EngineDb` methods, so the read hooks (which call several repos) never reach them via the `db` swap. Add a **thin coarse client** — an `EngineClient` (or per-screen coarse loaders) with methods `loadDashboard(learnerId)`, `loadSummary(sessionId)`, `loadSkillDetail(skillId, learnerId)`, `nextItem(sessionId, ...)` — each a single fetch to the matching coarse endpoint, returning `wire/` shapes. The 3 read hooks + the scheduler entry call this, NOT the repos (see Track A-reads below). **FR-A6 relaxed** accordingly. |
| `frontend/app/api/engine/**/route.ts` (NEW family) | Coarse handlers (§4): `session/open`, `quiz/bootstrap` (pure read), `attempt`, `next`, `session/active`, `session/current`, `session/close`, `skill-state`, `dashboard`, `summary`, `skill/[id]`. Each: WorkOS verify (401, FR-A1) → derive learnerId server-side (FR-A2) → authz-scope (next row) → call `pgEngineDb`. No domain `if` (F-R4/B6). |
| **Ownership guard (FR-A2a mechanism — review #6)** | The session-scoped `EngineDb` methods take only `sessionId` (no `learnerId` param), so scoping is a **route-family helper**: `requireOwnedSession(engineDb, sessionId, learnerId)` — `getSession(sessionId)` → compare `session.learner_id` to the server-derived id → mismatch/absent = `404` **before any dependent read/write**. Used by: `quiz/bootstrap`, `attempt` (payload `session_id`), `next`, `session/current`, `session/close`, `summary`. Handlers that need the session row anyway pay no extra query. Learner-keyed methods (`listSkillState`, `listMisses`, `listProgressPoints`, `accuracyRowsBySkill`, `getNewestOpenSession`) are scoped by passing the derived `learnerId` directly — never an id from the request. |
| `frontend/lib/bff/server_composition.ts` | Add a **standalone `engineDb(): EngineDb` composition-seam function**, mirroring the existing **`coachMarkerRepo()`** (`:71-77`) — a memoized, env-reading seam function the `/api/engine/*` route handlers call directly. **NOT a param inside `serverPortBag()`/`buildAdapters`:** `serverPortBag()` returns a `PortBag` (thread/chat ports); the engine DB is a separate port family, so it gets its own seam function exactly as the coach marker does. It calls a new `selectEngineDb(env)` (mirroring `selectCoachMarkerRepo`/`selectThreadRepo`) → `pgEngineDb(url)` (`drizzle_engine_db.ts:269`). **Diverge from the marker precedent on the else-branch:** FR-A3 forbids a silent in-memory fallback, so unset `DATABASE_URL` → typed `EngineRepoError`, NOT `InMemoryEngineDb`. |
| `frontend/lib/composition_engine_browser.ts` | `buildBrowserEngineAdapters()` (`:93-140`) builds every repo from one `db` (`:96,108-114`) — swap that `db` from `new InMemoryEngineDb()` (`:96`) to `new HttpEngineDb(...)`, and drop the `seedTestItemBank(db)` call (`:265`, now server-seeded via Track G). **This single line is the atomic swap.** Behind a flag (§6). |
| `frontend/lib/adapters/engine/db/engine_db.ts` | Add method #30 `setSessionCurrentQuestion` + method #31 `getNewestOpenSession(subject, learnerId)` (review #6-B2); add `current_question_id` to the `QuizSession`-returning reads. All three impls (drizzle/in-memory/sqlite) implement both. |
| `frontend/app/api/engine/**` — G3 guard | Empty content tables → explicit "no content" response (FR-G3); the "no content" UI state lands **with A**, before a full prod seed (spec §9a). |
| **Track A-reads — rewire the 3 heavy read hooks (NEW — review #1, the FR-A6 relaxation)** | `use_dashboard.ts` (5 reads `:141-157`), `use_summary.ts` (6 reads `:145-153`), `use_skill_detail.ts` (5 + N+1 `:47/:51-56/:65-66`) each stop calling their several repos and instead call the coarse client's single loader. This is a **real call-site change** (not the "unchanged" original FR-A6) — but it is confined to these 3 hooks; the quiz/write consumers of `EngineDb` are untouched. Without it the coarse endpoints are dead code and the read screens regress to per-repo network fan-out (§7). |

### Track C — bounded-30 + fresh restart

| File | Change |
|---|---|
| `frontend/app/(coach)/learn/quiz/page.tsx` — **owns the close trigger** | The close fires in a **page Effect keyed on `progressVm.complete` becoming true**, NOT inside `runQuizSubmit`. Rationale (grounded): completion is **derived page state** — `progressVm.complete` comes from `toQuizProgressVM(...)` (`:585`) computed from graded-total vs `target_count`, and it flips only when the 30th item **resolves** (a retry doesn't increment graded-total), so it *already* encodes the "resolution not first-grade" timing FR-C1a needs. `runQuizSubmit` (`use_quiz.ts`) can't own it: a wrong first submit opens the coached loop (unresolved) and `runQuizSubmit` never sees `target_count`/graded-total. So: on `progressVm.complete` → persist close (`session/close`) → navigate to summary, in one Effect. |
| `frontend/app/(coach)/learn/quiz/page.tsx` — remove relabel | Remove the "Keep practising"/relabel + `QuizDoneBanner` continuation in the reviewing branch (`:598-629`, `:751-752`, all gated on `progressVm.complete`) — FR-C3. The default adaptive path hard-stops at the close Effect above instead of relabeling. |
| `frontend/components/quiz/use_quiz.ts` | Graceful close on pool-exhaustion instead of throw (FR-C5 — `openQuizItem` throws at `:219,242,269`). `runQuizSubmit` still records `correct`/`resolution` (`:367-376`, resolution `:362-365`) — it feeds graded-total; it does not own the close. |
| (model) `session_repo`/`schema` | No change — `target_count` (default 30) + `patchSessionClose` already exist; FR-C6 keeps `target_count=null` valid for non-default callers. |

### Track B — cross-device resume (needs A; C first per §9a)

| File | Change |
|---|---|
| `frontend/components/quiz/use_quiz.ts` — **`resumeQuizSession` signature change** | Today `resumeQuizSession(ports, {sessionId, questionId})` (`:461-474`) takes `questionId` **from the caller**, who reads it from `readActiveQuiz()` RAM. Post-swap the questionId is authoritative from the **server** `GET /api/engine/session/active` response (its `current_question_id`), not RAM. So the signature changes: the caller passes **only `sessionId`** (or nothing — the server picks the newest open session for the learner), and `resumeQuizSession` gets the question from the server response. Behavior: restore position from `current_question_id` (FR-B3b); **NULL → scheduler re-derive scoped by served-set + content-fresh** (FR-B8); **running score server-side with commit-first unique-`first_try`/unique-resolved semantics** (FR-B10, review #3 — NOT all-resolving-correct, or the resumed score exceeds the live one); still returns `null` → caller opens fresh if the session/question is gone (FR-B5). The caller **stops reading `readActiveQuiz()` for the questionId** (RAM is no longer the source of truth for resume position). |
| — served-set (FR-B9) | **Owned by the `/next` handler server-side** (§6; supersedes the earlier "mostly honored today" note — that described the *client-side* `openQuizItem→servedQuestionIds→Scheduler.next` path (`use_quiz.ts:183-185`, `fsrs_scheduler.ts:159-182`), which the coarse `/next` rewiring replaces). Post-swap: the `/next` handler reconstructs the served-set from the session id (`NOT IN` attempted) + the FR-E1 content-fresh projection at pick time; the client passes only the session id and never materializes a served-set. Resume (`resumeQuizSession`) therefore inherits FR-B9 for free — no RAM set to trust or rebuild. Throw sites to convert to graceful close (FR-C5): `use_quiz.ts:219,242,269`. |
| `frontend/components/quiz/quiz_session_store.ts` | The RAM `activeQuiz` pointer (`ActiveQuizPointer` `:53-66`, module `let` `:69`, accessors `:96-111`) becomes a durable-backed read; write-through to `session/current` on serve (FR-B3a), fire-and-forget (§7). Note `ActiveQuizPointer` already carries `phase`/`verdict`/`answeredLetter` — deliberately **not** persisted in `0004` (FR-B3-feedback advance-to-next). |
| `frontend/app/(coach)/learn/quiz/page.tsx` | Effect that writes the served pointer (on entering `answering`) now calls `session/current` (fire-and-forget). Honor `?mode=review`/`?focus=` = fresh, not resume (FR-B6). |

### Track E — content-fresh eligibility (needs A + G)

| File | Change |
|---|---|
| `frontend/lib/adapters/engine/scheduler/fsrs_scheduler.ts` + the `/next` handler | `next(subject, learnerId, servedIds?, servedSkillIds?)` (`:96-187`) already threads `servedIds` through its exclusion walk (`:159-182`) → `nextReviewedQuestion(...,excludeIds)`. Add a **prefer/filter layer**: extend the exclude set with cross-session already-correct ids (FR-E1), fall back to full-bank FSRS when the not-yet-correct pool empties (FR-E3). Layers on the existing `excludeIds` channel (FR-E1a) — no new scheduler shape. **Where it runs (review #1):** the eligibility projection (FR-E4) is a cross-session read that must be **server-side** — so the scheduler's next-pick is reached through the coarse `GET /next` handler (the scheduler entry is one of the 4 rewired call sites). The client `openQuizItem` calls `/next` instead of running `Scheduler.next()` in-browser against a client-side already-correct set it can't durably compute. |
| BFF `next` handler | Compute the cross-session "already-correct question ids" read projection (FR-E4) server-side (latest-attempt `correct===true`, per-learner, inverse of `listMisses`); pass into the scheduler's exclude set. |

### Track D — enriched summary (needs C + A)

| File | Change |
|---|---|
| `frontend/lib/translators/session_summary_vm.ts` | Add misses-list (this-session `listSessionAttempts`, incorrect OR walked-through — FR-D1/D1a) and strong/weak panel (project per-skill accuracy from this-session attempts, NOT `accuracyBySkill` last-N — FR-D2). Reuse `countSessionOutcomes` group-by-question for the dedup tally (§6). **FR-D3 scope (review #6):** these panels are **client projection of server-supplied attempt rows** — permitted; only the *headline score* is server-authoritative (FR-B10/close). Projection (group/label already-fetched rows) ≠ re-tallying the authoritative score. The rows come from the coarse `/summary` endpoint (Track A-reads), so the client never re-fetches per-repo. |
| `frontend/components/summary/*` (`SummaryView`) | Render the misses list + strong/weak panel; zero-miss clean-sweep state (FR-D4); omit no-attempt skills (FR-D5). |

---

## 4. Data model & migration 0004

**`0004` has TWO parts — both dual-dialect (parity is non-negotiable — `schema.parity.test.ts`):**
(a) the `quiz_session.current_question_id` served-pointer column, and (b) the `attempt.idempotency_key`
column + its partial unique index (the FR-A9.1 idempotency guarantee — see §6 decision 4).

**Part (a) — served-pointer column:**

| File | Change |
|---|---|
| `frontend/drizzle/0004_durable_progress.sql` (NEW) | `ALTER TABLE quiz_session ADD COLUMN current_question_id uuid;` (nullable, no default). |
| `frontend/lib/adapters/engine/db/schema.pg.ts` | Add `current_question_id: uuid("current_question_id")` to `quizSession` (near line 214, after `target_count`). **Nullable, no default** (Drizzle columns are nullable unless `.notNull()`). |
| `frontend/lib/adapters/engine/db/schema.sqlite.ts` | Add the **same-name, same-nullability** column to the sqlite `quiz_session` (near line 161) — but **`text("current_question_id")`, NOT `uuid(...)`**: sqlite stores the app-supplied uuid as text (the engine's dual-dialect id-row rule; sqlite has no `uuid` type). "Identical" under the parity contract means **column name + nullability**, not Drizzle column-type constructor. `schema.parity.test.ts` registers `quiz_session` in `TABLE_PAIRS` (`:23`) and auto-asserts **column-name** identity (`:35-38`) — it does **not** compare dialect types — **no test edit needed**; adding to only one dialect turns it red. |
| `frontend/lib/wire/engine_entities.ts` | Add `current_question_id: z.string().nullable()` to the `QuizSession` Zod entity (`:210-226`). **Note the Zod type differs from the `target_count` precedent:** `target_count` is `z.number().int().positive().nullable()` (`:224`); `current_question_id` is a uuid-as-string on the wire, so `z.string().nullable()`. The wire entity is the cross-process contract — pin it explicitly. |
| `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` | Implement `setSessionCurrentQuestion` + surface the field on `getSession`/`patchSessionClose` return. (This is the pg impl — `pgEngineDb(url)` `:269` / `pgEngineDbFrom(db)` `:282`; there is no `pg_engine_db.ts`.) |
| `frontend/lib/adapters/engine/db/in_memory_engine_db.ts` | Same, in-memory — keeps unit tests + behavioral parity. |

**Part (b) — attempt idempotency (FR-A9.1), the client-key mechanism from §6 decision 4:**

| File | Change |
|---|---|
| `frontend/drizzle/0004_durable_progress.sql` (same NEW file) | `ALTER TABLE attempt ADD COLUMN idempotency_key uuid;` (**nullable** — legacy rows have none). Then a **partial unique index**: `CREATE UNIQUE INDEX attempt_idempotency_uq ON attempt (session_id, question_id, idempotency_key) WHERE idempotency_key IS NOT NULL;` — the `WHERE … IS NOT NULL` clause is what lets the many legacy NULL-key rows coexist; only client-stamped keys are constrained. |
| `frontend/lib/adapters/engine/db/schema.pg.ts` | Add `idempotency_key: uuid("idempotency_key")` to `attempt` (`:222-240`, nullable) + a `uniqueIndex("attempt_idempotency_uq").on(session_id, question_id, idempotency_key).where(sql\`idempotency_key IS NOT NULL\`)` in the table's index callback (mirrors the existing `hint_*_uq` partial-index pattern, `schema.pg.ts:130-133`). |
| `frontend/lib/adapters/engine/db/schema.sqlite.ts` | Add `idempotency_key: text("idempotency_key")` (nullable; `text` not `uuid`, same id-row rule as part (a)) + the same-named partial unique index. sqlite supports `CREATE UNIQUE INDEX … WHERE …`. Parity test asserts column-name identity — both dialects must carry the column. |
| `frontend/lib/wire/engine_entities.ts` | **`AttemptInput` wire-contract change** — add `idempotency_key: z.string()` to the `Attempt` entity (`:242-254`), so `AttemptInput` (`= Attempt.omit({id, created_at})`, `:258`) now **includes** it (the caller supplies it — the whole point). `id` + `created_at` stay engine-assigned; `idempotency_key` is the one field the client owns for dedup. Legacy stored rows read back with `idempotency_key: null`, so the field on the **`Attempt`** read entity is `z.string().nullable()`, while on **`AttemptInput`** it is required (new writes must carry a key). Simplest shape: `idempotency_key: z.string().nullable()` on `Attempt`, then `AttemptInput = Attempt.omit({id, created_at}).required({idempotency_key: true})` — or a dedicated `AttemptInput` object; pick the one that keeps the omit-precedent readable at implementation. |
| `frontend/lib/adapters/engine/repos/drizzle_attempt_repo.ts` | `record()` (`:56-72`) passes `idempotency_key` straight through from the input (it already spreads `...attempt`); no monotonic-clock interaction — the key is orthogonal to `created_at`. |
| `frontend/components/quiz/use_quiz.ts` | The client stamps `idempotency_key = newUuid()` **once per answer action** (at grade time, not per HTTP attempt) and resends the same value if the POST retries. A coached retry is a new answer action → new key. |
| `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` — `insertAttempt` (**in-adapter idempotency, corrected review #5**) | The idempotent insert lives **inside the DB adapter**, NOT the handler: `insertAttempt` does `.onConflictDoNothing({ target: attempt_idempotency_uq })` and returns a **typed result** ("inserted" vs "already-existed", re-selecting the existing row on conflict). **Why not the handler:** `pgEngineDb` wraps every op's error as an opaque `EngineRepoError(stringified)` (`drizzle_engine_db.ts:284-286`), so a handler `catch` cannot see SQLSTATE 23505. Precedent: `upsertSkillState` (`:660-686`) already does `.onConflictDoUpdate(...)` in-adapter — the attempt insert mirrors it with `DoNothing`. The `EngineDb.insertAttempt` signature changes to return the typed result (both dialects + `in_memory_engine_db.ts` match). |
| `frontend/app/api/engine/attempt/route.ts` | Thin: calls `insertAttempt`, returns the stored `Attempt` from the typed result (idempotent 200 whether inserted or already-existed). **No PG-error string-matching** — the adapter already resolved the conflict. |

**Why part (b) exists at all:** `created_at` is server-assigned (`AttemptInput` omits it), so a natural key
can't dedup a client retry, and a handler read-then-write has a TOCTOU double-insert race — full
rationale in §6 decision 4. The client `idempotency_key` + partial unique index is the atomic fix.

---

## 5. Coarse endpoint contracts (guards FR-A4 chattiness)

New `wire/` request/response shapes (snake_case; no SDK types — A4/F-R8). Read screens collapse to
one call each (else the atomic swap regresses their latency — §7):

- `POST /api/engine/session/open` → `insertSession` (the write; `sessionRepo.open` → `insertSession`,
  `use_quiz.ts:120`) → returns the new session id. **Split out so `bootstrap` stays a pure read** —
  same side-effecting-GET discipline the plan applied to `session/current` (§6). A GET that opens a
  session would do a write; splitting keeps the open-write REST-honest and `bootstrap` cacheable.
- `GET /api/engine/quiz/bootstrap?session=<id>` → session + current item + hint ladder, **pure read**
  (open or resume — the session already exists by this point). The client calls `session/open` first
  for a new quiz, or reuses the resumed session id, then `bootstrap` to hydrate.
- `POST /api/engine/attempt` → persist → stored `Attempt`. Body carries a client-stamped
  `idempotency_key` (§6 decision 4). The **DB adapter** (`insertAttempt` with `.onConflictDoNothing()`
  on the partial unique index) resolves a retried POST to an atomic no-op and returns a typed
  already-existed result; the handler returns the stored `Attempt` either way. **The handler does NOT
  string-match a PG error** (review #5 — `pgEngineDb` wraps errors opaquely). A coached retry is a
  new answer action → new key → new row.
- `GET /api/engine/next` → next scheduled item. **Owns served-set reconstruction** (FR-B9): the
  handler recomputes the served-set from the session id (`NOT IN` attempted, §6) and content-fresh
  scoping (FR-E) server-side at pick time. No served-set crosses the wire.
- `POST /api/engine/session/current` → write served pointer (FR-B3a; fire-and-forget caller).
- `GET /api/engine/session/active` → newest open session (**backed by the NEW `EngineDb` method #31
  `getNewestOpenSession(subject, learnerId)`** — review #6-B2: no existing method finds an open
  session by learner; `listClosedSessionsByLearner` excludes `ended_at IS NULL`) + `current_question_id`
  + **server-computed running score** (FR-B10, **commit-first semantics — review #3**): numerator = count of unique
  questions resolved `first_try`; denominator = count of unique resolved questions. NOT all
  resolving-correct — a coached-correct must not bump the numerator, or the resumed score exceeds the
  live one (`quiz_screen_reducer.ts:434`). **Does NOT return the served-set** — `next` owns it (§6).
- `POST /api/engine/session/close` → `patchSessionClose` computing the tally **server-side with the
  same first_try-only, dedup-by-`question_id` rule** (§6, FR-C1, FR-B10) — **ignores any
  client-provided tally**. The live client tally and the server close-tally must agree by construction.
- `POST /api/engine/skill-state` → `upsertSkillState`.
- `GET /api/engine/dashboard` → the ~5 dashboard reads in one call.
- `GET /api/engine/summary?session=<id>` → the **6** summary reads in one call.
- `GET /api/engine/skill/[id]` → skill-taxonomy list + tutorial + skill_state + misses + accuracy +
  **the miss-question bodies** in one call — `use_skill_detail.ts` today does **1 sequential**
  `skillTaxonomy.list(subject)` (`:47`, before the parallel batch) **+ 4 parallel** reads (`:51-56`)
  **then an N+1** `Promise.all(questionIds.map(get))` (`:65-66`) = **5 + N+1 reads**. The coarse
  endpoint must fold all five *and* resolve the miss-question bodies server-side, or the N+1 becomes
  N+1 network round-trips post-swap.

**Per-method disposition is exhaustive, not a blanket fallback (review #6-B3):** all **31** methods
are mapped in §2 to exactly one of — a coarse carrier above; a thin fine-grained route
(`listSkillIds`, `getSkillByKey`, `listContentStrings`, `getTestBlueprint`, `listProgressPoints`,
`listReviewedHints`, `listReviewedTestItems`, `getQuestion`, `getSkillState`, `getContentString`,
`getTutorial`, `listSessionQuestionIds`/`listSessionAttempts`/`listSessionSkillIds` where not carried
coarse); or **SERVER-ONLY** (`insertQuestion`, `insertHint`, `insertTestItem`, `insertTestBlueprint` —
`HttpEngineDb` throws typed; a blanket "every method gets a handler" would expose content-write
endpoints to any authenticated learner). The FR-A4 conformance test asserts the disposition table is
total — every interface method resolves to a route or a typed server-only throw, so it proves
behavior, not just TypeScript shape. Read-site counts confirmed: dashboard 5
(`use_dashboard.ts:141-157`, 2 skippable), summary 6 (`use_summary.ts:145-153`), skill-detail
**5 + N+1** (1 sequential `skillTaxonomy.list` `:47` + 4 parallel `:51-56` + N+1 `:65-66`).

---

## 6. Plan-time decisions (resolving spec §10 open items)

| Open item | Decision | Rationale |
|---|---|---|
| Seed mechanism (review #4 — CORRECTED) | **Multi-source SQL emitter with `ON CONFLICT DO UPDATE` (reconciliation), NOT `DO NOTHING`.** | `DO NOTHING` ignores *changed* content → fails FR-G2 (a corrected item/hint won't propagate). The emitter must enumerate **all ≥5 sources** (`_test_item_bank` items 987, `_hint_bank`, `seedLessonContent` tutorials+content, `seedDevTaxonomy` skills, blueprints) — the promoted JSON is items-only. Upsert keyed by each table's natural id. **Removal = RETIRE (`reviewed=false`), never hard-DELETE (decided, review #6):** `attempt.question_id` is `onDelete: "cascade"` (`schema.pg.ts:230-231`) — a hard DELETE cascades-deletes learner attempt history, the exact data this epic exists to keep. |
| Seed timing (before vs alongside A) | **Alongside A**, decoupled by G3 | The empty-content guard (FR-G3) lands with A, so A never ships a broken surface even if the seed slips. |
| Cutover/flagging | **Flag-gated** (shadow → canary), mirroring the coach-v3 flag precedent | The atomic swap is high-blast-radius; a flag lets InMemory and Http coexist during validation. |
| Running-score semantics (FR-B10, review #3) | **Server computes unique-`first_try` / unique-resolved (commit-first), matching the live reducer exactly.** | `quiz_screen_reducer.ts:434` bumps `correct` ONLY on `first_try` under commit-first; counting all resolving-correct would make the resumed/closed score exceed the live score. `session/active` (resume) and `session/close` both compute this server-side and ignore client tallies. |
| Attempt idempotency mechanism (FR-A9.1) | **Client-supplied `idempotency_key` + partial unique index, idempotent insert IN the DB adapter (`.onConflictDoNothing`), NOT a handler PG-error catch (review #5).** | **Three mechanisms were rejected before this one.** (0) **Handler catches the unique-violation** — impossible: `pgEngineDb` wraps every op's error as opaque `EngineRepoError(stringified)` (`drizzle_engine_db.ts:284-286`), so SQLSTATE 23505 is unrecoverable at the handler. The insert must be idempotent *in-adapter* — `insertAttempt` does `.onConflictDoNothing()` and returns a typed already-existed result (mirrors `upsertSkillState:660`'s in-adapter `.onConflictDoUpdate`). (1) A **natural key `(session_id, question_id, created_at)`** is impossible: `created_at` is **server-assigned** (`AttemptInput = Attempt.omit({id, created_at})`, `engine_entities.ts:257-258`), so the retried POST carries no `created_at` to match on, and the value is anyway software-monotonic-per-repo-instance (`DrizzleAttemptRepo.record:56-65`), not clock-unique — a key the client can't reproduce can't dedup a retry. (2) **Handler-side query-then-insert** on `(session_id, question_id, chosen_letter)` avoids a wire change but has a **TOCTOU race**: two identical POSTs racing both pass the read and double-insert — a real double-count on the one path FR-A9.1 exists to protect, and the "same letter, no intervening re-serve" test is a heuristic, not a guarantee. So: the client stamps **one `idempotency_key` (UUID) per answer action** and resends it verbatim on any HTTP retry; the DB enforces uniqueness atomically. `created_at` stays server-assigned (preserves the monotonic-ordering the misses-recap relies on, `engine_repos.test.ts:351`); the key's only job is dedup. A legitimate coached retry is a **new** answer action → new key → new row (append-only preserved). This costs an `AttemptInput` wire-contract change (§4) — accepted, because a narrow-but-real double-count race is not worth avoiding a one-field additive wire change. |
| Concurrent-device tally (§6) | **Dedup by `question_id`** at close | Reuses `countSessionOutcomes` group-by; kills the double-count at its root. |
| Served-set reconstruction shape (FR-B9) | **Scope scheduler query `NOT IN` attempted ids** | Simpler server-side than materializing an explicit set; equivalent outcome. |
| Served-set *ownership* (which endpoint) | **`next` owns it; `session/active` does not return it.** | The served-set is a scheduler input, consumed only server-side inside the `next` handler — the client never uses it directly. `next` reconstructs it from the session id (`NOT IN` attempted, above) at pick time. `session/active` returning it would be dead payload. |
| Optimistic-UI rollback UX (FR-A8) | Hold behind an error banner (no rollback-to-unanswered) | Less jarring; the verdict was already shown by the deterministic client grader. |

---

## 7. ADR-0038 (raised by this plan — ⚠️ Ask-first triggers)

This plan fires multiple `⚠️ Ask-first` triggers, bundled into **one** ADR (the coherent
"durable engine seam" decision): **new BFF route family** (`/api/engine/*`), **new abstraction**
(`HttpEngineDb` — G1), a **new-dialect schema column + migration** (`0004`), and a **new seed
mechanism** (Track G). ADR-0038 will carry:

- **Context:** prod quiz runs on ephemeral `InMemoryEngineDb`; the pg layer exists but is unwired;
  cross-device durability is the goal.
- **Decision:** D1 (HttpEngineDb → BFF `/api/engine/*` → pgEngineDb), D6 Shape B (BFF holds
  `DATABASE_URL`, threads precedent).
- **Options rejected (the intent-debt payload):** D2 direct RSC/Server-Action rewrite (~11-screen
  blast radius); D3 resume-snapshot (doesn't give cross-device attempt history for custom lessons);
  Shape A Python-proxy (100% new FastAPI + schema port); a data-migration seed job (heavier than the
  emitter); persisting feedback-phase state in `0004` (FR-B3-feedback deferred).
- **Consequences:** every `useEngine()` screen is network-backed at swap (atomic); a later D2 refactor
  moves call sites, not data (the `EngineDb` seam is preserved); served-pointer write is
  fire-and-forget (degrades to FR-B8, not an error).

OKF bookkeeping: new `docs/adr/0038-durable-engine-seam.md` (from `0000-template.md`) + an `index.md`
entry + a newest-first `log.md` line. Links from the code seam (`http_engine_db.ts`,
`server_composition.ts selectEngineDb`).

---

## 8. Test & gate plan (from spec §8)

- Red/green per FR: failure-path tests first (401/authz/unset-URL/write-fail), then happy path.
- Frontend unit = Vitest against seeded `InMemoryEngineDb` or MSW-mocked BFF; the pg seam proven by
  a full-stack persistence probe (on-demand, like `db-persistence-probe.spec`).
- `make check` green (lint + format-check + tsc + test) + `tests/architecture/` (F-R9, F-R4, A4/F-R8,
  C1/C2, and the `schema.parity.test.ts` column-identity for `0004`).
- ADR-0038 appended before implementation of Track A (the ratchet trigger fires on the new
  `/api/engine/*` + `http_engine_db.ts` seam).
- Engine persistence proven end-to-end at least once (currently unproven — design §4).

## 9. Sequencing recap (spec §9a)

```
G (SQL emitter) + F (DATABASE_URL)  →  A (HttpEngineDb full surface + /api/engine/*, G3 guard)
     →  C (bounded-30, produces completed sessions)  →  B (resume) + E (content-fresh)  →  D (summary)
```

A is atomic (all-or-nothing surface); B is the first user-visible capability but can't ship on a
partial bag. G3 lands with A so seed timing stays decoupled from A shipping.
