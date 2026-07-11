---
type: decision-record
title: 'ADR-0026: SessionRepo.listByLearner — new read on the existing engine port for derived trust signals'
status: accepted
created: 2026-07-10
updated: 2026-07-10
owner: Rajnish Khatri
related: docs/plan/preact-parity-C1-dashboard-rail.spec.md, docs/plan/preact-parity-sprint-board-C.md, docs/adr/0006-subject-coach-component-protocols.md, docs/adr/0011-subject-coach-engine-learner-read-port.md
tags: [decision-record, epic-c, engine-ports, dashboard-rail]
---

# ADR-0026: `SessionRepo.listByLearner` — new read on the existing engine port for derived trust signals

**Status:** Accepted — 2026-07-10 (ratified at the C1 tasks→implement human gate).
**Related:** [C1 dashboard-rail spec](../plan/preact-parity-C1-dashboard-rail.spec.md), [Epic C sprint board](../plan/preact-parity-sprint-board-C.md), [ADR-0006 (`SessionRepo` established)](0006-subject-coach-component-protocols.md), [ADR-0011 (`LearnerReadRepo` — the precedent for a new port)](0011-subject-coach-engine-learner-read-port.md).
**Audience:** Anyone extending an engine port, especially for Dashboard/Progress-style derived signals across Epics C→F.

---

## Context

Epic C sprint C1 restores two "coach who knows you" surfaces on the Dashboard —
a personalized greeting and a right rail with **streak** and **weekly-session**
tiles ([spec §1–2](../plan/preact-parity-C1-dashboard-rail.spec.md)). The C-4
honesty rule (Epic B) forbids placeholder numbers; every tile must be a real
count or an honest empty state.

The Stage-1 brainstorm audit ([preact-parity-epic-C.brainstorm.md §P8](../plan/preact-parity-epic-C.brainstorm.md))
**refuted** the premise that streak and weekly-sessions were derivable today.
`SessionRepo` currently exposes `open`/`close`/`get` **only**
([session_repo.ts:39-58](../../frontend/lib/ports/engine/session_repo.ts:39)).
Neither the Dashboard nor any other consumer can list a learner's closed
sessions.

Three forces:

1. **Honesty (C-4).** The tiles must render zero when there is nothing to
   show, and a real number when there is. Deriving from an in-memory session
   cache violates the honesty rule the moment the tab is closed.
2. **Independent releasability (Epic program §4).** C1 must ship alone. It
   cannot wait on Epic F's Progress screen to justify a new abstraction.
3. **Abstraction-introduction rule (root [AGENTS.md](../../AGENTS.md) §G1,
   frontend style guide §"Ports").** Do not create a new port until a second
   consumer arrives. Today the Dashboard is the only consumer; Epic F is
   ADR-gated and unshipped.

The spec grounds every seam it touches; no premise is unverified.

---

## Decision

Add **one new method** to the existing `SessionRepo` port:

```typescript
listByLearner(
  subject: string,
  learnerId: string,
  options?: { sinceISO?: string },
): Promise<QuizSession[]>;
```

Contract: closed sessions only (`ended_at != null`); newest-first (`ended_at
DESC`, `id ASC` tiebreak); `sinceISO` is an optional inclusive lower bound the
caller passes to keep the read bounded; empty result → `[]`, never `null`,
never throw; rejections → `EngineRepoError`.

Ship on both the live Drizzle adapter (`DrizzleSessionRepo`) and the
in-memory behavioral fake (`InMemoryEngineDb`); the existing conformance
suite (`engine_repos.test.ts`) parametrizes the same behavioral assertions
across both.

Do **NOT** create a new `LearnerStatsRepo` horizontal port; do NOT put the
derivation in a component; do NOT compute the signals server-side.

---

## Options considered & rejected

| # | Option | Verdict | Why it lost |
|---|--------|---------|-------------|
| **A** | **`SessionRepo.listByLearner` (chosen)** | ✅ **Accepted** | Smallest change that closes the honesty gap; keeps P1 (one interface per file — adding a method is not a new interface); rides an existing port that already owns session lifecycle. Sets up Epic F's Progress screen as the second consumer without freezing port shape today. |
| **B** | Client-side derivation from an in-memory session cache | Rejected | Violates C-4 honesty the moment the tab closes or the learner returns tomorrow. The "streak" the learner sees would depend on whether they refreshed. Frontend Ring §14 rule against parallel client stores also applies (a session cache mirroring persistence). |
| **C** | New horizontal port `LearnerStatsRepo` (D3 in the brainstorm) | Deferred to Epic F | The abstraction-introduction rule (root AGENTS.md §G1) requires **two consumers** before promoting to a new port. Dashboard is one; Epic F's Progress screen is the second — but Epic F is ADR-gated and unshipped. Pulling forward its port design today freezes surface area before we know it. When Epic F arrives, `listByLearner` (+ any future methods) can be lifted to a `LearnerStatsRepo` port in one atomic move — this ADR does not preclude that; it defers it. Precedent: [ADR-0011](0011-subject-coach-engine-learner-read-port.md) split `LearnerReadRepo` out of `SchedulerRepo` the moment the second consumer arrived. |
| **D** | Compute streak/weekly at the middleware / server side | Rejected | The engine lives in the Frontend Ring per [ADR-0005](0005-subject-coach-engine-home-and-substrate.md) (`Frontend-Ring local-first`). Moving derivation to the server would invert the plane and forbid the offline-safe posture ADR-0005 defends. |
| **E** | Leave the rail out until Epic F ships | Rejected | Sacrifices C1's visible parity gain; loses the "coach who knows you" increment. The honest-absent posture (rail with two real tiles + explicitly-deferred score-goal + coach-note tiles) already ships less-than-100% built — this option would ship 0%. |
| **F** | Add `listByLearner` **without** a `sinceISO` bound | Rejected | The read would scale linearly with learner history — fine for Maya's Phase-1 demo, regresses when multi-learner + years of data land. `sinceISO` is an easy optimization the caller can honor today (spec §4.1 = 30 days); making the port window-agnostic keeps future consumers free to pass their own bound. |

