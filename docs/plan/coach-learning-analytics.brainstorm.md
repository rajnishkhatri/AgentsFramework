---
type: brainstorm
title: 'Coach learning-analytics event plane — behavior / experience / feedback'
status: 'Stage-1 CLOSED (2026-07-03) — gate: G-A=D1, G-B=YES, G-C=(i,ii) defer(iii,iv,v); corrections C1–C3 binding on spec → sdd-spec next'
authored: 2026-07-03
---

# Brainstorm — Coach learning-analytics event plane (behavior / experience / feedback)

> **SDD Stage-1 artifact** (`brainstorm`). Idea-expansion for a **third signal plane**
> on the Subject-Coach pipeline: learner-side analytic events (behavior, experience,
> explicit feedback) for **coach + test mode**, distinct from the governance plane
> (`governanaceTriangle/` pillars) and the eval plane (grounded-theory judges). Two
> consumers shape the schema: a near-term **offline self-improvement loop** and future
> **RL-playground trajectory data**. It does **not** decide (an ADR will) and contains
> **no code**.
>
> **Status:** Draft — 2026-07-03 · **Owner:** Rajnish Khatri
> **Related:**
> - Parent program: [`subject-coach-agent.plan.md`](subject-coach-agent.plan.md) · [`subject-coach-agent.spec.md`](subject-coach-agent.spec.md)
> - Constraints inherited: [ADR-0009](../adr/0009-subject-coach-reflexion-not-on-live-path.md) (reflection offline-only), [ADR-0012](../adr/0012-subject-coach-context-contract-hint-ladder.md) (context contract), [ADR-0013](../adr/0013-subject-coach-test-mode-blueprint-generation-integrity.md) (test-mode integrity), [ADR-0014](../adr/0014-subject-coach-hint-repo-read-seam.md)/[ADR-0015](../adr/0015-subject-coach-test-item-bank-blueprint-read-seam.md) (read-seam precedents)
> - Eval plane this plane must NOT duplicate: [`meta/subject_coach_judge_sampler.py`](../../meta/subject_coach_judge_sampler.py), [`meta/subject_coach_corpus_harvest.py`](../../meta/subject_coach_corpus_harvest.py)

---

## 1. Intent (restated)

The pipeline already answers two questions with dedicated planes:

| Plane | Question it answers | Machinery |
|---|---|---|
| **Governance** | "Did the *system* behave correctly, provably?" | BlackBox recording, AgentFacts identity, GuardRails validation, PhaseLogger reasoning; per-turn `coach_context_contract` carrier (`orchestration/react_loop.py:1243`) |
| **Eval** | "Was the *LLM output* good, graded against a rubric?" | `target="subject_coach"` eval records → judge sampler → paired Grader/Pedagogy verdicts (`target="coach_judges"`) |

Missing: **"What did the *learner* do, experience, and say?"** Three signal families —
**behavior** (retries, hesitation latency, hint requests, answer changes, abandonment,
time-on-item), **experience** (flow/frustration proxies, completion vs bail-out),
**feedback** (ratings, "this hint didn't help", free-text). Two consumers with
different schema requirements:

1. **Offline self-improvement loop** — the coach's *content and config* adapt from
   accumulated learner signal (hint-ladder revision, persona tuning, blueprint
   difficulty mixes). Per ADR-0009 this loop is **offline-only**; live adaptation flows
   exclusively through deterministic engine state (`misses_aggregate`,
   `mastery_snapshot` already ride `coach_context` — spec §4).
2. **RL playground data (future)** — the stream must replay as trajectories
   `(state, coach action, learner response, outcome/reward)` with **episode boundaries
   and action attribution as first-class fields now**; they cannot be reconstructed
   later from a flat click log.

---

## 2. Premise audit

Every load-bearing premise checked against the working tree (2026-07-03, branch
`feat/subject-coach-agent`).

