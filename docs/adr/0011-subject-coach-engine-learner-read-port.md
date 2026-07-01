---
type: decision-record
title: 'ADR-0011: Subject-Coach engine learner read port (Phase-1 skill_state reads only)'
status: accepted
created: 2026-06-30
updated: 2026-07-01
owner: Rajnish Khatri
related: 0006-subject-coach-component-protocols.md, 0010-subject-coach-engine-ports-realization-and-ts-fsrs.md, preact-english-coach-ui.spec.md, SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md
tags: [decision-record]
---

# ADR-0011: Subject-Coach engine learner read port

**Status:** Accepted — 2026-07-01 (was Proposed — 2026-06-30; **amended 2026-07-01**
before ratification). Amends [ADR-0006](0006-subject-coach-component-protocols.md).
Ratified in the detailed-component-design adjudication
([SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §7).
**Related:** [ADR-0006 component protocols](0006-subject-coach-component-protocols.md) · [ADR-0010 ports realization](0010-subject-coach-engine-ports-realization-and-ts-fsrs.md) · [UI spec](../plan/preact-english-coach-ui.spec.md)
**Audience:** anyone wiring the Dashboard mastery grid (FR-C3) or the Session-Summary
mastery delta (FR-G1), and the eventual Screens 6/7 follow-up.

> **2026-07-01 amendment.** The original draft bundled `getTutorial` /
> `listProgressPoints` onto the same port to "avoid a second amendment when Screens 6/7
> resume." On review this was inconsistent with two sibling precedents — the four-layer
> "introduce protocols only when the second consumer arrives; document future
> abstractions now, build on demand" rule, and ADR-0010's on-device-SQLite deferral
> (no surface shipped until the consumer lands) — and it froze a port shape for the
> subjective plane (ADR-0007/0008/0009) which is still **Proposed**, not ratified. The
> amended decision ships **only the Phase-1 `skill_state` reads**; the tutorial/progress
> reads are deferred to a second amendment gated on Screens 6/7. Two further
> tightenings: the FR-G1 before/after mechanism is now specified (was silent), and the
> read-only invariant is **compiler-enforced** via a `ReadableEngineDb` projection (was
> "an architecture assertion or a code-review check" — the assert-in-prose pattern that
> forced ADR-0010's "Accepted with conditions" re-ratification).

---

## Context

The frontend UI plan's Phase 1 (Dashboard → Quiz → Feedback → Summary) needs to
**read** per-skill adaptivity state to render two things the UI spec makes normative:

- **FR-C3** — the Dashboard skill-mastery grid: each of the six bucket cards shows a
  mastery %. Mastery lives in `skill_state.mastery`.
- **FR-G1** — the Session-Summary mastery-delta stat tile (e.g. "+8%"): the difference
  between a skill's mastery before and after the session.

The seven ADR-0006 ports expose **no read path for `skill_state`.** `skill_state` is
written only by the `Scheduler` (ADR-0006 #5, the sole writer) and read internally by the
Scheduler for adaptivity. The row-level reads (`listSkillState`, `getSkillState`) exist on
the narrow **`EngineDb`** seam ([engine_db.ts:66-71](../../frontend/lib/adapters/engine/db/engine_db.ts))
and on `InMemoryEngineDb`, but `EngineDb` is the **adapter** layer — UI code must go
through a **port**, never `EngineDb` directly (Rule C2/F-R1; only `composition_engine*.ts`
names adapters). So there is no sanctioned way for `use_dashboard` / `use_summary` to read
mastery today.

This is the **same class of gap** the UI plan's Decision **D1** already flagged for
`Tutorial` (Screen 6, FR-H) and `ProgressPoint` (Screen 7, FR-I): the data is in
`EngineDb` (`getTutorial`, `listProgressPoints`) + the in-memory fake, but no ADR-0006
port surfaces it. D1 deferred Screens 6/7 pending "a small new `LearnerContentRepo` /
`EngineReadRepo` port … keeping `ContentRepo`'s labels-only boundary clean." The
`skill_state` read is the **Phase-1 instance** of that same missing port — it blocks the
core loop, not just the deferred subjective plane, so it is filed now. The tutorial/
progress reads are the **D1 instance**; they are *not* filed here (see Decision §2).

Adding a port is an `⚠️ Ask first` trigger (new abstraction, G1) + an ADR-0006 amendment
(ADR.1). Hence this record rather than an inline UI edit.

## Decision

### 1. Add one new engine port, `LearnerReadRepo`, Phase-1 surface only

`LearnerReadRepo` (F-R3: one interface per file, under
`frontend/lib/ports/engine/learner_read_repo.ts`) surfaces the **Phase-1 learner
read** the UI needs, backed by the existing `EngineDb` reads. It is vendor-neutral
(returns `wire/engine_entities` shapes only) and read-only (no writes — the
`Scheduler` remains the sole `skill_state` writer, FR-A2). Initial surface, driven by
the concrete Phase-1 FRs that need it:

```ts
export interface LearnerReadRepo {
  /** All skill_state rows for a learner (FR-C3 mastery grid). */
  listSkillState(subject: string, learnerId: string): Promise<SkillState[]>;
}
```

> **As shipped:** the port surfaces `listSkillState` only. The FR-G1 per-skill
> before/after delta is derived from two `listSkillState` reads — a
> UI-captured `skillStateAtStart` snapshot diffed against a fresh read at
> Summary (plan OD-6) — so a separate `getSkillState(subject, skillId,
> learnerId)` method is not needed and was dropped to keep the port minimal.
> If a genuine single-row read consumer arrives, add it then.

- **Name.** `LearnerReadRepo` (not `EngineReadRepo`) — the port reads *learner* state
  (`skill_state`), not engine-internal rows; the name carries that intent and leaves
  room for a future engine-internal read port without collision. The UI spec's D1
  floated both names; `LearnerReadRepo` is the better fit for what this port actually
  returns.
- **Home:** `frontend/lib/ports/engine/learner_read_repo.ts`; adapter
  `frontend/lib/adapters/engine/repos/drizzle_learner_read_repo.ts` (delegates to the
  injected `ReadableEngineDb` — see §3 — exactly like the other Drizzle repos, no new
  driver import).
- **Wiring:** added to `EnginePortBag` in `composition_engine.ts` **and**
  `composition_engine_browser.ts` (one line each), and to the sibling conformance gate
  `tests/architecture/test_engine_port_conformance.test.ts` (P7) as the explicit row:
  `{ file: "learner_read_repo.ts", interfaceName: "LearnerReadRepo" }` (no
  `syncJustification` — all methods are `Promise`).
- **`tutorial` / `progress` reads are NOT on this port.** They are deferred to a
  second ADR-0006 amendment gated on Screens 6/7 resuming (Decision D1). Rationale in
  §2 below.

### 2. Defer `getTutorial` / `listProgressPoints` to a second amendment

The original draft bundled them onto this port to "avoid a second amendment." On
review, that bundling violated two precedents and one currency constraint:

- **Four-layer "build on the second consumer" rule** (`SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md:18`):
  "introduce protocols only when the second consumer arrives; document future
  abstractions now, build on demand." The Screens 6/7 consumer has not arrived.
- **ADR-0010's on-device-SQLite precedent:** the `EngineDb` contract admits the SQLite
  seam but ships **no surface** for it until it lands ("a new seam file + a composition
  wire, no port/repo change"). The tutorial/progress reads should follow the same
  discipline.
- **Subjective-plane currency:** Screens 6/7 depend on the coach/tutorial pipeline
  governed by ADR-0007/0008/0009, all still **Proposed**. Freezing a port shape for a
  consumer whose design isn't ratified risks a shape-change amendment later — the very
  cost the bundling was meant to avoid.

Cost of deferral: one extra ADR amendment when Screens 6/7 resume. ADRs are cheap
(this record is proof — a small, fast amendment); dead surface and premature
shape-freeze are not. The second amendment, when filed, may extend this same port
or introduce a sibling `LearnerContentReadRepo` — that call is made then, with the
Screens 6/7 view-models in hand.

### 3. Compiler-enforce the read-only invariant via a `ReadableEngineDb` projection

The original draft's "an architecture assertion **or a code-review check** keeps
`upsertSkillState` off it" was the assert-in-prose pattern that forced ADR-0010's
"Accepted with conditions" re-ratification (two mitigations asserted but not
mechanically backed). A `LearnerReadRepo` adapter holding a reference to `EngineDb`
would see `upsertSkillState` and the `insert*`/`patch*` methods — so the type
system would not enforce read-only by default. We close that gap at the compiler
level (**as shipped**, `DrizzleLearnerReadRepo` holds a `ReadableEngineDb`, never
the full `EngineDb`, so a write is not reachable):

- Add a `ReadableEngineDb` interface in `engine_db.ts` that contains **only** the read
  methods of `EngineDb` (`listSkills`, `getSkillByKey`, `listSkillIds`,
  `nextReviewedQuestion`, `getQuestion`, `getSession`, `listMisses`, `listSkillState`,
  `getSkillState`, `getContentString`, `listContentStrings`, `getTutorial`,
  `listProgressPoints`).
- `EngineDb extends ReadableEngineDb` (the live seam and `InMemoryEngineDb` satisfy
  both; nothing changes for existing repos).
- `DrizzleLearnerReadRepo` depends on **`ReadableEngineDb`**, not `EngineDb`. The
  compiler now makes it impossible for the adapter to call `upsertSkillState` or any
  `insert*`/`patch*` — no architecture test or code-review discipline required.

This is stronger than the architecture-test alternative, removes the "or" hedge, and
costs one narrowed interface. A small architecture-test sanity assertion
(`LearnerReadRepo` declares no method whose name matches `/^(upsert|insert|update|delete|patch|save)/`)
is kept as belt-and-braces — it catches a future author adding a write method to the
port interface itself, which the projection cannot prevent.

### 4. FR-G1 before/after mechanism — UI-captured session-start snapshot

FR-G1 needs the **delta** between a skill's mastery before and after a session.
`SkillState.mastery` is mutated by `Scheduler.review()` during the session, so "before"
must be captured before the first review runs. The port as specified returns only the
*current* state; the before-snapshot is a UI-layer responsibility:

- `use_quiz` (or `use_session`, whichever owns the session lifecycle) calls
  `learnerReadRepo.listSkillState(subject, learnerId)` **once at session open**, after
  `sessionRepo.open(...)` resolves, and holds the result as an immutable
  `skillStateAtStart: ReadonlyMap<skillId, SkillState>` in session state.
- At Session-Summary render, `use_summary` (or the `session_summary_vm` translator)
  computes the per-skill delta as `currentMasteryPct − startMasteryPct` using the
  snapshot + a fresh `listSkillState` read. `session_summary_vm` already accepts the
  pair; the translator maps absent-start-state → "—" (skill not seen at open, e.g. a
  brand-new learner seeded mid-session by FR-A7).

**Why UI-captured (option a) over the alternatives:**

- **(b) `SessionRepo.open()` records a snapshot column** — rejected: couples the
  session lifecycle port to the skill_state schema; `SessionRepo`'s boundary is
  "session lifecycle + scoring tally only" (ADR-0006 #4), and a snapshot column
  duplicates mutable state into a row that can drift.
- **(c) Port grows `getSessionStartSkillState(sessionId)`** — rejected for Phase 1:
  implies a persisted snapshot (same drift risk as (b)) or a temporal query against
  `skill_state` history, which the schema does not store. Adds port surface for a
  Phase-1 single-learner local-first flow that doesn't need it.

**Accepted limitation / decision trigger:** if the session is resumed mid-flight (page
reload, native shell cold-start), the in-memory `skillStateAtStart` is lost and the
delta tile renders "—" for that session. Phase 1 is single-learner, local-first, and
sessions are short; this is acceptable. **Decision trigger:** when session resume
becomes a real UX path (multi-device sync via ADR-0005's deferred sync engine, or
long-running sessions that survive reloads), revisit and likely promote to (b) or (c).
Recorded here so the implementation does not silently pick a default and leave the
choice uncaptured (intent debt).

## Options considered

1. **New `LearnerReadRepo` read port, Phase-1 surface only (chosen).** One port, one
   file, read-only, returns wire shapes. Pros: honors C2/F-R1/F-R3 + the four-layer
   "build on second consumer" rule + ADR-0010's deferral precedent; the Scheduler stays
   the sole writer; the read-only invariant is compiler-enforced (§3); the FR-G1
   before/after is specified (§4). Cons: an eighth engine port (mitigated: read-only,
   cohesive, and the conformance gate already pairs one row per port); a second
   amendment is needed when Screens 6/7 resume (accepted — ADRs are cheap).
2. **Add `listSkillState` to the `Scheduler` port.** Rejected: the Scheduler is the
   adaptivity/writer contract; bolting UI reads onto it conflates "advance the learner"
   with "show the learner their state."
3. **Add the reads to `SkillTaxonomy` (return state-enriched skills).** Rejected:
   `SkillTaxonomy` is the static catalog (labels/shares/accents); folding per-learner
   mutable state into it breaks its "taxonomy, not learner data" boundary and couples
   the grid's static and dynamic halves.
4. **Let the UI read `EngineDb` directly.** Rejected outright: violates C2/F-R1 — only
   the composition roots name adapters; components/hooks consume ports.
5. **One port bundling `skill_state` + `tutorial` + `progress` reads (the original
   draft).** Rejected on amendment: ships two methods with zero Phase-1 callers,
   freezes port shape for the still-Proposed subjective plane (ADR-0007/0008/0009),
   and is inconsistent with the four-layer "build on second consumer" rule and
   ADR-0010's on-device-SQLite deferral precedent. Defer the tutorial/progress reads
   to a second amendment gated on Screens 6/7 (Decision §2).
6. **Two ports now — `LearnerReadRepo` (skill_state) + `LearnerContentReadRepo`
   (tutorial/progress).** Rejected as redundant: the second port has no Phase-1
   consumer, so it reduces to Option 5's bundling with a different file split. Build
   the second port when Screens 6/7 resume (may still be the right shape then; decide
   with the view-models in hand).

## Rationale

A single narrow read port is the smallest change that unblocks Phase-1 FR-C3/FR-G1
while honoring every law the ADR-0006 surface already obeys (F-R3 one-interface-per-
module, C2/F-R1 UI-via-ports-only, FR-A2 single-writer `skill_state`). Splitting the
deferred reads out (§2) applies the same "build on the second consumer" discipline the
four-layer doc and ADR-0010 already apply to the on-device SQLite seam — the precedent
is on-disk, not invented here. Compiler-enforcing read-only via `ReadableEngineDb`
(§3) is a deliberate rejection of the assert-in-prose pattern that forced ADR-0010's
re-ratification: mitigations must be mechanical, not narrated. Specifying the FR-G1
before/after path (§4) closes a design gap the original draft left silent, so the
implementation doesn't make the choice by default and leave it uncaptured.

## Consequences

**Commits us to:**
- One new port `frontend/lib/ports/engine/learner_read_repo.ts` + one adapter
  `frontend/lib/adapters/engine/repos/drizzle_learner_read_repo.ts` depending on
  `ReadableEngineDb`.
- One new `ReadableEngineDb` interface in `engine_db.ts` (`EngineDb extends
  ReadableEngineDb`; no change to existing repos or to `InMemoryEngineDb` /
  `pgEngineDb`).
- Two composition-root wire lines (one each in `composition_engine.ts` +
  `composition_engine_browser.ts`) + one `REQUIRED_PORTS` row in
  `test_engine_port_conformance.test.ts` + one belt-and-braces architecture assertion
  that the port interface declares no write method.
- A UI-layer session-start snapshot in `use_quiz`/`use_session` + a `session_summary_vm`
  delta computation that consumes `(snapshot, current)` — no schema or port change for
  the delta.

**Unblocks:**
- Phase 1.2 (Dashboard mastery grid, FR-C3) and Phase 1.6 (Summary mastery-delta,
  FR-G1).

**Pre-unblocks (NOT done here):**
- The deferred Screens 6/7 (D1, FR-H/FR-I) — a second ADR-0006 amendment lands the
  tutorial/progress reads when those screens resume. This ADR does not ship that
  surface.

**Does not change:**
- The other seven ports, the `Verdict` contract, the coach stream, or the `Scheduler`
  single-writer invariant (FR-A2). `bucket_card_vm` already accepts
  `SkillState | null` and maps `null → 0%` ([bucket_card_vm.ts:31-34](../../frontend/lib/translators/bucket_card_vm.ts)),
  so the "Proposed"-window placeholder path needs no VM change; a translator test
  locking `null → 0%` should land with the port so the fallback is not silently
  regressed.

**Accepted risks / mitigations:**
- *Session-resume loses the FR-G1 before-snapshot* → delta renders "—" for that
  session; acceptable for Phase-1 single-learner local-first short sessions. Decision
  trigger: real session-resume UX (multi-device sync or long sessions surviving
  reload) → revisit, likely promote to a persisted snapshot (§4).
- *A second amendment is required for Screens 6/7* → accepted; the alternative
  (bundling) ships dead surface and freezes shape for a non-ratified plane (§2).
- *`ReadableEngineDb` widens as `EngineDb` adds read methods* → the projection is a
  superset of `LearnerReadRepo`'s needs; if `EngineDb` grows reads that shouldn't be
  on the learner port, narrow the adapter's dependency to a per-port subset interface
  instead. Decision trigger: a read method that only the engine (not the learner UI)
  should see.

**Until Accepted and implemented:** the Dashboard grid renders mastery as a
0%/"—" placeholder and the Summary omits the delta tile (or shows "—"), rather than
reaching around the port boundary.

## Supersedes / related

Amends [ADR-0006](0006-subject-coach-component-protocols.md) (the contracts) on the
substrate of [ADR-0010](0010-subject-coach-engine-ports-realization-and-ts-fsrs.md)
(the realization). Conforms to
[FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](../Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md)
(F-R3, SDK confinement, composition root) and the four-layer "build on the second
consumer" rule in
[SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md](../Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md).