---

## Rationale

Option A is the smallest honest step. It:

- **Preserves invariants.** P1 (one interface per port module) preserved — a
  new method on an existing interface is not a new interface. F-R3 preserved.
  #7 (services must not import from components) preserved — the port lives
  under `frontend/lib/ports/engine/`. #1 (dependency direction) preserved —
  translators consume the returned wire shape, never the adapter.
- **Respects abstraction-introduction.** The C1 spec + this ADR name the exact
  trigger that would justify promotion to a new port: the arrival of a second
  consumer (Epic F). Until then, the method sits on the port that already
  owns session lifecycle.
- **Ships alone.** No cross-sprint dependency, no shared substrate, no
  ⚠️ Ask-first item beyond G1 (which this ADR resolves).
- **Honors C-4.** The derivation is a pure translator (`streak_vm`,
  `weekly_sessions_vm`, `greeting_vm`) reading a real engine read. Empty →
  honest empty state ("Start a streak", "0 / 3 sessions"), never a placeholder.
- **Reuses the conformance suite.** The parametrized `engine_repos.test.ts`
  already asserts adapter-agnostic behavior across `InMemoryEngineDb` and the
  live Drizzle seam. One new row per adapter covers the new method.

The `sinceISO` bound in the port signature is a caller-facing hygiene lever,
not a requirement: omitting it returns all closed sessions. The Dashboard
passes `nowISO - 30 days` (C1 spec §4.1, decision Q2) so the read stays
cheap as multi-learner history grows. Future consumers pick their own bound.

---

## Consequences

**Commits us to:**

- The port shape now carries `listByLearner`. Any future `SessionRepo`
  reimplementation (V2 substrate, multi-learner, sync engine) must
  provide it.
- The `EngineDb` row-level port grows one method
  (`listClosedSessionsByLearner`); both `InMemoryEngineDb` and
  `drizzleEngineDb` implement it (test-parity: L2 conformance row + L3 live
  Drizzle when a DB is available — see [ADR-0010](0010-subject-coach-engine-ports-realization-and-ts-fsrs.md)).
- The Dashboard's `EnginePortBag` already carries `sessionRepo`
  ([composition_engine.ts:68](../../frontend/lib/composition_engine.ts:68));
  no composition-root change required — the new method rides the existing
  bag.
- The spec's `decisions.md` entry for `sinceISO = 30 days` (Dashboard caller
  policy) documents the ratchet — raising it later is a spec change, not a
  port change.

**Accepted risks + mitigations:**

- **Risk:** the C1 tiles create a de-facto second interface (streak +
  weekly + future score-goal) that will want to become `LearnerStatsRepo`
  before Epic F formally arrives. **Mitigation:** the C1 DoD explicitly
  rejects score-goal and coach-note tiles (spec FR-14); the port grows one
  method today, not four. When Epic F arrives, promotion is a mechanical
  refactor (new port file + move `listByLearner` + update composition + one
  ADR).
- **Risk:** `sinceISO` = 30 days is Dashboard-appropriate but wrong for a
  future audit tool that needs 6 months of history. **Mitigation:** the
  bound is caller-owned, not port-owned. Any future consumer picks its own.
- **Risk:** the Drizzle query on `quiz_session` for `learner_id + subject +
  ended_at IS NOT NULL + ended_at >= sinceISO` needs an index to stay cheap
  at scale. **Mitigation:** at Phase-1 single-learner scale, sequential scan
  is fine; when multi-learner lands, a `(subject, learner_id, ended_at
  DESC)` composite index is a follow-up migration flagged in the plan.

**Follow-on work (not in C1):**

- Epic F Progress screen — likely the second consumer that triggers the
  `LearnerStatsRepo` port lift.
- `SessionRepo.listRecent(...)` — a fleet-wide (not per-learner) read a
  future ops surface would want. Not built today; not designed today.
- Composite DB index on `(subject, learner_id, ended_at DESC)` — deferred
  until multi-learner ships.

---

## Supersedes / related

- **Amends** [ADR-0006](0006-subject-coach-component-protocols.md) with a
  new method on the `SessionRepo` port (fifth amendment to the seven
  Frontend-Ring engine ports; the amendments so far are ADR-0011, ADR-0014,
  ADR-0015, ADR-0016, and this).
- **Precedent** [ADR-0011](0011-subject-coach-engine-learner-read-port.md)
  — split a new read port out of the Scheduler when the second consumer
  arrived. This ADR defers the analogous `LearnerStatsRepo` split for the
  same reason (single consumer today).
- **Realizes** [preact-parity-C1-dashboard-rail.spec.md](../plan/preact-parity-C1-dashboard-rail.spec.md).