| # | Premise | Status | Evidence |
|---|---|---|---|
| P1 | Coach + test-mode learner surfaces exist | **verified** | `frontend/app/(coach)/learn/` — dashboard, `quiz/page.tsx`, `test/page.tsx`, `summary/page.tsx`, `coach/page.tsx`; CoachPanel + coach screen share `coach_thread_store` (`frontend/components/coach/coach_thread_store.ts`); coach turns reach the backend via `use_coach.ts` → `frontend/app/api/coach/run/stream/route.ts` → middleware → graph |
| P2 | Governance plane covers the coach path and is genuinely separate | **verified** | `coach_context_contract` recorded as one `guardrail_checked` carrier per coach turn (`orchestration/react_loop.py:1243–1253`); `eval_capture` `target="subject_coach"` (5 call sites); Phase-1 §13 governance audit PASS in the plan ledger |
| P3 | Eval plane exists and is mode-aware | **verified** | `meta/subject_coach_judge_sampler.py` (task_id-hash sampling, paired verdicts, AP-6 undecidable-never-recorded); `meta/subject_coach_corpus_harvest.py` (shadow traffic → corpus, ≥100 turns/mode gate) |
| P4 | **No learner-behavior analytics exist (the gap is real)** | **verified — with two live surprises** | Zero matches for analytics/track/emitEvent/logEvent/PostHog/Amplitude across `frontend/` + `middleware/`. `TelemetrySink` port exists (`frontend/lib/ports/telemetry_sink.ts`) but its **only** implementation is `NullTelemetrySink` (`frontend/lib/composition.ts:82–86,137`) — fully speced, 100% inert. Partial signal persisted: `attempt` rows carry `chosen_letter, correct, elapsed_ms, used_hint, created_at` (`frontend/lib/ports/engine/attempt_repo.ts:22–28`) — **but `elapsedMs: 0` is hardcoded at the submit call site** (`frontend/app/(coach)/learn/quiz/page.tsx:121`, verified first-hand); `used_hint` is a bare boolean (which rung, when — unrecorded). Test mode persists **nothing** by documented design ("no use_quiz, no scheduler, no sessionRepo, no attempt/FSRS write" — `frontend/app/(coach)/learn/test/page.tsx:7–11`). Coach threads are **not persisted** ("a full page reload starts a fresh thread" — `coach_thread_store.ts:16–19`) |
| P5 | Existing transports can carry the new plane | **verified (characterized §5)** | Engine Drizzle DB: 11 tables (`ENGINE_TABLE_NAMES`, `schema.pg.ts:321–333` — corrected from a stale "9"; `test_item`/`test_blueprint` landed with Phase 6), no event/log table; `selectEngineDb()` is a binary in-memory/pg switch (`frontend/lib/composition_engine.ts:77–85`) — the SQLite "on-device twin" is schema-only, **no sync/outbox exists**; `coach_session_marker` `{user_id, question_id, submitted_at}` is a live INSERT-only fire-and-forget event-row precedent (`frontend/lib/adapters/coach_marker/db/schema.ts:19–29`); BFF thread store (Neon/pg) server-side |
| P6 | Trajectory-readiness exists somewhere today | **refuted → re-posed** | Episode boundaries: **partially yes** — `SessionRepo.open()/close()` gives `quiz_session` rows `started_at/ended_at` + score (`frontend/lib/ports/engine/session_repo.ts:33–47`). Action attribution: **no** — nothing records which hint rung was shown or when (`HintRepo.list()` is read-only, `hint_repo.ts:26–29`), coach turns aren't persisted client-side, and test mode has no session rows at all. **Re-posed framing:** trajectory-readiness is not a property to preserve but a property to *introduce*; the schema decision (D4) is where it's won or lost. |

**Corrected framing after audit (P6 re-pose):** the ask is not "add capture to a
surface that lacks it" — it is "add capture *and* create the attribution spine
(episode / action / response linkage) that no current row carries."

## 3. D0 — live defect ahead of any direction

`attempt.elapsed_ms` — the one behavioral field the schema already supports — is a
dead stub: `elapsedMs: 0` hardcoded (`frontend/app/(coach)/learn/quiz/page.tsx:121`;
plumbing exists end-to-end through `use_quiz.ts:113,146` into the row). Every attempt
row written to date carries a fabricated timing value — which also poisons any future
backfill ("why were all 2026 attempts instant?"). **Fix regardless of direction
choice** (wire the real per-question timer; small, no ADR). A present defect in the
only existing behavioral signal outranks every new-capability direction.

---

## 4. Directions

Three high-probability (named repo pattern each) + three exploratory. All six respect:
no `/learn/test` serving change (ADR-0013 tripwire), no trust/ changes, reflection
offline-only (ADR-0009), learner content never in logs (O2 — content belongs in DB
rows, as `attempt.chosen_letter` already establishes).

### D1 — `learning_event` append-only table + write port on the engine plane *(lead candidate)*

