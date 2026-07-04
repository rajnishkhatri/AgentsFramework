---
type: design
title: 'Coach learning-analytics event plane (D1) — task design (FR → structure → task-group map)'
status: 'Draft — 2026-07-04 (design bridge between spec rev-3, plan T1–T16, tasks A–J; tasks→implement gate pending)'
authored: 2026-07-04
---

# Design — Coach learning-analytics event plane (D1): FR → structure → task-group map

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Bridges:**
[`coach-learning-analytics.spec.md`](coach-learning-analytics.spec.md) rev-3 (the *what* — FR-1..FR-4) ·
[`coach-learning-analytics.plan.md`](coach-learning-analytics.plan.md) (the architecture — touchpoints T1–T16) ·
[`coach-learning-analytics.tasks.md`](coach-learning-analytics.tasks.md) (the atomic red-first checklist — Groups A–J)
**Governed by:** [ADR-0016](../adr/0016-subject-coach-learning-event-append-plane.md) (the *why*)

---

## Purpose

The *design of the tasks* — the binding between each acceptance criterion (spec) and the
concrete engine-plane structure that realizes it (and the task group that builds it). The
spec owns the `what`; the plan owns the architecture rationale; the tasks own the atomic
RED→GREEN units; this doc is the **join** — one row per FR, so no criterion is
zero-coverage and every structure traces back to a testable claim. Split out of the spec
(was spec §10) so the spec stays the pure EARS `what` and the design has its own home.

## Ground truth (verified at Stage 3–4 grounding)

The plane is one vertical slice mirroring the **`AttemptRepo`** precedent at every layer:

- Entity `Attempt`/`AttemptInput` via `.omit` — `engine_entities.ts:200,214`
- Adapter `DrizzleAttemptRepo` (constructor `{ db, newId?, now? }`) — `drizzle_attempt_repo.ts`
- Row methods `EngineDb.insertAttempt`/`listMisses` on the **full** `EngineDb` interface —
  **NOT** `ReadableEngineDb` — `engine_db.ts:62,96–98`
- Wiring `EnginePortBag.attemptRepo` + `buildEngineAdapters` — `composition_engine.ts:55,105`

## FR → structure → task-group map

