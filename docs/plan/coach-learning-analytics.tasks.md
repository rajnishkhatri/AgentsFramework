---
type: tasks
title: 'Coach learning-analytics event plane (D1) — atomic task checklist'
status: 'Draft — 2026-07-04 (derived from plan T1–T16; R1 recommended approach confirmed; tasks→implement gate pending)'
authored: 2026-07-04
---

# Tasks — Coach learning-analytics event plane (D1)

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Derives:** [`coach-learning-analytics.plan.md`](coach-learning-analytics.plan.md) (T1–T16) ← [`coach-learning-analytics.spec.md`](coach-learning-analytics.spec.md) rev-3 (FR-1..FR-4)
**Design map (FR → structure → task-group):** [`coach-learning-analytics.design.md`](coach-learning-analytics.design.md)
**Precedent mirrored:** the `AttemptRepo` vertical slice — `Attempt`/`AttemptInput` entity
(`engine_entities.ts:200`), `DrizzleAttemptRepo` (constructor `{ db, newId?, now? }`,
`drizzle_attempt_repo.ts`), `EngineDb.insertAttempt`/`listMisses` (`engine_db.ts:96–98`),
`EnginePortBag.attemptRepo` wiring (`composition_engine.ts:105`).
**Gate confirmed:** R1 = thread real coach `trace_id`; emit NULL `run_ref` when no real
trace (never the `"no-trace"` sentinel). See T14.

---

## How to read this list

Every task is **red-first** (TAP-4): write the named test, watch it fail, then implement.
Each `[ ]` is one atomic unit with an explicit **RED** (the failing assertion to see
first) and **GREEN** (the implementation that makes it pass). Failure-path tasks come
before happy-path within each group. The build order is the plan's dependency chain
(§3): substrate bottom-up → port → wiring → conformance → emit → server → ADR.

`make check` (backend/pytest) + `pnpm test` (frontend/vitest) must be green at every
group boundary. **Paste actual output** (not a summary) at each verification checkpoint.

Test-file locations mirror the precedent: co-located `*.test.ts` next to source for L1/L2,
`frontend/tests/architecture/` for the conformance + lock tests, `tests/agent_ui_adapter/`
for the one pytest.

---

## Group A — Wire kernel (T1) · FR-1.1, FR-1.2, §4 data model

The pure Zod entity + discriminated payload. No I/O; all L1. This group is the
foundation — nothing else compiles against `LearningEvent` until it exists.

- [ ] **A1 (RED) — reject unknown `action_kind`.**
  New `frontend/lib/wire/engine_entities.test.ts` case
  `learning_event::rejects_unknown_action_kind`: `LearningEvent.safeParse({... action_kind:"frobnicate" ...})`
  → `success===false`. Watch it fail (no `LearningEvent` export yet). *(FR-1.1)*
- [ ] **A2 (RED) — reject reserved namespaces.**
  `::rejects_reserved_namespaces` — `experience_thumb`, `feedback_rating`, `governance_purge`
  each rejected at parse (they are not valid `action_kind`s this increment). *(FR-1.1, §5)*
- [ ] **A3 (RED) — reject payload mismatched to `action_kind`.**
  `::rejects_payload_mismatched_to_action_kind` — `{action_kind:"hint_shown", payload:{}}`
  (no `rung`) rejected by the discriminated union; `{action_kind:"answer_changed", payload:{rung:1}}`
  rejected. *(FR-1.1)*
- [ ] **A4 (RED) — reject empty-string `run_ref`.**
  `::rejects_empty_string_run_ref` — `run_ref:""` rejected; `run_ref:null` and a non-empty
  string both accepted (nullable OK, empty not). *(FR-1.2)*
- [ ] **A5 (GREEN) — implement `LearningEvent` + `LearningEventInput` + `LearningEventPayload`.**
  In `engine_entities.ts` (mirror the `Attempt` block at l.200): the §4 columns as a Zod
  object; `payload` = `z.discriminatedUnion("action_kind", [...])` with the six branches
  (`item_served`{}, `hint_shown`{rung:1|2|3 via the existing `Hint.rung` union}, `answer_changed`{from,to},
  `coach_turn_shown`{mode:"pre_submit"|"post_feedback"}, `episode_start`{origin}, `episode_end`{reason});
  `run_ref = z.string().min(1).nullable()`; `subject` default `DEFAULT_SUBJECT`;
  `LearningEventInput = LearningEvent.omit({ id: true, occurred_at: true, step_index: true })`.
  Co-export Schema + inferred type (W7). **A1–A4 now green.**