One generic event row on the engine DB (both dialects):
`{id, user_id, session_id?, question_id?, run_ref?, kind, payload, occurred_at}` with a
narrow **write-only** engine port (`LearningEventRepo.append(event)`) emitted from
quiz/test/coach components through one hook.

- **Pattern followed:** `coach_session_marker`'s INSERT-only fire-and-forget write
  (`frontend/lib/adapters/coach_marker/db/schema.ts`) + the ADR-0014/0015 port-per-seam
  discipline; table added to `ENGINE_TABLE_NAMES` like `test_item` will be.
- **Class over instance:** one append seam + one event union type — not per-widget logging.
- **Tradeoffs / what breaks:** this is the engine plane's **first write-surface port**
  — ADR-0014/0015 deliberately kept ports read-only ("serving code can never flip
  `reviewed`"). An append-only, learner-generated event stream doesn't violate that
  *reason* (nothing governed is writable) but it breaks the *pattern*, so the ADR must
  argue it explicitly. ⚠️ Ask-first: new port + new table ⇒ **new ADR** (12th port).
- **Invariants stressed:** F-R2 (emit hook must stay SDK-free), engine-port growth cap.

### D2 — Activate the inert `TelemetrySink` seam

Implement the first real `TelemetrySink` adapter (browser → batched BFF route →
server store/Langfuse), and emit learner events as spans/events.

- **Pattern followed:** the O-family observability contract already fully speced on the
  port (`frontend/lib/ports/telemetry_sink.ts`; non-blocking, trace_id-bearing) — the
  textbook **under-used signal**: a designed seam with a `Null` implementation.
- **Tradeoffs / what breaks:** the port's contract is RUM-shaped (`span`, `error`) and
  O2 forbids content in telemetry — so **feedback text and answer payloads cannot ride
  it**; fire-and-forget browser emission is lossy (tab close, ad-block → attrition
  bias, worst exactly on the abandonment events we most want). Good for *timings*,
  wrong as the plane's system of record.
- **Invariants stressed:** O1/O2; no ADR needed for the adapter itself (port exists).

### D3 — Demand-side: enrich rows already being written (derive, don't emit)

No new plane. Fix D0; add `hint_rung_shown`, `answer_changes`, `first_interaction_ms`
to `attempt`; persist test-mode attempts (new `test_attempt` row); make coach threads
durable (promote `coach_thread_store` to a persisted store keyed by session).

- **Pattern followed:** schema-extension-in-both-dialects (ADR-0015's `test_item` recipe).
- **Tradeoffs / what breaks:** experience/feedback families have **no home** (no
  ratings, no abandonment — you can't derive a signal from a row that's only written on
  submit); persisting test-mode attempts **re-opens a documented deliberate decision**
  (test page's isolation header) and coach-thread persistence re-opens
  `coach_thread_store`'s "deliberately not persisted" stance — each needs its own
  justification, not a silent flip. Schema churn on core scheduling tables.
- **Honest role:** the *derivable* half of the plane; pairs with (doesn't replace) D1.

### D4 — Trajectory-first schema: episodes + steps as the primary shape *(exploratory)*

Design the store RL-native from day one: `episode` (question-scoped within a session)
and `step` rows `{state_ref, action {kind: item_served | hint_shown(rung) | coach_turn(run_ref)},
learner_response, outcome}` — behavior/experience/feedback become *step payloads*, not
a flat click log.

- **Why exploratory:** inverts D1's shape (events derived from trajectories instead of
  trajectories reconstructed from events). Strongest guarantee that RL replay works —
  attribution is structural, not join-time.
- **Tradeoffs / what breaks:** heavier contract to design before *any* signal flows;
  risks duplicating the governance recording plane for the coach-turn action (the run
  is already recorded server-side — the step row should hold a `run_ref`/`task_id`
  **pointer**, never a copy, or the two planes drift); YAGNI risk if the RL consumer
  never arrives. Mitigation: adopt D4's *fields* (episode_id, action attribution,
  run_ref) as **constraints on D1's schema** rather than a separate machinery.

### D5 — Server-side derivation only: a `meta/` journey-join job *(exploratory, demand-side extreme)*

No client capture at all. A `meta/` job (mirroring `subject_coach_corpus_harvest.py`)
joins what the server already has — `target="subject_coach"` eval records (mode,
task_id, user_id) × `coach_session_marker` (submit times) × `attempt`/`quiz_session`
rows — into learner-journey rows offline.

- **Pattern followed:** the harvest job's exact shape (reads logs/config, invariant #8
  clean, idempotent by task_id).
- **Coverage ceiling (measured, §2 P4):** blind to hesitation, hint-rung usage,
  abandonment, everything in test mode, and all experience/feedback signal — the P4
  audit *is* the ceiling. Signal quality: high (server-truth), coverage: low.
- **Honest role:** Phase-A stopgap + the *join-spine rehearsal* (task_id/user_id keys)
  while D1 lands; also the cheapest way to learn which joins break before committing
  the event schema.

### D6 — Explicit-feedback surface: ratings + micro-surveys *(exploratory, product-visible)*

Per-coach-turn thumbs / "did this hint help?" chips / post-session one-tap survey —
the only **ground-truth** experience/feedback source, and the highest-value reward
signal for the future RL consumer (everything else is proxy).

- **Tradeoffs / what breaks:** learner-visible UI change (product decision, a11y
  + i18n `t()` obligations per the frontend guide); response + selection bias (who
  rates?); **depends on a storage substrate** — D6 emits *into* D1's table (or is
  blocked until it exists). Feedback text is learner content: DB rows only, never logs.
