---
type: spec
title: 'Coach learning-analytics event plane (D1) — behavior + episode capture'
status: 'Draft rev-2 — 2026-07-03 (clarify CLOSED; review B1–B3/H1–H5/M1–M6/L1–L3 applied; spec→plan gate pending)'
authored: 2026-07-03
---

# Spec — Coach learning-analytics event plane (D1): behavior + episode capture

**Status:** Draft (rev-2 — post-review) — 2026-07-03
**Owner:** Rajnish Khatri
**Related:**
- Stage-1 gate this spec inherits: [`coach-learning-analytics.brainstorm.md`](coach-learning-analytics.brainstorm.md) §8 (CLOSED — G-A=D1, G-B=YES, G-C=(i,ii))
- Sibling spec (D5 derive + crosswalk, referenced not covered here): `coach-learning-analytics-derive.spec.md` (to author)
- Port precedent applied (C3): [ADR-0006](../adr/0006-subject-coach-component-protocols.md) #3 `AttemptRepo` — **append + scoped-read** port ("write attempts; read for review my misses")
- Read-seam precedents (structure, not posture): [ADR-0014](../adr/0014-subject-coach-hint-repo-read-seam.md), [ADR-0015](../adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md)
- Loop constraint respected: [ADR-0009](../adr/0009-subject-coach-reflexion-not-on-live-path.md) (offline-only self-improvement)
- D0 (`elapsed_ms`) — **already landed** (2026-07-03), out of this spec's scope: [`decisions.md`](../adr/decisions.md) entries "D0 elapsed timing: page wiring is typechecked" + "Quiz `attempt.elapsed_ms` real timing (D0 fix)"; contract in [`quiz-attempt-elapsed-timing.spec.md`](quiz-attempt-elapsed-timing.spec.md)
- New ADR this spec raises: **ADR-0016** (12th engine port `LearningEventRepo` + `learning_event` table)

> **rev-2 changelog (post-review, all binding):** removed the D0/FR-4.1 red-first framing
> (D0 landed — B3); added the mandatory `subject` OCP column (B1); changed the port from
> "write-only" to **append + `meta/`-scoped read**, the true `AttemptRepo` posture (B2);
> replaced untyped `payload` + redundant `kind`/`action_kind` with a single
> `z.discriminatedUnion("action_kind", …)` typed payload (H5+M2 merged); defined
> `episode_id` minting authority + coach-only boundaries (H2); added a per-episode
> `step_index` for replay ordering (H3); named the authoritative hint-usage source (H4);
> the test-page write vs its isolation header is now an explicit ADR-0016 argument (H1);
> plus M1/M3/M4/M5 and the C1 DoD-correction.

---

## 1. Goal

Give the Subject-Coach learn surfaces (quiz, timed test, coach) a durable, append-only
**learner-analytics event plane** — behavior events and episode boundaries — distinct
from the governance plane (did the system behave?) and the eval plane (was the output
good?). It answers *"what did the learner do?"* and lays the trajectory spine (episode +
**ordered** action attribution) that a future offline self-improvement loop and
RL-playground replay both require, without any live adaptation (ADR-0009) and without
changing `/learn/test` serving (ADR-0013 tripwire).

D0 (the `attempt.elapsed_ms` real-timing fix) **has already landed** (2026-07-03; two
`decisions.md` entries) and is **out of scope here** — this spec is the D1 event plane
only.

## 2. Context

The Stage-1 premise audit ([brainstorm](coach-learning-analytics.brainstorm.md) §2)
verified the gap is real: **no learner-behavior capture exists** — the only
`TelemetrySink` implementation is `NullTelemetrySink`. (The brainstorm's `attempt.elapsed_ms`
hardcoded-`0` stub — D0 — has since been fixed on `frontend/app/(coach)/learn/quiz/page.tsx:121`
via `elapsedMsFrom(...)`; that fix is landed and out of this spec.) Trajectory-readiness
was **refuted**: nothing records which hint rung was shown, when, or which coach turn
preceded an answer.

*(Audit reconciliation, M6: the engine now has **11** tables in `ENGINE_TABLE_NAMES`
(`schema.pg.ts:321–333`), not the brainstorm's stale "9" — `test_item`/`test_blueprint`
landed with Phase 6. `learning_event` is the 12th.)*