- [ ] **A6 (verify)** — `pnpm test engine_entities` green; paste output.

## Group B — Schema both dialects (T2, T3) · FR-1.3

- [ ] **B1 (RED) — `ENGINE_TABLE_NAMES` lock.**
  New `frontend/lib/adapters/engine/db/schema.test.ts` (or extend the existing table-name
  lock test) `::engine_table_names_includes_learning_event` — asserts `learning_event` ∈
  `ENGINE_TABLE_NAMES`. Fails (not added yet). *(FR-1.3)*
- [ ] **B2 (RED) — dialect parity for `subject`.**
  `::learning_event_has_subject_col_both_dialects` — reflect both `schema.pg.ts` and
  `schema.sqlite.ts` `learning_event` tables; assert each has a `subject` column
  `notNull` defaulting to `DEFAULT_SUBJECT`, and a `step_index` integer `notNull`. *(FR-1.3, B1)*
- [ ] **B3 (GREEN) — add the `learning_event` table to `schema.pg.ts`.**
  Mirror the `attempt` pgTable; columns per §4 (`id` PK, `subject notNull default DEFAULT_SUBJECT`,
  `user_id`, `session_id` NULL, `question_id` NULL, `episode_id` NULL, `step_index integer notNull`,
  `run_ref` NULL, `action_kind notNull`, `payload notNull`, `occurred_at notNull`); append
  `learning_event` to `ENGINE_TABLE_NAMES`.
- [ ] **B4 (GREEN) — add the dialect twin to `schema.sqlite.ts`.**
  Same table, sqlite types (no pg-only types), `step_index` as `integer`. **B1–B2 now green.**
- [ ] **B5 (verify)** — `pnpm test schema` green; paste output.

## Group C — EngineDb interface + both impls (T4, T5, T6) · FR-1.4, FR-1.5, FR-1.6

The load-bearing group: `step_index` monotonicity is where a naive `occurred_at`-only
ordering must be seen to fail first.

- [ ] **C1 (RED) — two identical appends persist two rows (non-idempotent).**
  Extend `frontend/lib/adapters/engine/db/engine_repos.test.ts` (or a new
  `learning_event_db.test.ts`) `::identical_payloads_persist_two_rows` — two
  `insertLearningEvent` with identical caller payloads → `listLearningEventsForReplay`
  returns 2 distinct rows (distinct `id`). Fails (method absent). *(FR-1.5)*
- [ ] **C2 (RED) — `step_index` monotonic per episode, survives same-ms ties.**
  `::step_index_monotonic_per_episode` + `::same_ms_events_get_distinct_ordered_step_index` —
  append 3 events to one `episode_id` with a **frozen clock** (same `occurred_at`); assert
  `step_index` is `0,1,2` in append order and `listLearningEventsForReplay` returns them
  ordered by `(episode_id, step_index)`, NOT by `occurred_at`. Watch fail against the naive
  sort. *(FR-1.6)*
- [ ] **C3 (RED) — per-episode scoping of `step_index`.**
  `::step_index_resets_per_episode` — events across two `episode_id`s each start at 0. *(FR-1.6)*
- [ ] **C4 (GREEN) — extend the `EngineDb` interface (T4).**
  In `engine_db.ts`, add to `EngineDb` (the full interface, **NOT** `ReadableEngineDb` —
  the serving read-seam stays clean, H1/B2):
  `insertLearningEvent(e: LearningEvent): Promise<void>` and
  `listLearningEventsForReplay(subject: string, userId: string, sinceOccurredAt?: string): Promise<LearningEvent[]>`.
  Import the `LearningEvent` wire type at the top (alongside `Attempt`).
- [ ] **C5 (GREEN) — in-memory impl (T5).**
  In `in_memory_engine_db.ts`: append to a private array; **assign `step_index` = count of
  existing rows with the same `episode_id`** at insert (monotonic, gap-free, per-episode);
  `listLearningEventsForReplay` filters by subject+user (+`sinceOccurredAt`), returns sorted
  by `(episode_id, step_index)`.