- **Signal characterization:** coverage low / quality highest / bias class:
  self-selection.

---

## 5. Transport characterization (P5 detail)

| Candidate | Coverage | Quality | Bias / failure class | Verdict |
|---|---|---|---|---|
| Engine Drizzle DB (new table, D1) | All learn surfaces incl. test mode | Durable, queryable, joins to `attempt`/`quiz_session` natively | In-memory fallback when no `DATABASE_URL` (dev) — events vanish; acceptable for dev | **System of record** |
| `TelemetrySink` → Langfuse/BFF (D2) | Browser sessions that flush | Non-blocking by contract | Lossy on close/ad-block → undercounts abandonment; O2 bars content | Timing/RUM side-channel only |
| eval_capture / Cloud Logging (existing) | Every coach LLM turn | Server-truth | Only sees turns that reach the LLM — no client behavior | Join target (`task_id`), not a carrier |
| `coach_session_marker` store | Quiz submits | Minimal but live | Boolean-shaped | Write-pattern precedent |
| SQLite on-device twin + sync | — | — | **Does not exist** (no outbox/sync; `selectEngineDb()` binary) | `needs-probe` if iPad-offline capture ever required |

## 6. Hypotheses for the lead (D1 constrained by D4, with D0+D5 regardless) — validated

- **H1 — "wires like existing engine adapters"** — VALIDATED: composition seam exists
  and is the single adapter-selection point (`frontend/lib/composition_engine.ts:77–85`);
  table registration pattern (`ENGINE_TABLE_NAMES`, `schema.pg.ts:276–286`); in-memory +
  Drizzle conformance-bundle recipe established by the 9 existing tables and rehearsed
  again in ADR-0015's commitments.
- **H2 — "safe because additive and off the serving path"** — VALIDATED: no change to
  `/learn/test` serving (`_test01_english_corpus.ts` untouched; ADR-0013 tripwire
  unfired), no `trust/` types, no graph node (invariant #6 untouched); rollback = drop
  table + unwire port.
- **H3 — "action attribution is capturable at emit time"** — VALIDATED for hint rung,
  **PARTIAL / gap found for the coach-turn join** (see §8 correction C1). Hint rung:
  the client renders the ladder, so the rung is in scope where the event is emitted
  (today it collapses to `used_hint` boolean at `use_quiz.ts:114,147`) — capturable.
  Coach turn: the client sees only `trace_id` on the SSE wire (`raw_event.trace_id`,
  **optional**, `frontend/lib/wire/ag_ui_events.ts:55`); it does **not** see `task_id`.
  But the eval/governance record is keyed by `task_id` (`services/eval_capture.py:38`),
  and on the live path `trace_id` and `task_id` are **independent `uuid4()` draws**
  (`agent_ui_adapter/adapters/runtime/langgraph_runtime.py:186–188`) — so `task_id` is
  **not** derivable from `trace_id`. The learner-side `run_ref` a client can capture is
  `trace_id`; joining it to the `task_id`-keyed coach record needs an explicit crosswalk
  that does not exist today. Attribution is therefore capturable, but **not** by the
  "task_id already on the wire" path the naive plan assumed — the join key is an open
  spec question (§8 C1), not a solved one.
- **H4 — "episode boundaries exist to anchor trajectories"** — PARTIALLY VALIDATED:
  quiz plane yes (`SessionRepo.open()/close()`, `session_repo.ts:33–47`); **test mode
  no** (no session rows — D1 must emit its own `episode_start/end` events there);
  coach-only sessions no (thread not persisted — episode = the enclosing
  question/session context via `coach_context.question_id`).
- **H5 — "privacy posture holds"** — VALIDATED: learner content in DB rows only
  (precedent: `attempt.chosen_letter`); events carry ids + enums + timings; O2 keeps
  content out of logs/telemetry; per-user isolation rides the existing
  `user_id` discipline (H5 rule: every LLM-adjacent record already carries
  `user_id`+`task_id`).
- **REJECTED en route:** "reuse `TelemetrySink` as the system of record" (contract
  forbids content; lossy exactly on abandonment — see D2); "trajectories can be
  reconstructed later from a flat click log" (P6 refuted: no attribution fields exist
  anywhere today — if `run_ref`/rung/episode aren't first-class at emit time, the RL
  consumer inherits an unjoinable corpus).