| FR | Realizing structure (the design) | Precedent applied | Touchpoint(s) | Task group |
|----|----------------------------------|-------------------|---------------|------------|
| **FR-1.1/1.2** (parse rejection: unknown/reserved/mismatched `action_kind`, empty `run_ref`) | `LearningEvent` Zod entity + `payload = z.discriminatedUnion("action_kind", …)`; `run_ref = z.string().min(1).nullable()`; reserved namespaces absent from the enum | `Attempt` entity block (W1/W7) | T1 | **A** |
| **FR-1.3** (`learning_event` both dialects + `ENGINE_TABLE_NAMES`, `subject`+`step_index`) | New pgTable + sqlite twin; `subject notNull default DEFAULT_SUBJECT`; `step_index integer notNull`; unique `(episode_id, step_index)` index | `attempt` table + OCP `subject` col (B1/FR-H1) | T2, T3 | **B** |
| **FR-1.4** (12th port, append + `meta/`-scoped read) | `LearningEventRepo` interface + `DrizzleLearningEventRepo` + barrel; two `EngineDb` methods on the **full** interface only | `AttemptRepo` #3 / `insertAttempt`+`listMisses` | T4, T7, T8, T9 | **C, D** |
| **FR-1.5** (non-idempotent: identical payloads → 2 rows) | Both `EngineDb` impls append unconditionally (no content-hash dedup — the opposite of `test_item`) | contrast to `test_item` idempotency | T5, T6 | **C** |
| **FR-1.6** (engine-assigned monotonic per-episode `step_index`, survives ms-ties) | In-memory: count-of-same-episode at insert; Drizzle: `max(step_index)+1` within episode + unique index; `listForReplay` orders by `(episode_id, step_index)` | store-owned assignment (new; the load-bearing red-first test) | T5, T6 | **C** |
| **FR-2.1** (three sites, one port, no shared hook) | Emit calls in `use_quiz`/quiz page, `test/page.tsx` reducer, `use_coach`/CoachPanel; test-emit imports no `sessionRepo`/`scheduler` (ts-morph lock) | `attemptRepo.record` call-site shape | T12, T13, T14 | **G** (+ F2 lock) |
| **FR-2.2** (fire-and-forget; rejection never blocks) | Each emit wraps `append()` so a throw is swallowed, learner action completes | `coach_session_marker` precedent | T12–T14 | **G** (G1 first) |
| **FR-2.3** (`hint_shown` carries rung; `used_hint` retained) | `hint_shown` payload `{rung:1|2|3}` (the `Hint.rung` union); `attempt.used_hint` still written for FSRS | `Hint.rung`; H4 non-deprecation | T12 | **G** (G2) |
| **FR-2.4** (`coach_turn_shown`, `run_ref=trace_id` or NULL, `mode` client-derived) | Thread real coach `trace_id` (remove `use_coach.ts:90` `"no-trace"`); NULL when absent; `mode` via `deriveCoachMode` rule off the client marker, not the wire | ADR-0012 `deriveCoachMode`; **R1** | T14 | **G** (G4a→G4b) |
| **FR-2.5** (`item_served`; `answer_changed` from/to) | `item_served` payload `{}`; `answer_changed` payload `{from,to}` letters | typed discriminated payload | T12, T13 | **G** |
| **FR-3.1** (quiz episode = session id) | `episode_id` = `SessionRepo.open()` return (`session_repo.ts:33–47`) | `SessionRepo` minting authority | T12 | **G** (G2) |
| **FR-3.2** (test mode mints uuid; start/end; no `quiz_session`) | Reducer mints one `uuid4` at test start; emits `episode_start{origin:"test"}`/`episode_end{reason}`; id only on events | reducer-as-authority; isolation lock | T13 | **G** (G3) |
| **FR-3.3** (coach-only mints uuid keyed to question_id; start/end) | `uuid4` keyed to `coach_context.question_id`; bounded start/end; thread not persisted | coach-episode boundary (H2) | T14 | **G** (G4b) |
| **FR-4.1** (crosswalk source: `task_id` in `run_started` details) | `_emit_trace(run_started, details={…, task_id})` (`langgraph_runtime.py:191–196`); open `dict`, no re-sign | additive detail field | T15 | **H** |

## Cross-cutting design decisions carried by the tasks (not new FRs)

- **Read-seam segregation (H1/B2/spec §5):** `listForReplay`/`listLearningEventsForReplay`
  live on `EngineDb` + the port, **never** on `ReadableEngineDb`; a ts-morph isolation lock
  (task F2) asserts serving paths don't import them — the `AttemptRepo.misses` posture made
  code-enforced (the ADR-0011 "prose integrity rots" lesson), not a prose claim.
- **Test-page isolation compatibility (H1):** the test-emit isolation lock (task G3) + the
  fire-and-forget append discharge the new-coupling force; the argument is owned by ADR-0016
  and the `test/page.tsx:7–11` header is amended in the same PR (spec DoD).
- **ADR-0016 timing:** drafted alongside (task I1), ratifies at the tasks→implement gate; the
  ratchet (`test_adr_ratchet.py`) is satisfied by the `docs/adr/0016-*.md` file existing
  before the first `⚠️ Ask-first` (new port + new table) diff lands.
- **12th-port count reconciliation:** `LearningEventRepo` is the 12th engine port by the
  ADR-0006 amendment chain (7 + `LearnerReadRepo` + `HintRepo` + `TestBlueprintRepo` +
  `TestItemRepo`); the `ports/engine/index.ts` barrel comment currently says "nine" and omits
  the two Phase-6 test ports — task D4 reconciles that comment (a pre-existing staleness, not
  introduced here).

## Coverage assertion

Every automated FR (FR-1.1..FR-4.1) has a named realizing structure **and** a task group;
no FR is zero-coverage — the Stage-3 checklist criterion ("unit tests for English": is every
criterion measurable?) is met. The one FR realized outside the frontend ring is FR-4.1 (the
`langgraph_runtime.py` `task_id` detail, task group **H**, pytest).