- [ ] **C6 (GREEN) — Drizzle impl (T6).**
  In `drizzle_engine_db.ts`: `insertLearningEvent` INSERTs; `step_index` via
  `max(step_index)+1` within the `episode_id` (read-then-write in one statement/txn);
  `listLearningEventsForReplay` = `SELECT ... WHERE subject=? AND user_id=? [AND occurred_at>=?]
  ORDER BY episode_id, step_index`. Add the unique index `(episode_id, step_index)` in the
  schema (B3/B4) so a race is a hard error, not silent disorder (R2). **C1–C3 now green
  against both impls.**
- [ ] **C7 (verify)** — `pnpm test` for the db tests green; paste output.

## Group D — Port + repo + barrel (T7, T8, T9) · FR-1.4

- [ ] **D1 (RED) — repo append round-trips; listForReplay reads back.**
  New `frontend/lib/adapters/engine/repos/drizzle_learning_event_repo.test.ts`
  `::append_assigns_id_occurred_at_step_index` + `::list_for_replay_ordered_by_episode_then_step` —
  against an `InMemoryEngineDb`, with injected `newId`/`now`. Fails (repo absent). *(FR-1.4)*
- [ ] **D2 (GREEN) — port interface (T7).**
  New `frontend/lib/ports/engine/learning_event_repo.ts`: one interface
  `LearningEventRepo` with `append(event: LearningEventInput): Promise<LearningEvent>` and
  `listForReplay(subject, userId, sinceOccurredAt?): Promise<LearningEvent[]>`. JSDoc states
  the append+scoped-read posture (mirror `attempt_repo.ts` header) and that `listForReplay`
  is **not reachable from serving code** (meta/-derivation + test read only).
- [ ] **D3 (GREEN) — repo adapter (T9).**
  New `drizzle_learning_event_repo.ts` mirroring `drizzle_attempt_repo.ts`: constructor
  `{ db, newId?, now? }`; `append` builds the row with `id=newId()`, `occurred_at=now().toISOString()`
  (step_index is the **store's** to assign — C5/C6 — so `append` passes the input through and
  the db assigns it, OR the repo reads it back; pin this in the task: **db assigns step_index**,
  repo returns the persisted row), delegates to `db.insertLearningEvent`, translates errors to
  `EngineRepoError`; `listForReplay` delegates to `db.listLearningEventsForReplay`.
- [ ] **D4 (GREEN) — barrel export (T8).**
  In `ports/engine/index.ts`, add `export type { LearningEventRepo } from "./learning_event_repo";`.
  Fix the stale barrel header comment while here: it says "nine ports" but omits the two
  Phase-6 files already on disk (`test_blueprint_repo.ts`/`test_item_repo.ts`, ADR-0015) —
  they are NOT re-exported through this barrel today. `LearningEventRepo` is the **12th
  engine port** by the ADR-0006 amendment chain (7 + LearnerReadRepo + HintRepo +
  TestBlueprintRepo + TestItemRepo); reconcile the comment to that count and export the two
  Phase-6 ports too if that is the intended barrel surface (confirm during implement — do not
  silently change the chat-port gate). **D1 now green.**
- [ ] **D5 (verify)** — `pnpm test drizzle_learning_event_repo` green; paste output.

## Group E — Composition wiring (T10, T11) · FR-1.4

- [ ] **E1 (RED) — server bag exposes `learningEventRepo`.**
  Extend `composition_engine.test.ts` `::bag_has_learning_event_repo` — `buildEngineAdapters({env:{}})`
  returns a bag whose `learningEventRepo.append` is callable. Fails (not wired). *(FR-1.4)*
- [ ] **E2 (RED) — browser bag exposes it too.**
  Extend `composition_engine_browser.test.ts` with the mirror assertion. *(FR-1.4)*
- [ ] **E3 (GREEN) — wire the server root (T10).**
  In `composition_engine.ts`: add `learningEventRepo: LearningEventRepo` to `EnginePortBag`;
  construct `new DrizzleLearningEventRepo({ db })` in `buildEngineAdapters` (next to
  `attemptRepo`, l.105).
- [ ] **E4 (GREEN) — mirror the browser root (T11).**
  Same addition in `composition_engine_browser.ts`. **E1–E2 now green.**