## 7. Dependency map & decision structure

```
D0 (fix elapsed_ms stub)          — do-regardless, no ADR, small
D5 (meta/ journey join)           — do-regardless-ish: independent, rehearses the joins
D1 (event table + write port)     — THE substrate decision (ADR required, 12th port)
 └─ constrained by D4 fields      — episode_id / action attribution / run_ref first-class
     └─ D6 (feedback UI)          — emits into D1; product-gated; unlocks ground-truth reward
D2 (TelemetrySink activation)     — orthogonal side-channel; any time; never the record
D3 (row enrichment)               — partially folded into D0/D1; the two "re-open a
                                     deliberate decision" items (test-mode persistence,
                                     coach-thread persistence) are separate consent gates
```

Two axes the human gate should split, not conflate:
- **What is the system of record** — D1-table (recommended) vs D2-telemetry vs D5-derive-only.
- **How RL-committed is the schema** — D4-constraints-on-D1 (recommended; cheap now,
  unrecoverable later) vs flat events now + hope.

Cost axes: D1+D4 is engineering time; D5/D6 are calendar time (signal must accumulate
before either consumer can use it) — the RL consumer's real cost is the wait, which is
the argument for landing the schema early.

## 8. Human gate — CLOSED (2026-07-03)

Direction-level acceptance recorded. The spec (Stage 2) inherits **this** section, not
the naive first-pass summary — three corrections (C1–C3) were folded in after a
post-gate evidence check; they are binding on the spec.

### 8.1 Decisions

| Gate | Decision | Implication |
|---|---|---|
| **G-A** | **D1** — `learning_event` append-only table + append/scoped-read port + ADR | 12th engine port → ADR required. **C3 RESOLVED at spec time: NOT the "first write port"** — `AttemptRepo`/`QuestionRepo`/`Scheduler`/`SessionRepo` already write; `AttemptRepo` is append+scoped-read ("write attempts; read for review my misses"). The ADR **applies** that precedent, not a read-only exception. See [`coach-learning-analytics.spec.md`](coach-learning-analytics.spec.md) §2. |
| **G-B** | **YES** — bake D4 trajectory fields into D1's schema from day one | D1 schema gains nullable `episode_id`, `run_ref`, `action_kind` as first-class columns. `run_ref` is a **pointer** (joins to the governance/eval record), never a copy — avoids plane drift. **Join key is unresolved — see C1.** |
| **G-C** | **(i) D0 now · (ii) D5 now** — defer (iii), (iv), (v) | D5 runs as an independent join-*rehearsal* (not yet a signal source — see C2/N1). Test-mode + coach-thread persistence reversals are deferred **contingent on C1 being resolved** (not merely on G-B=YES). D6 deferred to a second increment — but D1's `kind` enum reserves `feedback_*` namespaces now so D6 is a clean add. |

### 8.2 Binding corrections (post-gate evidence check — the honest version)

**C1 — the `run_ref` coach-turn join key is an OPEN spec question, not solved.**
The naive summary claimed "coach-turn `run_ref` rides the existing `trace_id`/`task_id`
already on the wire." Refuted by evidence: `task_id` is **never on the wire** — the
client sees only `trace_id` (`ag_ui_events.ts:55`, optional). The eval/governance record
is keyed by **`task_id`** (`eval_capture.py:38`), and on the live path `trace_id` and
`task_id` are **independent `uuid4()` draws** (`langgraph_runtime.py:186–188`), so
`task_id` is not derivable from `trace_id`. **The spec MUST resolve the join key as its
#1 clarify item**, choosing between:
- **(a) client emits `trace_id`; a server-side `trace_id → task_id` crosswalk** lands in
  the D5 job (crosswalk source: the run-start trace already carries both keys in
  `configurable` at `langgraph_runtime.py:205–210`). Cheaper; keeps the wire unchanged.
