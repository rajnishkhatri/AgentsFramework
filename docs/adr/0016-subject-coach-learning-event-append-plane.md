---
type: decision-record
title: 'ADR-0016: Subject-Coach learning-event append plane — learning_event table + LearningEventRepo (12th engine port, append + meta/-scoped read)'
status: accepted-with-conditions
created: 2026-07-04
updated: 2026-07-04
owner: Rajnish Khatri
related: 0006-subject-coach-component-protocols.md, 0009-subject-coach-reflexion-not-on-live-path.md, 0012-subject-coach-context-contract-hint-ladder.md, 0013-subject-coach-test-mode-blueprint-generation-integrity.md, 0014-subject-coach-hint-repo-read-seam.md, 0015-subject-coach-test-item-bank-blueprint-read-seam.md, coach-learning-analytics.spec.md, coach-learning-analytics.plan.md, coach-learning-analytics.tasks.md, coach-learning-analytics.design.md
tags: [decision-record]
---

# ADR-0016: Subject-Coach learning-event append plane

**Status:** Accepted with conditions — 2026-07-04 (was Proposed — 2026-07-04). The four
blocking conditions below were **discharged in-text at ratification** (the ADR was amended,
not merely annotated): (C1) the `task_id`/`run_id` grounding in Context + clause 7 was
corrected to the three-branch reality; (C2) the `use_coach.ts:90` citation was corrected
(error path, not normal emit path); (C3) `listForReplay` NULL-`episode_id` handling was
specified; (C4) the `step_index`-race × fire-and-forget composition was named as a single
composed accepted risk. Four **non-blocking recommendations** (R1–R4) are recorded in §
"Findings & recommendations" and tracked as follow-ups, not gating. Amends [ADR-0006](0006-subject-coach-component-protocols.md)
(**fourth amendment** — after [ADR-0011](0011-subject-coach-engine-learner-read-port.md) #8
`LearnerReadRepo`, [ADR-0014](0014-subject-coach-hint-repo-read-seam.md) #9 `HintRepo`,
[ADR-0015](0015-subject-coach-test-item-bank-blueprint-read-seam.md) #10/#11
`TestBlueprintRepo`/`TestItemRepo`). Adds the **12th** engine port.
**Related:** [ADR-0006 component protocols](0006-subject-coach-component-protocols.md) (the port
being amended; #3 `AttemptRepo` is the applied precedent) ·
[ADR-0009 reflexion-not-on-live-path](0009-subject-coach-reflexion-not-on-live-path.md)
(the offline-only loop constraint this plane serves) ·
[ADR-0012 context contract](0012-subject-coach-context-contract-hint-ladder.md)
(the `deriveCoachMode` rule the coach emit reuses; the BFF marker store) ·
[ADR-0013 Test Mode integrity](0013-subject-coach-test-mode-blueprint-generation-integrity.md)
(the serving tripwire this plane must not fire) ·
[ADR-0014 read-seam posture](0014-subject-coach-hint-repo-read-seam.md) /
[ADR-0015](0015-subject-coach-test-item-bank-blueprint-read-seam.md) (read-only-for-a-governed-field
posture — this ADR does **not** apply that one; see Rationale) ·
[D1 spec](../plan/coach-learning-analytics.spec.md) ·
[D1 plan](../plan/coach-learning-analytics.plan.md) ·
[D1 tasks](../plan/coach-learning-analytics.tasks.md) ·
[D1 task design](../plan/coach-learning-analytics.design.md)
**Audience:** anyone adding an emit call site, a new `action_kind`, the D5 offline
derivation/crosswalk job, or reasoning about whether an engine write is compatible with the
Test-Mode isolation stance.

---

## Context

The Subject-Coach learn surfaces (quiz, timed test, coach) capture **no learner-behavior
signal** today — the only `TelemetrySink` implementation is `NullTelemetrySink`, and nothing
records which hint rung was shown, when, or which coach turn preceded an answer. The
[D1 brainstorm](../plan/coach-learning-analytics.brainstorm.md) verified this gap and its
[spec](../plan/coach-learning-analytics.spec.md) (rev-2) scopes a **third signal plane** —
learner behavior + episode boundaries — distinct from the governance plane (*did the system
behave?*) and the eval plane (*was the output good?*). It answers *"what did the learner
do?"* and lays the trajectory spine a future **offline** self-improvement loop
([ADR-0009](0009-subject-coach-reflexion-not-on-live-path.md)) and RL-playground replay both
require — with **no live adaptation** and **no `/learn/test` serving change**
([ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md) tripwire stays
unfired).

Two structural forces make an ADR necessary now (both `⚠️ Ask-first` triggers):

1. **A new engine port + a new engine table.** The plane needs a durable, append-only home
   for events and a port to write them. That is a contract-surface change to the ADR-0006
   engine, which rides the amendment train, never a silent add.
2. **A new engine-plane *write* from the Test-Mode surface.** `test/page.tsx:7–11` documents
   the timed-test surface as sharing **nothing** with the quiz drip ("no `use_quiz`, no
   scheduler, no `sessionRepo`, no attempt/FSRS write"). Adding a `LearningEventRepo.append()`
   call from that surface **is a new coupling** — the "three call sites, not one hook"
   structure does not by itself discharge it. Whether an append-only analytics write is
   compatible with that isolation header's *intent* is a decision this ADR must own, not a
   line the spec asserts away.

The join key for coach-turn attribution (the `run_ref` semantics) was resolved in the spec's
clarify pass with first-hand evidence: `trace_id` is the only client-visible correlation id
on the SSE wire, `task_id` keys the eval record but is **not named on the wire** and is **not
in the `run_started` trace `details`** today (`langgraph_runtime.py:186–188`, `eval_capture.py:37–40`).
The `trace_id`↔`task_id` relationship is **branch-dependent** in `langgraph_runtime.py`: in the
fresh-path branch (`trace_id = uuid4()`, `run_id = uuid4()`, `task_id = run_id`) `task_id`
coincides with `run_id` — which IS on the wire via `RunStartedDomain` and already in `details`;
in the saturation branch `task_id` is an independent draw (`task_id = saturation.get("task_id") or uuid4()`,
diverging from `run_id = trace_id`); in the workflow-id branch `task_id` comes from `values`.
So the crosswalk cannot rely on a `run_id == task_id` assumption across branches. Decision:
`run_ref` stores **`trace_id`** (zero wire change), and clause 7 adds `task_id` to the black-box
`run_started` trace `details` as a **named, branch-uniform source** so the D5 job can resolve
`run_ref (=trace_id) → task_id → eval record` offline without per-branch equality reasoning.
The join is deliberately 2-hop and meta-plane-only — the live path stays untouched (ADR-0009).
One further grounding fact shaped the coach emit: the synthetic error path at
`use_coach.ts:90` (inside `sendCoachAsk`'s `catch` block, fired when `streamRun` throws
synchronously before yielding any events) hardcodes `trace_id: "no-trace"`; the normal coach
turn path consumes the real `trace_id` from the `RunStarted` SSE event via `applyCoachEvent`
but does not today surface it to an emit site (which does not exist yet).

---

## Decision

1. **One `learning_event` table** in BOTH dialects (`schema.sqlite.ts` + `schema.pg.ts`,
   added to `ENGINE_TABLE_NAMES`), **separate from `attempt`** — analytics events are not
   attempts and must never enter FSRS scheduling reads. Columns (spec §4):
   `{id, subject (notNull default DEFAULT_SUBJECT), user_id, session_id (NULL), question_id
   (NULL), episode_id (NULL), step_index (integer notNull), run_ref (NULL), action_kind
   (notNull), payload (notNull JSON), occurred_at (notNull)}`. `id`, `occurred_at`, and
   `step_index` are **engine-assigned**. It carries `subject` — the engine-wide OCP
   discriminator every other table carries — so a future Math coach is *new rows, not a
   migration*.
2. **`LearningEventRepo` as the 12th engine port** with an **append + `meta/`-scoped read**
   surface — **applying** the [ADR-0006 #3 `AttemptRepo`](0006-subject-coach-component-protocols.md)
   posture ("write attempts; read for review my misses"), the one existing engine port that
   is append-with-a-scoped-read:
   - `append(event): Promise<LearningEvent>` — inserts one row; returns it with
     engine-assigned `id`, `occurred_at`, `step_index`. **No `update`/`delete`.**
   - `listForReplay(subject, userId, sinceOccurredAt?): Promise<LearningEvent[]>` — the
     offline-derivation read, ordered by `(episode_id, step_index)`; the analogue of
     `AttemptRepo.misses()`. **Not reachable from serving code** — it lives on the full
     `EngineDb` and the port, **not** on the `ReadableEngineDb` serving projection, and a
     ts-morph isolation lock asserts serving paths do not import it (the compiler-plus-lint
     enforcement the ADR-0011 lesson demands, not a prose claim). **NULL-`episode_id`
     handling (C3):** every emit site mints an `episode_id` per clause 5 / FR-3, so a NULL
     `episode_id` is not produced in practice; the column is `NULL` only as a defensive
     over-permission. The conformance bundle pins an explicit `ORDER BY episode_id NULLS
     LAST, step_index` parity assertion across **both** dialects (SQLite and PG differ on
     default NULL ordering) so the D5 consumer's replay order is dialect-independent. A
     follow-up tightening (R-pending) may promote the column to `NOT NULL` once the
     three emit sites are confirmed to always mint.
3. **A single typed discriminated payload.** `action_kind` is the sole event-type
   discriminant (no separate free `kind` column that could disagree with it); `payload` is a
   `z.discriminatedUnion("action_kind", …)` (every other engine entity is a typed Zod object
   per W1, so `payload` must be too). Increment-1 frozen enum: `item_served`, `hint_shown`,
   `answer_changed`, `coach_turn_shown`, `episode_start`, `episode_end`. **Reserved and
   rejected at parse:** `experience_*`, `feedback_*` (D6), `governance_*` (retention/consent).
4. **Engine-assigned, per-episode `step_index`** (0-based, monotonic, gap-free in append
   order), scoped per `episode_id` — because `occurred_at` (ms ISO) + a non-monotonic UUID
   `id` disambiguate *identity* but not *order*, and replay needs order. The store assigns it
   (a unique index `(episode_id, step_index)` makes a concurrent-append collision a hard
   error, not silent disorder); the caller never supplies it.
5. **Three emit call sites, one port, fire-and-forget** — quiz (`use_quiz`/page), timed test
   (`test/page.tsx` reducer), coach (`use_coach`/CoachPanel). A rejecting/throwing `append()`
   is swallowed and **never** blocks, fails, or alters the learner action (analytics is never
   on the correctness path — the `coach_session_marker` precedent). Episode minting authority
   is fixed per surface so two impls cannot diverge: **quiz** = the `quiz_session` id from
   `SessionRepo.open()`; **test** = a reducer-minted `uuid4` at test start (no `quiz_session`
   row); **coach-only** = a fresh `uuid4` per coach exchange (NOT keyed to/derived from
   `coach_context.question_id` — `question_id` is a column and the replay grouping key, not
   the episode id; a second coach exchange on the same question mints a new `episode_id`) —
   each bounded by explicit `episode_start`/`episode_end`.
6. **Coach `run_ref` = the real `trace_id`, or NULL — never the `"no-trace"` sentinel.** The
   coach emit first threads the real `trace_id` from the consumed `RunStarted` SSE event to
   the emit site (which does not exist today). **Threading detail (C5, verified):**
   `coach_thread_store.ts`'s `CoachThreadState` is `{threadId, turns, busy}` and
   `applyCoachEvent(turnId, evt)` consumes `UIRuntimeEvent`s — **neither carries `trace_id`
   today**. So the emit work must *add* a `trace_id`-bearing field to the store (on `ChatTurn`
   or `CoachThreadState`), not merely "surface" an existing one; `applyCoachEvent` captures it
   from the `run_started` `UIRuntimeEvent` and the emit site reads it back. The synthetic error
   path at `use_coach.ts:90` (inside `sendCoachAsk`'s `catch`
   block, fired only when `streamRun` throws synchronously before yielding any events) drops
   its `"no-trace"` sentinel and emits `run_ref = NULL` there too. When a frame carries no
   `trace_id`, `run_ref` is emitted **NULL** (a fabricated constant is worse than absent —
   attribution degrades cleanly to the time-window join). The coach `mode` is **client-derived**
   via the same `deriveCoachMode` rule ([ADR-0012](0012-subject-coach-context-contract-hint-ladder.md);
   `hasSubmittedMarker ? "post_feedback" : "pre_submit"`), NOT read from the wire (the AG-UI
   events carry no `mode`).
7. **Crosswalk source (this ADR's one server touch):** `task_id` is added to the black-box
   `run_started` trace `details` (`langgraph_runtime.py:_emit_trace`, today `{run_id,
   thread_id}`), so a `trace_id`-keyed record carries a **named, branch-uniform** `task_id`
   and the D5 job can resolve `run_ref (=trace_id) → task_id → eval record` offline **without
   per-branch equality reasoning**. The `task_id`↔`run_id` relationship is branch-dependent
   in `langgraph_runtime.py` (fresh path: `task_id = run_id`, already on the wire as
   `run_id`; saturation: independent draw; workflow-id: from `values`) — relying on
   `run_id == task_id` would couple the crosswalk to runtime-branch internals; an explicit
   `task_id` in `details` makes the source uniform. Additive; `TrustTraceRecord.details` is
   an open `dict` — **no trust-kernel type change, no re-sign**. The join itself is D5's
   spec; this ADR guarantees only the *source* exists.

**Test-Mode isolation compatibility (the clause 2-force decision).** An append-only,
read-segregated `learning_event` write from `test/page.tsx` **is compatible** with the
isolation header's *intent*. The header's stance is *no shared learning-state* — no
`use_quiz`, no scheduler, no `sessionRepo`, no attempt/FSRS write that changes the learner's
trained model. A `learning_event` append: (a) mutates **no** scheduling/mastery state and can
never feed FSRS reads (clause 1's table separation makes that structurally impossible); (b)
imports **no** `sessionRepo`/`scheduler` at the test emit site (clause 5; enforced by a
ts-morph isolation-lock test — the "three call sites, not one hook" structure is *backed* by
an import assertion, not merely claimed); (c) is fire-and-forget, so it cannot alter test
behavior even on failure (clause 5). The test surface gains an analytics *observer*, not a
coupling to the learner's trained state. The `test/page.tsx:7–11` header is **amended in the
same PR** to record this one exception explicitly (analytics-observer append permitted; no
learning-state coupling), so the header stays truthful rather than silently contradicted.
This is separate from the [ADR-0013](0013-subject-coach-test-mode-blueprint-generation-integrity.md)
serving tripwire, which is about `/learn/test` *content/serving integrity* — untouched here
(no serving change; `_test01_english_corpus.ts` byte-frozen).

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **Events as `attempt` rows + an `action_kind` column** | Analytics events would enter the FSRS/`misses` scheduling reads that `attempt` feeds; one missed filter trains the learner model on a `hint_shown` "attempt". Table separation makes that unrepresentable (the ADR-0015 clause-1 lesson). ❌ |
| **Write-only port, no read surface** (rev-1's framing) | Self-contradictory: the D5 consumer and the conformance/emit tests both read events back, and there is no engine precedent for a truly read-less write port. `AttemptRepo` is *append + scoped read* — the exact posture. Corrected to append + `listForReplay`. ❌ |
| **Read-only-for-a-governed-field posture** (the ADR-0014/0015 seam) | Those ports are read-only because a *governed* field (`reviewed`) must never be flipped by serving code — a reason that does not apply here (there is no learner-flippable governed field on an event). Applying it would forbid the very `append()` the plane exists for. ❌ |
| **Untyped `payload` + separate `kind`/`action_kind` columns** | Two type keys can disagree; an untyped JSON blob makes an inconsistent state (`hint_shown` with no rung) representable. A single discriminant + `z.discriminatedUnion` makes the mismatch a parse rejection. ❌ |
| **`occurred_at`-only ordering (no `step_index`)** | ms-resolution ties are real (two events in one millisecond) and `id` is a non-monotonic UUID — replay order would be nondeterministic exactly when the trajectory is densest. A per-episode `step_index` is the minimal ordering key. ❌ |
| **Caller-supplied `step_index`** | Two emit sites (or two impls) would diverge on numbering; races would collide. The store owns assignment + the unique index. ❌ |
| **`run_ref = "no-trace"` sentinel when the coach frame lacks a trace_id** | A fabricated constant pollutes the crosswalk with a value that looks joinable but isn't; NULL is honest and degrades to the time-window join. ❌ |
| **One shared cross-surface emit hook for all three sites** | Couples the quiz/test/coach lifecycles and breaks the `test/page.tsx` isolation the header promises. Three sites calling one port keeps the lifecycles independent. ❌ |
| **`trace_id` + `task_id` both on the SSE wire (single-row join)** | `task_id` is deliberately eval-plane-only and off the wire; putting it on the wire widens the client's trust surface for zero live benefit. The 2-hop offline crosswalk keeps the live path untouched (ADR-0009). ❌ |
| **Retention/consent (`governance_*`) shipped now** | FERPA/GDPR-adjacent (likely minor-serving) retention/export/delete is a real obligation but a *separate* increment; the namespace is reserved (rejected until specced) so the plane does not silently ship a behavioral store with no deletion story. Named + deferred, not ignored. ❌ (a stated non-goal + reserved namespace) |

---

## Rationale

Smallest surface that satisfies the D1 spec's FR-1..FR-4 while breaking no invariant: one
table + one port that **apply** (not invent) the ADR-0006 `AttemptRepo` append+scoped-read
pattern — narrow port per responsibility, in-memory + Drizzle conformance, composition-root
injection. Table separation keeps analytics structurally out of scheduling; the typed
discriminated payload keeps an inconsistent event unrepresentable; the engine-assigned
`step_index` makes replay order deterministic under ms-ties; the read-seam segregation
(`EngineDb` not `ReadableEngineDb`, + a ts-morph lock) keeps serving code unable to read the
plane, exactly as `AttemptRepo.misses` is a review-only read. The one server touch is an
additive open-dict detail field — no trust-kernel change, no re-sign, no new graph node — so
the offline crosswalk the plane is built around has its source without disturbing the live
path (ADR-0009). Scope discipline (no serving change, no live adaptation, reserved
governance namespace) keeps the ADR-0013 tripwire and the local-first posture untouched.

---

## Consequences

**Commits us to:**
- `frontend/lib/wire/engine_entities.ts` — `LearningEvent`/`LearningEventInput` +
  `LearningEventPayload` discriminated union.
- `learning_event` table in both dialects + `ENGINE_TABLE_NAMES` + the unique index
  `(episode_id, step_index)`.
- Two new `EngineDb` methods (`insertLearningEvent`, `listLearningEventsForReplay`) on the
  **full** interface only, implemented in **both** `InMemoryEngineDb` and the Drizzle seam
  (the in-memory impl is what the emit/conformance tests read).
- `frontend/lib/ports/engine/learning_event_repo.ts` + `drizzle_learning_event_repo.ts`,
  barrel export, and the engine-conformance bundle extended to run the port against both
  impls.
- `learningEventRepo` wired into `EnginePortBag` on **both** composition roots (server +
  browser).
- Three emit call sites (`use_quiz`, `test/page.tsx` reducer, `use_coach`), all
  fire-and-forget; the coach `trace_id` threading (surfacing the real `trace_id` from the
  consumed `RunStarted` event through `coach_thread_store` to the emit site, and dropping
  the `"no-trace"` sentinel at the `use_coach.ts:90` synthetic error path in favor of NULL).
- `agent_ui_adapter/.../langgraph_runtime.py` — `task_id` in the `run_started` trace details.
- **`DEFAULT_SUBJECT` single source:** all three emit sites read the `DEFAULT_SUBJECT`
  constant (not a literal `'act-english'`) when stamping `subject`; a lock test asserts no
  emit site writes a bare literal, preventing three-way drift when Math lands.
- Two enforcement tests as the code-backed backstops (the ADR-0011 "prose integrity rots"
  lesson): a **serving read-seam isolation lock** (no serving path imports `listForReplay`)
  and a **test-emit isolation lock** (the `test/page.tsx` emit imports no
  `sessionRepo`/`scheduler`).
- A **dialect-parity `ORDER BY episode_id NULLS LAST, step_index` assertion** in the
  conformance bundle (C3) so the D5 replay order is dialect-independent across SQLite + PG.
- ADR-0006 header gains the **fourth** amendment pointer **and** its port-enumeration table
  gains the 12th row (`LearningEventRepo · append(...) · listForReplay(...)` — "write events;
  read for offline replay") — not just a header line. (R1 below confirms the pre-edited
  ADR-0006 header lands in this ADR's ratification PR, not as a stale carry-over.)
- A `test/page.tsx:7–11` header amendment recording the one analytics-observer exception.

**Accepted risks / mitigations:**
- *`step_index` race × fire-and-forget composition* → `max(step_index)+1` within an
  episode races if two emits fire near-simultaneously; learn emits are user-paced and
  serialized per episode, and the unique `(episode_id, step_index)` index turns any residual
  collision into a hard error. **But** clause 5's fire-and-forget rule (FR-2.2) swallows a
  rejecting/throwing `append()` so it never blocks the learner action — so under the Drizzle
  adapter a rare concurrent-collision `append()` is **silently dropped, not surfaced** (the
  in-memory adapter is trivially serial, so this only bites under Drizzle with real
  concurrent test emits, which the spec calls "user-paced" — residual is small). The two
  risks compose to "a rare same-episode same-ms Drizzle collision silently loses one event,"
  not two independent failures; replay determinism degrades to "ordered, with a possible
  one-event gap under concurrent Drizzle appends" — acceptable for trajectory density but
  named here as a single composed accepted risk. The swallow MUST emit a warn-level log line
  (the `coach_session_marker` precedent logs, it does not surface) so the loss is observable
  in telemetry even though it never reaches the learner. In-memory is trivially serial. Named
  accepted risk.
- *`subject` default is English-only today* → coach/test events default to `DEFAULT_SUBJECT`
  ('act-english'); correct now, and the column exists so a Math coach is new rows, not a
  migration (OCP). Mitigated by construction.
- *No deletion/retention story ships* → **stated non-goal** of this increment; the
  `governance_*` namespace is reserved and rejected until specced. The gap is named and must
  be closed **before any production enablement** — not silently deferred.
- *Coach `run_ref` NULL rate* → until the `trace_id` threading lands and is verified, coach
  attribution degrades to the time-window join; the NULL-not-sentinel rule keeps the
  crosswalk clean meanwhile. A test asserts NULL (never `"no-trace"`) on a trace-absent frame.
- *Test-page coupling creep* → the analytics-observer exception is the *only* permitted
  engine write from the test surface; the ts-morph import lock fails any future
  `sessionRepo`/`scheduler` import, so the exception cannot silently widen.
- *Dev with no `DATABASE_URL`* → events land in `InMemoryEngineDb` and vanish on restart;
  acceptable for dev, documented, not a failure (the emit/conformance tests read the
  in-memory store).

---

## Findings & recommendations (ratification record)

Two review passes against the codebase. The first produced four **blocking findings** (C1–C4,
discharged in-text). A **second independent verification pass** (2026-07-04) re-checked every
discharged finding first-hand against the source and confirmed C1/C2 (they overturned real
overclaims in the pre-ratification draft), then surfaced one further precision finding (C5,
discharged) and one evidence-basis correction. Four **non-blocking recommendations** (R1–R4)
are tracked as follow-ups. Recorded here so the rationale for the amendments is durable, not
just the amended text.

### Blocking findings — discharged at ratification (conditions met)

- **C1 — `task_id`/`run_id` grounding (Context + clause 7).** The original draft asserted
  `task_id` is "not on the wire and an independent `uuid4()` draw." First-hand inspection of
  `langgraph_runtime.py:170–188` shows the relationship is **branch-dependent**: fresh path
  sets `task_id = run_id` (so `task_id` IS on the wire as `run_id` and already in `details`);
  saturation branch draws `task_id` independently; workflow-id branch takes it from `values`.
  FR-4.1's `task_id`-in-`details` addition is still warranted — for branch uniformity and
  the saturation/workflow-id cases — but the justification was corrected to "a named,
  branch-uniform source rather than a `run_id == task_id` assumption." **Discharged:** Context
  and clause 7 rewritten.
- **C2 — `use_coach.ts:90` citation (Context + clause 6).** The original draft characterized
  line 90 as the normal coach emit path "discarding the real trace." Line 90 is inside
  `sendCoachAsk`'s `catch` block — the synthetic `run_error` fired only when `streamRun`
  throws synchronously before yielding events; there is no real trace to discard there. The
  normal path consumes `trace_id` from `RunStarted` via `applyCoachEvent` but does not surface
  it to an emit site (which doesn't exist yet). **Discharged:** Context and clause 6 rewritten
  to reflect the error-path vs normal-path distinction; the prescription (NULL-not-sentinel)
  is unchanged and still correct.
- **C3 — `listForReplay` NULL-`episode_id` handling (clause 2).** The column spec permits
  `episode_id (NULL)` but FR-3 mints an episode at every emit site, so NULL is a defensive
  over-permission, not a produced value. SQLite and PG differ on default NULL ordering in
  `ORDER BY`, so an unspecified `ORDER BY episode_id, step_index` would make replay order
  dialect-dependent. **Discharged:** clause 2 now pins an explicit `ORDER BY episode_id NULLS
  LAST, step_index` parity assertion in the conformance bundle; a follow-up (R-pending) may
  promote the column to `NOT NULL` once all three emit sites are confirmed to always mint.
- **C4 — `step_index` race × fire-and-forget composition (Consequences).** The two accepted
  risks were listed independently, but they compose: a rare same-episode same-ms Drizzle
  collision throws, and FR-2.2's fire-and-forget swallows the throw, so the event is
  **silently dropped, not surfaced** — neither "retry" nor "observe" as the original text
  claimed. **Discharged:** the Consequences block now names this as a single composed
  accepted risk and requires the swallow to emit a warn-level log line (the
  `coach_session_marker` precedent logs, it does not surface) so the loss is observable in
  telemetry.
- **C5 — coach `trace_id` threading path (clause 6), verification pass.** Clause 6 originally
  read "threads the real `trace_id` … through `applyCoachEvent`/`coach_thread_store` to the
  emit site," implying the store already carries `trace_id`. First-hand check of
  `coach_thread_store.ts:29–37,84` shows `CoachThreadState` is `{threadId, turns, busy}` and
  `applyCoachEvent(turnId, evt: UIRuntimeEvent)` — **neither holds a `trace_id`**. The store
  must *gain* a `trace_id`-bearing field (on `ChatTurn` or `CoachThreadState`); the value
  cannot merely "surface" through an existing one. **Discharged:** clause 6 now states the
  store must add the field. This is R1/G4a work (the emit site "does not exist today"), so it
  is a precision fix, not a contradiction — but the imprecise wording could have led the
  implementer to look for a field that isn't there.

### Non-blocking recommendations (tracked follow-ups, not gating)

- **R1 — ADR-0006 pre-edit confirmation.** ADR-0006's header and port-enumeration table
  already contain the ADR-0016 amendment pointer and the 12th row at ratification time
  (`0006-…md:24–29, 69`). Confirm this pre-edit lands in the **same PR** as ADR-0016's
  ratification (and is not a stale carry-over) so ADR-0006 never advertises a port that
  doesn't exist should ADR-0016 be revised. `tests/architecture/test_adr_ratchet.py` is the
  mechanical backstop; a green run after the ratification PR is the evidence.
- **R2 — Mechanical retention/enablement guard.** The ADR's own ADR-0011 lesson ("prose
  integrity rots; mechanical checks do not") argues for a parallel to ADR-0013's
  `COACH_TEST_KEYS_CLIENT_SERVED` flag. The proposed serving read-seam isolation lock already
  prevents serving reads; consider extending it (or a sibling test) to fail if any
  non-`meta/`, non-test consumer wires a `learning_event` read **and** no `governance_*`
  `action_kind` has been specced — i.e. "no production enablement without a retention story"
  is mechanically enforced, not asserted. File as a follow-up task; not blocking this ADR.
- **R3 — Spec sync (coach-only episode_id).** Clause 5 now clarifies that the coach-only
  `episode_id` is a **fresh `uuid4` per coach exchange**, with `question_id` as the replay
  grouping column (not the episode id). The D1 spec's FR-3.3 still reads "keyed to
  `coach_context.question_id`," which this ADR's wording supersedes. Open a parallel spec
  edit (`coach-learning-analytics.spec.md` FR-3.3 + §4 column note) so spec and ADR do not
  diverge. Tracked; not blocking.
- **R4 — `DEFAULT_SUBJECT` single-source lock.** Consequences now commits all three emit
  sites to read the `DEFAULT_SUBJECT` constant (not a literal) and adds a lock test. This
  prevents three-way drift when Math lands. Implementation-time detail; recorded so the
  implementer does not silently pick a literal.

### Evidence basis

Grounding verified first-hand against: `test/page.tsx:7–11` (isolation header, verbatim);
`schema.pg.ts:321–333` (11 `ENGINE_TABLE_NAMES` → 12 after); `attempt_repo.ts:22–28`
(`record`/`misses` posture); `langgraph_runtime.py:114–199` (`_emit_trace` signature,
`run_started` details, three-branch `task_id`/`run_id`/`trace_id` derivation);
`eval_capture.py:37–40` (`task_id`-keyed, no `trace_id`); `ag_ui_events.ts:51–60`
(`raw_event.trace_id` optional); `use_coach.ts:71–95` (catch-block location of the
`"no-trace"` sentinel, verified line 85–94); `coach_thread_store.ts:29–37,84`
(`CoachThreadState` + `applyCoachEvent`, neither carries `trace_id` — C5); `test/page.tsx:1–11`
(isolation header verbatim, incl. its own "Grep the imports" invitation); `docs/adr/0009`
(offline-only loop constraint). The ts-morph/AST isolation-lock pattern the two enforcement
tests follow is established — the layering walker `frontend/tests/architecture/test_frontend_layering.test.ts`
(the architecture-test home) and the CSP AST checker `frontend/scripts/check_csp_strict.ts`
(a sibling `scripts/` pattern, not itself in the architecture-test dir — the new isolation
locks belong in `frontend/tests/architecture/`). ADR-0006 amendment chain (0011 → 0014 →
0015 → 0016) and the four-layer invariants checked against root `AGENTS.md` and
`tests/architecture/`.

---

## Supersedes / related

Applies (does not supersede) the [ADR-0006 #3 `AttemptRepo`](0006-subject-coach-component-protocols.md)
append+scoped-read precedent as the fourth ADR-0006 amendment. Canonicalizes the
[D1 spec](../plan/coach-learning-analytics.spec.md) / [plan](../plan/coach-learning-analytics.plan.md)
/ [tasks](../plan/coach-learning-analytics.tasks.md) /
[task design](../plan/coach-learning-analytics.design.md). The D5 offline derivation + crosswalk
(`trace_id → task_id → eval`) is a **sibling spec** (`coach-learning-analytics-derive.spec.md`,
to author) that consumes clause 7's crosswalk source; it is referenced, not decided, here.