- [ ] **E5 (verify)** — `pnpm test composition_engine` green; paste output.

## Group F — Conformance (extend the engine conformance suite) · FR-1.4

- [ ] **F1 (RED→GREEN) — run the new port against both impls.**
  Extend `frontend/tests/architecture/test_engine_port_conformance.test.ts`: parametrize a
  `LearningEventRepo` bundle over `InMemoryEngineDb` **and** the Drizzle seam (mirroring how
  `AttemptRepo` is covered) — exercises **both** `append` and `listForReplay`, incl.
  `::list_for_replay_ordered_by_episode_then_step`. *(FR-1.4)*
- [ ] **F2 (RED) — serving read-seam lock (H1/B2).**
  New `frontend/tests/architecture/test_learning_event_read_isolation.test.ts` (ts-morph):
  assert no serving-path module (quiz/test/coach serving code, `ReadableEngineDb` consumers)
  imports `listForReplay`/`listLearningEventsForReplay` — the analogue of the
  `AttemptRepo.misses` posture. Watch it define the boundary, then keep it green. *(§5, DoD)*
- [ ] **F3 (verify)** — `pnpm test` architecture suite green; paste output.

## Group G — Emit call sites (T12, T13, T14) · FR-2, FR-3

Three sites, one port, all **fire-and-forget** (FR-2.2). Failure-path first: a throwing
repo must never block the learner action.

- [ ] **G1 (RED) — append rejection does not block submit (all sites).**
  `::append_rejection_does_not_block_submit` — inject a `LearningEventRepo` whose `append`
  rejects; assert the quiz submit (and test advance, coach turn) still completes. *(FR-2.2)*
- [ ] **G2 (RED+GREEN) — quiz emit site (T12).**
  Test `::quiz_emits_item_served_hint_shown_answer_changed` + `::quiz_episode_id_is_session_id`.
  In `use_quiz.ts`/quiz page: emit `item_served`(question_id, episode_id=`SessionRepo.open()` id),
  `hint_shown`(rung, question_id), `answer_changed`(from,to); `episode_id` = the quiz_session id
  (FR-3.1 — SessionRepo is the minting authority). `attempt.used_hint` still written for FSRS
  (H4 — `::used_hint_still_written_for_scheduling`). *(FR-2.3, FR-2.5, FR-3.1)*
- [ ] **G3 (RED+GREEN) — timed-test emit site (T13).**
  `::test_mode_mints_uuid_and_emits_start_end` + isolation lock `::test_emit_imports_no_session_repo`.
  In `test_runner_reducer.ts`/`test/page.tsx`: **mint one `episode_id`(uuid4) at test start**,
  emit `episode_start`{origin:"test"}/`episode_end`{reason}, plus `item_served`/`answer_changed`;
  **no `sessionRepo` import** (isolation lock, H1). *(FR-3.2, FR-2.5, FR-2.1)*
- [ ] **G4 (RED+GREEN) — coach emit site (T14) — includes the R1 prerequisite.**
  Two sub-steps, R1 first:
  - **G4a (R1) — thread the real coach `trace_id`.** `use_coach.ts:90` hardcodes
    `trace_id:"no-trace"`. Thread the real `trace_id` from the coach SSE `RunStarted`/token
    events (`raw_event.trace_id`) to the emit site. Test `::coach_turn_shown_run_ref_is_trace_id`
    (run_ref = the SSE trace_id) and `::coach_turn_run_ref_null_when_no_trace` (emit **NULL**,
    never `"no-trace"`, when the frame carries no trace_id — FR-2.4 edge case, §6).
  - **G4b — emit `coach_turn_shown` + coach episode.** `::coach_turn_mode_client_derived_not_wire`
    (mode via the `deriveCoachMode` rule from the client's submitted-marker state, NOT the wire —
    `hasSubmittedMarker ? "post_feedback" : "pre_submit"`); `::coach_only_mints_episode_and_emits_start_end`
    (mint coach `episode_id` keyed to `coach_context.question_id`, bounded start/end). *(FR-2.4, FR-3.3)*
- [ ] **G5 (verify)** — `pnpm test` for the three emit sites green; paste output. Confirm
  the learn-e2e still green (no `/learn/test` serving change — ADR-0013 tripwire unfired).

## Group H — Server crosswalk source (T15) · FR-4.1 (parallelizable)

