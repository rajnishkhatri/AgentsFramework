---
type: plan
title: 'Coach learning-analytics event plane (D1) — architecture plan + task list'
status: 'Draft — 2026-07-03 (derived from spec rev-2; plan→tasks gate pending)'
authored: 2026-07-03
---

# Plan — Coach learning-analytics event plane (D1)

**Status:** Draft — 2026-07-03
**Owner:** Rajnish Khatri
**Derives:** [`coach-learning-analytics.spec.md`](coach-learning-analytics.spec.md) rev-2 (FR-1..FR-4)
**Raises:** **ADR-0016** (12th engine port `LearningEventRepo` + `learning_event` table; append+scoped-read)
**Precedent mirrored end-to-end:** the `AttemptRepo` vertical slice (ADR-0006 #3) — the
only engine port that is *append + scoped-read*, the exact posture this needs.

---

## 1. Architecture — the vertical slice this adds

The engine plane is hexagonal: a `port` interface → a repo adapter → an `EngineDb`
row-store interface with **two** implementations (in-memory + Drizzle) → both dialects'
schema → wired in the composition root's `EnginePortBag` → conformance-tested against
both impls. `LearningEventRepo` adds one slice mirroring `AttemptRepo` at every layer.

```
FR-2 emit call sites (quiz / test / coach)   ← 3 sites, one port (spec FR-2.1)
        │  ports.learningEventRepo.append(evt)   (fire-and-forget — FR-2.2)
        ▼
frontend/lib/ports/engine/learning_event_repo.ts   ← NEW port (append + listForReplay)
        │
        ▼
frontend/lib/adapters/engine/repos/drizzle_learning_event_repo.ts  ← NEW repo
        │  delegates to EngineDb row methods (the AttemptRepo pattern)
        ▼
frontend/lib/adapters/engine/db/engine_db.ts       ← EXTEND interface:
        │     insertLearningEvent(e), listLearningEventsForReplay(subject,user,since?)
        ├── in_memory_engine_db.ts   ← NEW impl of the two methods (+ step_index assignment)
        └── drizzle_engine_db.ts     ← NEW impl of the two methods
        ▼
frontend/lib/adapters/engine/db/schema.{sqlite,pg}.ts  ← NEW learning_event table + ENGINE_TABLE_NAMES
        ▼
frontend/lib/wire/engine_entities.ts   ← NEW LearningEvent Zod + discriminated payload
        ▼
frontend/lib/composition_engine.ts (+ _browser)  ← wire learningEventRepo into EnginePortBag
        ▼
frontend/tests/architecture/test_engine_port_conformance.test.ts  ← run new port vs both impls
```

Server-side, one additive change out of the frontend ring:
```
agent_ui_adapter/adapters/runtime/langgraph_runtime.py  ← _emit_trace run_started details += task_id (FR-4.1)
```

## 2. File-level touchpoints

| # | File | Change | Spec FR | Precedent |
|---|------|--------|---------|-----------|
| T1 | `frontend/lib/wire/engine_entities.ts` | NEW `LearningEvent`/`LearningEventInput` + `LearningEventPayload` (`z.discriminatedUnion("action_kind", …)`); `subject` field; `Input = omit({id, occurred_at, step_index})` | FR-1.1/1.2, §4 | `Attempt` (l.200) |
| T2 | `frontend/lib/adapters/engine/db/schema.pg.ts` | NEW `learning_event` pgTable + add to `ENGINE_TABLE_NAMES`; `subject notNull default DEFAULT_SUBJECT`, `step_index integer notNull` | FR-1.3, B1 | `attempt` table |
| T3 | `frontend/lib/adapters/engine/db/schema.sqlite.ts` | NEW `learning_event` sqliteTable (dialect twin — no pg-only types) | FR-1.3 | `attempt` twin |
| T4 | `frontend/lib/adapters/engine/db/engine_db.ts` | EXTEND `EngineDb`: `insertLearningEvent`, `listLearningEventsForReplay`. **NOT on `ReadableEngineDb`** (serving read-seam stays clean — H1/B2) | FR-1.4 | `insertAttempt`/`listMisses` |
| T5 | `frontend/lib/adapters/engine/db/in_memory_engine_db.ts` | NEW impl of T4's two methods; **assigns `step_index` monotonic per `episode_id`** at insert | FR-1.4/1.6 | in-memory `attempt` |
| T6 | `frontend/lib/adapters/engine/db/drizzle_engine_db.ts` | NEW impl of T4's two methods; step_index via `max(step_index)+1` within episode (or a per-episode counter — task detail) | FR-1.4/1.6 | drizzle `attempt` |
| T7 | `frontend/lib/ports/engine/learning_event_repo.ts` | NEW port: `append(e): Promise<LearningEvent>` + `listForReplay(subject,user,since?): Promise<LearningEvent[]>` (JSDoc: not reachable from serving) | FR-1.4 | `attempt_repo.ts` |
| T8 | `frontend/lib/ports/engine/index.ts` | EXPORT the new port (barrel) | FR-1.4 | existing barrel |
| T9 | `frontend/lib/adapters/engine/repos/drizzle_learning_event_repo.ts` | NEW repo delegating to `EngineDb` | FR-1.4 | `drizzle_attempt_repo.ts` |
| T10 | `frontend/lib/composition_engine.ts` | ADD `learningEventRepo` to `EnginePortBag` + `buildEngineAdapters()` | FR-1.4 | `attemptRepo` wiring |
| T11 | `frontend/lib/composition_engine_browser.ts` | Mirror T10 for the browser root | FR-1.4 | browser wiring |
| T12 | `frontend/components/quiz/use_quiz.ts` (+ quiz page) | EMIT `item_served`, `hint_shown(rung)`, `answer_changed`, episode via `SessionRepo` id | FR-2.3/2.5, FR-3.1 | `attemptRepo.record` site |
| T13 | `frontend/components/test/test_runner_reducer.ts` (+ `test/page.tsx`) | MINT `episode_id` (uuid4) at start; EMIT `episode_start/end` + `item_served`/`answer_changed` — **no `sessionRepo` import** (isolation lock) | FR-3.2, FR-2.5 | reducer dispatch |
| T14 | `frontend/components/coach/use_coach.ts` (+ CoachPanel) | EMIT `coach_turn_shown(run_ref=trace_id, mode)`; MINT coach episode + `episode_start/end` | FR-2.4, FR-3.3 | `sendCoachAsk` |
| T15 | `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` | `_emit_trace(run_started, details={…, task_id})` | FR-4.1 | l.191–196 |
| T16 | `docs/adr/0016-*.md` + `index.md` + `log.md`; `docs/adr/0006-*.md` header + port table 12th row | NEW ADR + amendment | §5 ratchet, L3 | ADR-0015 |

## 3. Dependency-ordered build sequence

Bottom-up (each layer's tests pass before the next builds on it):

1. **Wire kernel (T1)** — entity + discriminated payload; L1 tests (reject unknown
   `action_kind`, reject payload mismatch, reject reserved namespaces, reject empty `run_ref`).
2. **Schema both dialects (T2, T3)** — table + `ENGINE_TABLE_NAMES` lock test + subject-col
   parity test.
3. **EngineDb interface + both impls (T4, T5, T6)** — the two row methods; **step_index
   monotonicity** is the load-bearing test here (same-ms ordering, per-episode).
4. **Port + repo + barrel (T7, T8, T9)** — append + listForReplay.
5. **Composition wiring (T10, T11)** — `EnginePortBag` gains `learningEventRepo`;
   composition tests green.
6. **Conformance (extend T-conformance)** — new port runs against in-memory + Drizzle.
7. **Emit call sites (T12, T13, T14)** — three sites, family-appropriate events, all
   fire-and-forget (rejection never blocks the learner action).
8. **Server crosswalk source (T15)** — `task_id` into trace details (independent of 1–7;
   can land in parallel).
9. **ADR-0016 (T16)** — drafts alongside; ratifies at the plan's human gate before implement.

Steps 1–6 are the substrate (no user-visible behavior). Step 7 is where the plane goes
live. Step 8 is parallelizable. **T14 has a blocking prerequisite — see §4 R1.**

## 4. Risks / blocking prerequisites surfaced by grounding

- **R1 (BLOCKING for T14) — the coach client has no real `trace_id` today.**
  `use_coach.ts:90` hardcodes `trace_id: "no-trace"` in `sendCoachAsk`. FR-2.4 sets
  `run_ref = raw_event.trace_id` from the SSE stream — but the coach path currently
  discards it. **T14 must first thread the real `trace_id` from the coach SSE events to the
  emit site**, or `run_ref` is uniformly `"no-trace"` and the C1 crosswalk is dead on
  arrival. This is a real task, not a field read. (Spec §6 already models `trace_id`-absent
  → `run_ref` NULL, but `"no-trace"` is worse: a *fabricated constant*, not NULL — the task
  must emit NULL when no real trace, never the sentinel.)
- **R2 — step_index under concurrent appends (Drizzle).** `max(step_index)+1` within an
  episode races if two emits fire near-simultaneously. In practice learn emits are
  user-paced and serialized per episode, but the plan pins the assignment as the store's
  responsibility (FR-1.6) and the task uses an INSERT that reads-then-writes within the
  episode; a unique index on `(episode_id, step_index)` makes a collision a hard error, not
  silent disorder. In-memory impl is trivially serial.
- **R3 — `subject` on coach/test events.** Quiz rows have a subject via the session; test
  mode and coach carry `coach_context.skill_id`/blueprint subject. The emit sites default to
  `DEFAULT_SUBJECT` (English-only today) — correct now, and the column exists so a Math coach
  is new rows, not a migration (B1/OCP).
- **R4 — ADR-0013 tripwire (non-risk, asserted).** No `/learn/test` serving change; only
  additive event emission. `_test01_english_corpus.ts` untouched.

## 5. Constitution check (AGENTS.md 8 invariants + frontend F-R)

- **Inv #1–#8 (backend layering):** T15 is the only backend touch — an additive detail-field
  in an existing adapter, no new node (Inv #6), no `trust/` change (`TrustTraceRecord.details`
  is an open dict). Meta-layer untouched (D5 is the sibling spec).
- **F-R2 (SDK isolation):** emit sites call the port; Drizzle stays in `adapters/engine/`.
- **F-R3 (one interface per port module):** `learning_event_repo.ts` = one interface.
- **F-R8 / W1 (wire purity):** `LearningEvent` is pure Zod; typed discriminated payload,
  no SDK type.
- **⚠️ Ask-first → ADR:** new engine port + new table ⇒ ADR-0016 (T16). `test_adr_ratchet`
  is satisfied by the new `docs/adr/*` file.
- **Append+scoped-read posture (B2):** `listForReplay` lives on `EngineDb`/the port but
  **not** on `ReadableEngineDb` (the serving read-seam), and an arch/lock test asserts
  serving code paths don't import it — the `AttemptRepo.misses` posture.

## 6. Human gate (plan → tasks)

Advance → **Stage 3 (checklist + atomic task decomposition)** once this plan is accepted.
The one decision worth surfacing before task derivation:

- **R1 (coach `trace_id`)** is a real prerequisite task inside T14, not a freebie. Confirm
  the approach: **thread the real trace_id from coach SSE events to the emit site, emit NULL
  `run_ref` when no real trace exists (never the `"no-trace"` sentinel)** — recommended. The
  alternative (ship `coach_turn_shown` without `run_ref` this increment, defer coach
  attribution) weakens the C1 story the whole plane is built around; not recommended.

Everything else follows the `AttemptRepo` precedent mechanically.