- **(b) surface `task_id` onto the wire** — a `wire/` schema change paying the
  schema-drift-gate cost (W2 baseline + Python mirror).
Recommendation: **(a)** — but this is a spec decision, not a brainstorm assertion.

**C2 — the G-C-iii/iv defer is contingent on C1, not only on G-B=YES.**
Deferring test-mode and coach-thread persistence is only safe if coach-turn attribution
works *without* persisting the thread — which requires a working learner-event → coach-
record join (C1). If C1 resolves to a real crosswalk, the defer holds; **if C1 is
punted, G-C-iii/iv become forced.** The spec must state this dependency explicitly:
`defer(iii,iv) ⟸ (G-B=YES ∧ C1-resolved)`.

**C3 — "first WRITE port" must be verified before the ADR leans on it.**
**RESOLVED at spec time (2026-07-03): the claim is FALSE — verified by grep.** Write ports
already exist: `AttemptRepo.record()`, `QuestionRepo.save()`, `Scheduler.review()`,
`SessionRepo.open()/close()`. And `AttemptRepo` is **append + a scoped read** (`misses()`,
`attempt_repo.ts:27`; ADR-0006 #3 "write attempts; read for review my misses"). So the spec
frames `LearningEventRepo` as **applying** that append+scoped-read posture — not excepting a
read-only rule, and not "first write port." (This also corrected a rev-1 spec self-
contradiction: "write-only, no read surface" was refuted by the test plan reading events
back — review B2.) See [`coach-learning-analytics.spec.md`](coach-learning-analytics.spec.md)
§2 + FR-1.4.

### 8.3 Smaller recorded notes (non-binding, carry to spec)

- **N1 — D5 immediacy is calendar-gated, not co-equal with D1.** Pre-D1, D5 can only
  join `coach_session_marker` × `attempt` × eval records (the P4 ceiling); it becomes a
  signal *source* only after D1 data accrues. It is a *join-rehearsal* now — §7 said
  this; the gate keeps it honest.
- **N2 — the emit "seam" is one port with THREE call sites, not one shared hook.**
  Quiz, timed-test, and coach are three different lifecycles (the test page shares no
  `sessionRepo`/FSRS by documented design — `test/page.tsx:7–11`). The spec says
  `LearningEventRepo.append` (one port) called from three sites emitting different
  `action_kind`s — not a single hook — so it doesn't trip the test page's isolation
  header at review.

### 8.4 Carried into Stage 2 (sdd-spec)

1. **Schema (D1 + D4):** `learning_event {id, user_id, session_id?, question_id?,
   episode_id?, run_ref?, action_kind, kind, payload, occurred_at}` — both dialects,
   added to `ENGINE_TABLE_NAMES`. `kind` enum reserves `behavior_*` / `experience_*` /
   `feedback_*`. `run_ref` join key **per C1** (do not assert `task_id`-on-wire).
2. **Port (12th, first WRITE — per C3):** `LearningEventRepo.append(event)`, write-only
   (reads via `meta/` derivation, not serving code).
3. **Emit:** one port, **three call sites** (N2); hint rung expanded from the
   `used_hint` boolean (`use_quiz.ts:114,147`).
4. **Episode boundaries:** quiz rides `SessionRepo.open()/close()`; test mode + coach-
   only sessions emit their own `episode_start/end` events (H4).
5. **ADR (12th port):** excepts the ADR-0014/0015 read-only precedent; respects ADR-0009
   (events feed offline derivation, never inline adaptation); cites the P6 audit
   (attribution introduced, not preserved). Ratifies at the spec's human gate.
6. **Do-regardless tracks:** D0 fix + D5 `meta/` journey-join job (mirrors
   `subject_coach_corpus_harvest.py`; idempotent by key). D5 doubles as the C1 crosswalk
   host under option (a).

Advance → **sdd-spec** with D1 (constrained by D4), the §6 hypotheses (H3 downgraded per
C1), and corrections C1–C3 as binding clarify inputs.