Independent of Groups A–G; the one pytest task.

- [ ] **H1 (RED) — `run_started` trace details carry `task_id`.**
  New `tests/agent_ui_adapter/adapters/runtime/test_run_started_trace_carries_task_id.py`
  `::test_run_started_trace_carries_task_id` — assert the `_emit_trace(run_started, ...)`
  `details` dict includes `task_id`. Fails today (`{run_id, thread_id}` only,
  `langgraph_runtime.py:191–196`). *(FR-4.1)*
- [ ] **H2 (GREEN) — add `task_id` to the details.**
  In `langgraph_runtime.py`, add `"task_id": task_id` to the `run_started` `_emit_trace`
  `details` (additive; `TrustTraceRecord.details` is an open dict — no trust-kernel type
  change, no re-sign). **H1 now green.**
- [ ] **H3 (verify)** — `.venv/bin/python -m pytest tests/agent_ui_adapter/.../test_run_started_trace_carries_task_id.py -q`;
  paste output.

## Group I — ADR-0016 + amendments (T16) · §5 ratchet, L3

Drafts alongside Groups A–H; **ratifies at the tasks→implement gate before any code
lands** (or the ratchet blocks the PR).

- [ ] **I1 — draft `docs/adr/0016-*.md`** from `docs/adr/0000-template.md`
  (Context / Decision / Options / Rationale / Consequences). Decision: 12th engine port
  `LearningEventRepo` + `learning_event` table, **append + meta/-scoped read** applying the
  `AttemptRepo` precedent (C3/B2 — NOT a read-only exception, NOT "write-only"). Must
  **explicitly argue the test-page isolation-header compatibility (H1)**: an append-only,
  read-segregated event that never feeds FSRS/scheduling preserves the "no shared
  learning-state" intent — OR record a `test/page.tsx` header amendment in the same PR.
- [ ] **I2 — OKF bookkeeping:** `type:` frontmatter, `docs/adr/index.md` entry, newest-first
  `docs/adr/log.md` line.
- [ ] **I3 — amend ADR-0006:** header amendment pointer **and** the port-enumeration table
  gains the 12th row (`LearningEventRepo · append(...) · listForReplay(...)` · "write events;
  read for offline replay") — not just a header line (L3).
- [ ] **I4 — `test_adr_ratchet` satisfied** by the new `docs/adr/0016-*.md` file; run
  `.venv/bin/python -m pytest tests/architecture/test_adr_ratchet.py -q`; paste output.

## Group J — D5 sibling stub + final gate close · DoD

- [ ] **J1 — create `docs/plan/coach-learning-analytics-derive.spec.md` stub** (the D5 join
  spec) that consumes the FR-4.1 crosswalk source; link it from this bundle's `index.md` +
  the D1 spec's Related list.
- [ ] **J2 — reconcile the brainstorm §8** (M6): "9 tables" → 11; "first write port" C3 note →
  "append+scoped-read like `AttemptRepo`" (if any stale wording remains).
- [ ] **J3 — full gate:** `make check` green (backend) **and** `pnpm test` green (frontend);
  `tests/architecture/` green; learn-e2e green. Paste actual output for each — not a summary.
- [ ] **J4 — DoD sweep:** walk the spec §9 Definition-of-Done checklist; every box checked
  with evidence.

---

## Dependency graph (build order)

```
A (wire) ──▶ B (schema) ──▶ C (EngineDb + impls) ──▶ D (port+repo) ──▶ E (wiring) ──▶ F (conformance)
                                                                                          │
                                                                                          ▼
                                                                                     G (emit sites)
H (server task_id) ──────────────────────────────────────────────── parallel, joins at J
I (ADR-0016) ───────────────────────────────────────────────────── drafts alongside; ratify before merge
J (D5 stub + gate) ◀── depends on all of A–I
```

Groups A→F are the substrate (no user-visible behavior). Group G is where the plane goes
live. H is parallelizable. I ratifies at the gate. J closes.

## Human gate (tasks → implement)

Advance → **sdd-implement** once this checklist is accepted and **ADR-0016 (I1) is drafted**
(ratified before code merges — the ratchet enforces the file exists). Nothing else in this
list needs a decision; R1 is resolved (G4a). Start at **A1**, failure-first.