The gate closed on **D1** (event table + write port + ADR) with D4 trajectory fields
baked in from day one. The clarify pass then resolved the two blocking corrections with
first-hand evidence:

- **C1 (run_ref join key) — RESOLVED to `trace_id` + offline crosswalk.** The client
  sees only `trace_id` on the wire (`frontend/lib/wire/ag_ui_events.ts:55`, optional);
  the eval record is keyed by `task_id` and does **not** carry `trace_id`
  (`services/eval_capture.py:37–40`); `trace_id` and `task_id` are independent
  `uuid4()` draws on the live path (`agent_ui_adapter/adapters/runtime/langgraph_runtime.py:186–188`).
  Decision: `run_ref` stores **`trace_id`** (zero wire change); the black-box
  `run_started` trace gains `task_id` in its `details` so the D5 job can join
  `trace_id → task_id → eval record` offline. The join is deliberately 2-hop and
  meta-plane-only — the live path stays untouched (ADR-0009).
- **C3 (write-port framing) — CORRECTED.** The brainstorm's "first write port" claim is
  **wrong**: `AttemptRepo.record()` (`frontend/lib/ports/engine/attempt_repo.ts:24`),
  `QuestionRepo.save()`, `Scheduler.review()`, `SessionRepo.open()/close()` are all write
  ports. Crucially `AttemptRepo` is documented as **"write attempts; read for review my
  misses"** (ADR-0006 #3) — an **append-only port with a scoped read** (`misses()`,
  `attempt_repo.ts:27`). `LearningEventRepo` **applies** that exact posture: `append()`
  + a `meta/`-scoped `listForReplay()`; it excepts nothing. The ADR is a pattern-
  application, not an exception. *(This corrects rev-1's self-contradictory "write-only,
  no read surface," which the test plan and the D5 consumer both violated — review B2.)*

**Scope of THIS spec (clarify):** behavior + episode families only. `experience_*`,
`feedback_*` (D6), and `governance_*` (retention/consent, M5) enum namespaces are
**reserved but not emitted**. D5 (`meta/` join + crosswalk) is a **sibling spec**,
referenced here for the crosswalk source it consumes.

## 3. Functional requirements (EARS)

Failure paths first within each family (TAP-4). Numbers are this spec's identities.

### FR-1 — `learning_event` append-only table + append/scoped-read port

- **FR-1.1** IF a caller supplies a `learning_event` whose `action_kind` discriminant is
  unknown, OR whose typed `payload` does not match that discriminant's schema, THEN THE
  SYSTEM SHALL reject it at parse (Zod `ValidationError`) — never persist an untyped,
  mismatched, or partially-formed event. *(Single discriminant: `action_kind` is the sole
  event-type key; there is no separate free `kind` column that could disagree with it —
  review H5. Reserved namespaces `experience_*`/`feedback_*`/`governance_*` are not valid
  `action_kind`s this increment and are rejected here.)*
- **FR-1.2** IF `run_ref` is present but not a non-empty string THEN THE SYSTEM SHALL
  reject at parse — `run_ref` is nullable (absent for non-coach events), never empty-string.
- **FR-1.3** THE SYSTEM SHALL define a `learning_event` table in **both dialects**
  (`schema.sqlite.ts` + `schema.pg.ts`), added to `ENGINE_TABLE_NAMES`, with the §4
  columns — including a `subject text notNull default DEFAULT_SUBJECT` column (the
  engine-wide OCP discriminator every other table carries, README §"subject discriminator"
  / FR-H1 — review B1). `id`, `occurred_at`, and `step_index` are engine-assigned.
- **FR-1.4** THE SYSTEM SHALL expose `LearningEventRepo` as the 12th engine port with an
  **append + `meta/`-scoped read** surface — mirroring `AttemptRepo`'s posture
  ("write attempts; read for review my misses", ADR-0006 #3):
  - `append(event): Promise<LearningEvent>` — inserts one row; returns it with
    engine-assigned `id`, `occurred_at`, `step_index`. No `update`/`delete`.
  - `listForReplay(subject, userId, sinceOccurredAt?): Promise<LearningEvent[]>` — the
    offline-derivation read, ordered by `(episode_id, step_index)`; the analogue of
    `misses()`. **Not reachable from serving code** (ADR-0016 argues the same
    read-on-append-only posture as `AttemptRepo`); consumed by the D5 `meta/` job and by
    the conformance/emit tests to read events back.
  - Wired through `buildEngineAdapters()` (the `EnginePortBag`) with in-memory + Drizzle
    adapters + a conformance bundle mirroring `attempt_repo`.
- **FR-1.5** WHEN `append()` is called twice with identical caller payloads THE SYSTEM
  SHALL persist **two distinct rows** (events are occurrences, not idempotent facts —
  the opposite of `test_item`'s content-hash idempotency; two hesitations are two events).
- **FR-1.6** WHEN events are appended within one `episode_id` THE SYSTEM SHALL assign a
  **monotonic per-episode `step_index`** (0-based, gap-free in append order) so a replay
  can reconstruct the sequence `(item_served → hint_shown → answer_changed → …)` —
  `occurred_at` (ms ISO) + a non-monotonic UUID `id` disambiguate identity but **not
  order** (review H3). IF two `append()`s for one episode race THEN the store SHALL still
  assign distinct, ordered `step_index` values (the assignment is the store's, not the
  caller's).

### FR-2 — Emit seam: three call sites, one port

- **FR-2.1** THE SYSTEM SHALL emit events through the single `LearningEventRepo` port from
  **three distinct call sites** — quiz (`use_quiz`/quiz page), timed test (`test/page.tsx`
  reducer), coach (`use_coach`/CoachPanel) — each emitting family-appropriate
  `action_kind`s; no shared cross-surface hook that couples the three lifecycles (the test
  page's documented isolation, `test/page.tsx:7–11`, stays intact).
- **FR-2.2** IF an `append()` call rejects or throws THEN THE SYSTEM SHALL swallow the
  error (fire-and-forget, the `coach_session_marker` precedent) and SHALL NOT block, fail,
  or alter the learner action that triggered it — analytics is never on the correctness path.
- **FR-2.3** WHEN a learner is shown a hint rung THE SYSTEM SHALL emit `hint_shown`
  carrying the **rung** (`1|2|3`, the `Hint.rung` union) and its `question_id` — the
  richer signal that the `attempt.used_hint` boolean cannot express. **`learning_event`
  is the authoritative hint-usage source for D5** (rung + timing + order); `attempt.used_hint`
  is **retained, not deprecated** — it still feeds FSRS scheduling reads, which need only
  the boolean. D5 derives rung-level usage from events, never from `used_hint` (review H4).
- **FR-2.4** WHEN a coach turn's response is shown to the learner THE SYSTEM SHALL emit
  `coach_turn_shown` with `run_ref = trace_id` (read from the SSE event's
  `raw_event.trace_id`), `question_id`, and the derived coach `mode` — where `mode ∈
  {pre_submit, post_feedback}`, the two `CoachMode` values the BFF derives
  (`coach_context_sanitizer.ts` `deriveCoachMode`; M3) — so the learner's subsequent
  answer is attributable to the coach action offline (C1).
- **FR-2.5** WHEN a question is served to the learner THE SYSTEM SHALL emit `item_served`
  (`question_id`, `episode_id`); WHEN the learner changes a selection before submit THE
  SYSTEM SHALL emit `answer_changed` carrying the `from`/`to` letters in its typed payload.

### FR-3 — Episode boundaries + minting authority (trajectory spine)

Every episode has exactly one minting authority (who assigns `episode_id`) so two
implementations cannot diverge (review H2). `step_index` (FR-1.6) is scoped per `episode_id`.

- **FR-3.1** WHERE a quiz session exists THE SYSTEM SHALL set `episode_id` = the
  `quiz_session` id returned by `SessionRepo.open()` (`session_repo.ts:33–47`) — the
  session lifecycle is the minting authority; episodes are not re-invented where a boundary
  already exists.
- **FR-3.2** WHERE **timed test mode** runs (no `quiz_session` row exists —
  `test/page.tsx:7–11`) THE SYSTEM SHALL have the **test reducer mint one `episode_id`
  (`uuid4`) at test start** and emit `episode_start` / `episode_end` events bounding the
  test under that id — so test-mode trajectories have explicit boundaries **without**
  persisting test attempts or a `quiz_session` row (G-C-iii stays deferred). The minted id
  lives only on the emitted events, not in a new test-mode table.
- **FR-3.3** WHERE a **coach-only** interaction runs with no enclosing quiz session THE
  SYSTEM SHALL mint a coach-episode `episode_id` (`uuid4`) **keyed to
  `coach_context.question_id`** and emit `episode_start` / `episode_end` bounding the
  coach exchange — coach-only episodes are **explicitly bounded**, not merely grouped by
  `question_id` (closing the rev-1 gap the review flagged: `question_id` is not an
  `episode_id`). The coach thread itself is still not persisted (`coach_thread_store.ts:16–19`
  — G-C-iv stays deferred); only the boundary events are.

### FR-4 — Crosswalk source for D5 (this spec's server-side obligation)

- **FR-4.1** THE SYSTEM SHALL include `task_id` in the black-box `run_started` trace
  `details` (`langgraph_runtime.py:_emit_trace`, today `{run_id, thread_id}`), so a
  `trace_id`-keyed record carries `task_id` and the D5 sibling job can resolve
  `run_ref (=trace_id) → task_id → eval record` offline. (The join itself is D5's spec;
  this FR only guarantees the crosswalk **source** exists.)

> *(D0 note: the former FR-4 `attempt.elapsed_ms` fix is not in this spec — it landed
> 2026-07-03; see `decisions.md`. Renumbering: the crosswalk FR is now FR-4; there is no
> FR-5.)*

## 4. Data model / contracts

| Contract | Kind | Home | Notes |
|---|---|---|---|
| `learning_event` table | NEW, both dialects | `frontend/lib/adapters/engine/db/schema.{sqlite,pg}.ts` | Added to `ENGINE_TABLE_NAMES`. Columns below. Carries `subject` (B1). **Separate table** from `attempt` — analytics events are not attempts and must never enter FSRS scheduling reads. |
| `LearningEvent` / `LearningEventInput` Zod entities | NEW | `frontend/lib/wire/engine_entities.ts` | Mirrors `Attempt`/`AttemptInput`: snake_case, Schema + inferred-type co-export, `Input = omit({id, occurred_at, step_index})`. `payload` is a `z.discriminatedUnion("action_kind", …)` (H5+M2). |
| `LearningEventRepo` port | NEW (12th; append + `meta/`-scoped read) | `frontend/lib/ports/engine/learning_event_repo.ts` | `append()` + `listForReplay()`. The `AttemptRepo` (ADR-0006 #3) append+scoped-read posture (B2). No update/delete; read not reachable from serving code. |
| In-memory + Drizzle adapters | NEW | `frontend/lib/adapters/engine/repos/` | Conformance bundle mirrors `attempt_repo` adapters (both `append` and the scoped read). |
| `_emit_trace` `run_started` details | CHANGED | `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` | `details` gains `task_id` (FR-4.1). Additive; no signature change; `TrustTraceRecord.details` is an open `dict` (no trust-kernel type change, no re-sign). |

**`learning_event` columns** (both dialects):

```
id            text  PK        -- engine-assigned
subject       text  notNull   -- default DEFAULT_SUBJECT ('act-english') — the OCP discriminator (B1/FR-H1)
user_id       text
session_id    text  NULL       -- quiz_session id ONLY (FK for quiz score/scheduling joins); NULL in test/coach
question_id   text  NULL
episode_id    text  NULL       -- FR-3 trajectory boundary: quiz_session id | test-minted uuid | coach-minted uuid
step_index    integer notNull  -- engine-assigned; monotonic per episode_id (FR-1.6, replay ordering)
run_ref       text  NULL       -- trace_id of the coach run (C1); NULL for non-coach events
action_kind   text  notNull    -- SINGLE discriminant (H5); the enum below
payload       text  notNull    -- JSON of the typed discriminated-union payload for action_kind (no learner free-text this increment)
occurred_at   text  notNull    -- engine-assigned ISO-8601
```

**`session_id` vs `episode_id` (M1):** they are **not** redundant. `session_id` is the
FK to `quiz_session` for score/scheduling joins and is **NULL outside quiz** (test/coach
have no session row). `episode_id` is the trajectory boundary and is **always present**
(quiz: = session id; test/coach: a minted uuid). For quiz rows they coincide by design;
for test/coach only `episode_id` is set. Both are kept.

**`action_kind` discriminant — increment 1 (frozen; single enum, no separate `kind`
column — H5):** `item_served`, `hint_shown`, `answer_changed`, `coach_turn_shown`,
`episode_start`, `episode_end`. **Reserved (rejected at parse this increment):**
`experience_*`, `feedback_*` (D6), `governance_*` (retention/consent — M5).

**Typed `payload` per `action_kind`** — `z.discriminatedUnion("action_kind", …)` (H5+M2;
every other engine entity is a typed Zod object per W1, so `payload` must be too):

| `action_kind` | payload fields |
|---|---|
| `item_served` | `{}` (question_id/episode_id are columns) |
| `hint_shown` | `{ rung: 1\|2\|3 }` |
| `answer_changed` | `{ from: string, to: string }` (choice letters) |
| `coach_turn_shown` | `{ mode: "pre_submit" \| "post_feedback" }` (run_ref is a column) |
| `episode_start` | `{ origin: "quiz" \| "test" \| "coach" }` |
| `episode_end` | `{ reason: "completed" \| "abandoned" }` |

A row whose `payload` does not parse against its `action_kind` branch is rejected (FR-1.1).

## 5. Invariants & security boundaries

- **F-R2 (SDK isolation):** the emit hook lives in components/pages and calls the port —
  no SDK import; the Drizzle SDK stays confined to `adapters/engine/`.
- **W1 / F-R8 (wire kernel purity):** `LearningEvent` is a pure Zod shape; `payload` is
  JSON string, never a typed SDK object.
- **Engine port posture (C3/B2):** `LearningEventRepo` mirrors `AttemptRepo` (ADR-0006 #3):
  **append + a scoped read** (`listForReplay`, the analogue of `misses()`), no update/delete.
  The read is **not reachable from serving code** — it is a `meta/`-derivation + test read,
  exactly as `AttemptRepo.misses()` is a "review my misses" read on an append-only port.
  ADR-0016 argues this posture explicitly; it does **not** except ADR-0014/0015 (those are
  read-only for a governed-field reason that does not apply here).
- **Test-page isolation stance (H1 — consent-grade argument, NOT a tripwire assertion):**
  `test/page.tsx:7–11` documents the timed-test surface as sharing nothing with the quiz
  drip — "no use_quiz, no scheduler, no sessionRepo, no attempt/FSRS write." FR-2.1 adds a
  `LearningEventRepo.append()` call from that surface, which **is a new engine-plane write
  and therefore a new coupling** — the "three call sites, not one hook" structure does not
  by itself discharge this (the review's correct point). **ADR-0016 MUST argue why an
  append-only analytics write is compatible with the isolation header's intent** — the
  header's stance is *no shared learning-state / no FSRS/attempt mutation that changes the
  learner's trained model*; an append-only, read-segregated event that never feeds
  scheduling preserves that intent — OR the test page's header is amended in the same PR to
  record the exception. This is a decision the ADR owns, not a line this spec asserts away.
  (ADR-0013 remains about *serving/content integrity*, a separate stance — cited below only
  for the serving tripwire, not for this write.)
- **ADR-0013 tripwire UNFIRED (separate from H1):** no `/learn/test` serving change;
  `_test01_english_corpus.ts` untouched. Emitting test-mode *episode events* is not serving
  test content.
- **ADR-0009 (offline-only loop):** events are captured for **offline** derivation; nothing
  here feeds a live in-turn adaptation. No graph node added (invariant #6); FR-4.1 is an
  additive detail field, not a new node.
- **Privacy / retention (O2 / H5 / M5):** no learner free-text in `learning_event` this
  increment (payloads are enums/ids/timings); per-user isolation rides `user_id`. **Data
  governance is a stated NON-GOAL of this increment** — retention windows, export/delete
  (FERPA/GDPR-adjacent, likely minor-serving), and consent are **deferred**, with a
  reserved `governance_*` `action_kind` namespace (rejected until specced). The spec does
  not silently ship a behavioral plane with no deletion story: it names the gap and defers
  it explicitly, to be closed before any production enablement.
- **No `trust/` change:** `TrustTraceRecord.details` is an open `dict` (FR-4.1 adds a key,
  no kernel type change, no re-sign).
- **ADR ratchet (⚠️ Ask first):** new engine port + new table ⇒ **ADR-0016** (OKF
  frontmatter + `index.md` + `log.md`; ADR-0006 header gains the amendment pointer **and
  its port-enumeration table gains the 12th row** — not just a header line, L3).

## 6. Edge cases

- Coach event with no `trace_id` on the SSE frame (it is optional) → `run_ref` NULL; the
  event still records via `(user_id, question_id, occurred_at)` — attribution degrades to
  the time-window join, never a fabricated `run_ref`.
- Timed-test learner abandons mid-test (no `episode_end`) → the dangling `episode_start`
  is a valid, queryable signal; the D5 job treats a missing `episode_end` as
  `reason="abandoned"` — not an error to suppress.
- `append()` in dev with no `DATABASE_URL` (in-memory engine DB) → events land in the
  in-memory store and vanish on restart — acceptable for dev; documented, not a failure.
  (The in-memory adapter's `listForReplay` is what emit/conformance tests read — FR-1.4.)
- Two events in the same millisecond in one episode → two rows with **distinct, ordered
  `step_index`** (FR-1.6); `occurred_at` ties but `step_index` does not — ordering is
  preserved for replay (H3). `id` (UUID) disambiguates identity, never order.
- Answer changed twice → two `answer_changed` rows, `step_index` n and n+1 (each an
  occurrence, ordered).
- Reserved-namespace `action_kind` (`feedback_thumb`, `governance_purge`) submitted this
  increment → rejected at parse (FR-1.1) — reserved ≠ accepted.
- `payload` shape mismatched to `action_kind` (e.g. `hint_shown` with no `rung`) → rejected
  at parse by the discriminated union (FR-1.1) — an inconsistent state is unrepresentable.

## 7. Non-functional requirements

- **Determinism:** entity validation, table roundtrip, and enum rejection are L1 (exact).
  Emit-seam behavior is L2 (in-memory adapter, no live I/O). No live LLM anywhere.
- **Cost / latency:** `append()` is one INSERT, fire-and-forget (FR-2.2) — off the
  learner correctness path; zero added LLM calls.
- **Reversibility:** all-additive (new table/port/entity/files + one detail-field add +
  one call-site fix). Rollback = drop table, unwire port, revert the two edits.
- **CI:** every FR test runs in `make check` / `pnpm test` (all deterministic). D5's live
  join is out of scope here.

## 8. Test plan

Failure-path tests first. All rows run in `make check` / `pnpm test`.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1.1 | `learning_event_entities.test.ts::rejects_unknown_action_kind`, `::rejects_reserved_namespaces` (experience_*/feedback_*/governance_*), `::rejects_payload_mismatched_to_action_kind` (discriminated union) — all failure-path | L1 | yes (vitest) |
| FR-1.2 | `::rejects_empty_string_run_ref` (nullable ok, empty rejected) | L1 | yes (vitest) |
| FR-1.3 | `drizzle_learning_event_repo.test.ts::roundtrip_both_dialects` (incl. `subject` col defaulting to `DEFAULT_SUBJECT`) + `ENGINE_TABLE_NAMES` includes `learning_event` (lock test) | L2 | yes (vitest) |
| FR-1.4 | port barrel + `buildEngineAdapters` wiring test; conformance bundle (in-memory + Drizzle) mirrors `attempt_repo` — exercises **both** `append` and `listForReplay`; `::list_for_replay_ordered_by_episode_then_step` | L2 | yes (vitest) |
| FR-1.5 | `::identical_payloads_persist_two_rows` (non-idempotent, before any happy path) | L1 | yes (vitest) |
| FR-1.6 | `::step_index_monotonic_per_episode` + `::same_ms_events_get_distinct_ordered_step_index` (ordering, not just identity) — failure-path against a naive occurred_at-only sort | L1 | yes (vitest) |
| FR-2.1 | three-call-site test: quiz/test/coach each emit via the port; test-page emit imports no `sessionRepo`/`scheduler` (isolation lock — H1) | L2 | yes (vitest) |
| FR-2.2 | `::append_rejection_does_not_block_submit` (throwing repo → learner action still completes) — failure path | L2 | yes (vitest) |
| FR-2.3 | `::hint_shown_carries_rung` (rung 1/2/3 in typed payload, not `used_hint`); `::used_hint_still_written_for_scheduling` (H4 — not deprecated) | L1 | yes (vitest) |
| FR-2.4 | `::coach_turn_shown_run_ref_is_trace_id` (run_ref = SSE `raw_event.trace_id`); `::coach_turn_mode_is_pre_or_post` (M3 enum) | L1 | yes (vitest) |
| FR-2.5 | `::item_served_emitted`; `::answer_changed_carries_from_to_letters` | L1 | yes (vitest) |
| FR-3.1 | `::quiz_episode_id_is_session_id` | L1 | yes (vitest) |
| FR-3.2 | `::test_mode_mints_uuid_and_emits_start_end` (no `quiz_session` dependency; reducer is minting authority) | L1 | yes (vitest) |
| FR-3.3 | `::coach_only_mints_episode_and_emits_start_end` (bounded, not just question_id-grouped) | L1 | yes (vitest) |
| FR-4.1 | `tests/agent_ui_adapter/.../test_run_started_trace_carries_task_id` (details has `task_id`) — failure path: absent today | L1 | yes (pytest) |

## 9. Definition of Done

- [ ] All FRs implemented; each has a passing test *seen to fail first* (FR-4.1 must be
      watched red against the absent `task_id` detail; FR-1.6 against a naive occurred_at-only
      ordering; FR-1.1 against each reserved namespace + payload mismatch).
- [ ] `learning_event` carries `subject` (`notNull default DEFAULT_SUBJECT`) in **both**
      dialects (B1); a dialect-parity test asserts the column exists in each.
- [ ] `LearningEventRepo` exposes `append` **and** `listForReplay` (B2); no `update`/`delete`;
      an architecture/lock test asserts serving code paths do not import `listForReplay`.
- [ ] `payload` is a `z.discriminatedUnion("action_kind", …)`; no separate `kind` column
      (H5+M2); a mismatched payload is unrepresentable.
- [ ] `step_index` is engine-assigned, monotonic per `episode_id`, and ordering survives
      same-ms ties (H3/FR-1.6).
- [ ] Episode minting authority is implemented per surface (H2): quiz = `SessionRepo`,
      test = reducer-minted uuid, coach-only = minted uuid keyed to `question_id`, each with
      `episode_start`/`episode_end`.
- [ ] `make check` green (backend) + frontend `pnpm test` green; no `/learn/test` behavior
      change (learn-e2e stays green).
- [ ] Invariants in §5 unbroken (`tests/architecture/` green; `test_adr_ratchet` satisfied
      by ADR-0016).
- [ ] **ADR-0016** accepted, OKF-complete (frontmatter, `index.md`, `log.md`); ADR-0006
      header gains the amendment pointer **and its port-enumeration table gains the 12th row**
      (L3); applies the `AttemptRepo` **append+scoped-read** precedent (C3/B2), does not claim
      "write-only" or a read-only exception; **explicitly argues the test-page isolation-header
      compatibility (H1)** or records a header amendment in the same PR.
- [ ] D0 is NOT in this spec (landed 2026-07-03; `decisions.md`) — no FR-4.1-elapsed test here (B3).
- [ ] C2 contingency **explicitly closed**: FR-4.1 resolves C1, so `defer(G-C-iii,iv)` holds
      (`defer ⟸ G-B=YES ∧ C1-resolved`); test-mode + coach-thread persistence stay deferred (M4).
- [ ] Brainstorm reconciled: §8 C3 note ("first write port") corrected to "append+scoped-read
      like `AttemptRepo`"; brainstorm P5 "9 tables" corrected to 11 (M6).
- [ ] D5 sibling spec (`coach-learning-analytics-derive.spec.md`) stub created and linked;
      it consumes the FR-4.1 crosswalk source.
- [ ] Actual command output pasted (not summarized) for the verification claims.
