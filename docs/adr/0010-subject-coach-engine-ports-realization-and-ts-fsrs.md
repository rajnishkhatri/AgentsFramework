---
type: decision-record
title: 'ADR-0010: Subject-Coach engine ports realization — ports/engine/ home, ts-fsrs dependency, EngineDb seam'
status: accepted
created: 2026-06-30
updated: 2026-07-01
owner: Rajnish Khatri
related: 0006-subject-coach-component-protocols.md, 0005-subject-coach-engine-home-and-substrate.md, preact-english-coach-engine.spec.md, FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md
tags: [decision-record]
---

# ADR-0010: Subject-Coach engine ports realization

**Status:** Accepted — 2026-06-30, **with conditions** (added 2026-07-01).
**Related:** [ADR-0006 protocols](0006-subject-coach-component-protocols.md) · [ADR-0005 engine home](0005-subject-coach-engine-home-and-substrate.md) · [engine spec](../plan/preact-english-coach-engine.spec.md) · [Frontend ports deep dive](../Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md)
**Audience:** anyone changing an engine port location, the FSRS library, or the engine persistence seam.

> **Acceptance conditions (2026-07-01) — ⏳ PENDING.** A post-acceptance review found two
> of this ADR's stated mitigations are asserted in prose but not yet backed by anything
> mechanical. The decision itself stays **Accepted** and the code as shipped (Postgres +
> `InMemoryEngineDb`, 129/129 architecture tests green) is unaffected — but the following
> MUST land **before the on-device SQLite seam (ADR-0005's local-first path) is built**:
> 1. **The FR-G3 dual-dialect parity test does not exist.** `schema.pg.ts`, `schema.sqlite.ts`,
>    and `adapters/engine/db/README.md` all reference "a parity test guards against drift,"
>    and the engine spec's §8 test plan names `schema.spec::same_drizzle_schema_compiles_pg_and_sqlite`
>    as a `make check` gate — but no such test file exists in `frontend/`. This is the one
>    hard constraint the whole dual-dialect substrate choice (ADR-0005) depends on; it is
>    currently unenforced.
> 2. **The "engine spec §8.2" follow-up cited below does not exist.** The engine spec's Test
>    Plan (§8) has no §8.2 — the `DATABASE_URL`-gated `pgEngineDb` integration test mitigation
>    is a citation to nothing. Add a real, numbered follow-up item to
>    `preact-english-coach-engine.spec.md` §8 (or an explicit tracked TODO/issue) before
>    relying on that mitigation.
>
> Until both land, treat the dual-dialect substrate as **unverified**, not merely
> "not yet exercised in CI." The condition gates the *next* increment, not what is already
> merged.

---

## Context

[ADR-0006](0006-subject-coach-component-protocols.md) ratified the *contracts* (seven
ports + `Verdict` + renderer registry). Realizing them surfaced three concrete choices
that ADR-0006 deliberately left open and that the engine spec
([`preact-english-coach-engine.spec.md`](../plan/preact-english-coach-engine.spec.md))
does not pin:

1. **Where the seven engine port *interfaces* physically live.** The existing port
   conformance gate (`frontend/tests/architecture/test_port_conformance.test.ts`)
   **hard-asserts** that the flat `lib/ports/` directory contains *exactly* the eight
   V3 chat ports (`expect(new Set(files)).toEqual(required)`). Adding seven engine
   interfaces flat would break that gate, and it would also mix two bounded contexts
   (chat substrate vs learner engine) in one directory.

2. **The FSRS implementation.** ADR-0006's `Scheduler` is vendor-neutral, but a real
   FSRS algorithm is non-trivial (stability/difficulty/retrievability math). The
   design doc names a "ts-fsrs adapter" — but `ts-fsrs` is **not** a current
   dependency, and adding a `package.json` dependency is an `⚠️ Ask first` /
   ADR-triggering change (root `AGENTS.md`).

3. **The engine persistence seam.** The repos must reach Postgres (canonical) and
   eventually on-device SQLite (ADR-0005), without the Drizzle SDK leaking past the
   adapter boundary (F-R2 / Rule A4).

---

## Decision

1. **Home the seven engine ports under `frontend/lib/ports/engine/`** (one interface
   per file), grouped as a sibling bounded context to the eight flat chat ports. A
   dedicated `test_engine_port_conformance.test.ts` is the P7 gate for them; the chat
   gate stays untouched. A `ports/engine/errors.ts` holds the shared typed errors
   (P4) and is recognized as a ports-local helper by both gates.

2. **Adopt `ts-fsrs` (^5.4.1)** as the FSRS engine, **confined to**
   `lib/adapters/engine/scheduler/fsrs_scheduler.ts` (the sole importer; added to the
   layering test's `SDK_PACKAGES`). The `Scheduler` port stays vendor-neutral — the
   FSRS `Card` type never escapes; `review()` returns a `wire/engine_entities`
   `SkillState`, the durable vendor-neutral projection of a card.

3. **Introduce a narrow `EngineDb` row-level port** (the engine analogue of
   `thread_store`'s `DrizzleLike`). The six DB-backed repos depend only on it; two
   implementations satisfy it — `InMemoryEngineDb` (fake; L1/dev/CI) and
   `pgEngineDb` (the one live Drizzle+pg SDK seam). A separate engine composition
   root `lib/composition_engine.ts` selects the seam by `DATABASE_URL` (mirroring
   `selectThreadRepo`), independent of the chat `ARCHITECTURE_PROFILE`.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **Engine ports flat in `lib/ports/` + widen the chat gate to 15** | Edits a shared architecture test, mixes two bounded contexts in one flat dir, and couples the engine's evolution to the chat conformance list. The subdir keeps the contexts separate and each gate single-purpose. ❌ |
| **Hand-rolled FSRS-style update (no new dependency)** | Avoids the `Ask first` trigger, but re-implements a well-specified, actively-maintained algorithm (FSRS-6) — exactly the "build it yourself" trap. The design doc already names ts-fsrs; the port keeps it swappable. The dependency is deterministic and CI-safe. ❌ |
| **Repos talk to the Drizzle client directly** | The Drizzle query builder would leak into repo logic + tests (violates A4/F-R8 and makes repos un-unit-testable without a DB). The `EngineDb` shim is the proven `thread_store` pattern. ❌ |
| **Reuse the chat `composition.ts` for the engine bag** | Would entangle the engine seam selection with the chat `ARCHITECTURE_PROFILE` switch and force the engine to graduate on the chat substrate's schedule. A separate root matches how `composition_browser.ts` / `composition_ios.ts` already split roots by bounded context. ❌ |

---

## Rationale

The subdir + sibling-gate choice *applies* the existing one-interface-per-module rule
(F-R3) without weakening the chat gate — each gate stays single-purpose, and the two
bounded contexts evolve independently. Confining `ts-fsrs` to one adapter file is the
same SDK-confinement law that confines `drizzle`/`pg`; the vendor-neutral `Scheduler`
port means a future swap to another spaced-repetition library is a one-file change
(Rule F3). The `EngineDb` shim makes all six repos + the Scheduler fully L1-testable
against an in-memory fake (failure-paths-first, the reviewed gate, typed-error
translation, idempotent close, FSRS seeding) — proving they depend only on the narrow
contract the live seam must reproduce.

---

## Consequences

**Commits us to:**
- `ts-fsrs ^5.4.1` in `frontend/package.json` (deterministic — `enable_fuzz: false` on
  the verifier path; CI-safe, no live LLM/network).
- Seven `lib/ports/engine/*.ts` interfaces + `errors.ts`, their conformance gate, the
  `EngineDb` shim + two implementations, six repo adapters, the `ExactLetterGrader`,
  the `FsrsScheduler`, and `lib/composition_engine.ts`. All wired; 0 tsc errors of
  ours; engine adapter + composition tests green; the full frontend architecture
  suite green (no existing gate regressed).
- Two small, intended extension-point edits to `test_frontend_layering.test.ts`:
  `ts-fsrs` added to `SDK_PACKAGES`; `composition_engine.ts` + `ports/engine/errors.ts`
  recognized (composition root / ports-local helper).

**Accepted risks / mitigations:**
- *The live `pgEngineDb` seam is not exercised in CI* (no DB on the deterministic gate)
  → its behavior is `tsc`-checked against the real schemas and mirrors the
  `InMemoryEngineDb` the repos are tested against; a `DATABASE_URL`-gated integration
  test was intended as a documented follow-up, but the "engine spec §8.2" citation this
  mitigation originally pointed to **does not exist** (the spec's §8 test plan has no
  §8.2) — **acceptance condition #2 above** tracks fixing this.
- *Dual-dialect schema drift* (`schema.pg.ts` vs. `schema.sqlite.ts`) → the design intends
  a `tsc --noEmit` + parity test (FR-G3) to guard column-for-column identity, but **no such
  test is implemented yet** — **acceptance condition #1 above** blocks the on-device SQLite
  adapter on this landing first.
- *FSRS→mastery projection* (retrievability→0..1) is a modeling choice → isolated in
  one private method; revisable without touching the port or `skill_state` columns.
- *FSRS card persistence.* The scheduler round-trips the **full** FSRS card via an
  opaque `skill_state.fsrs_card` JSON column (the named `mastery`/`fsrs_stability`/
  `fsrs_difficulty`/`due_at`/`last_seen` columns stay the vendor-neutral projection).
  Restoring only stability/difficulty/due is insufficient — the card's state machine
  (`state`/`reps`/`lapses`/`learning_steps`) must survive across reviews or `fsrs.next`
  treats every review as a first review and intervals never grow. `fsrs_card` is typed
  `unknown` on the wire so no FSRS type leaks the adapter (only the scheduler parses it).
  Guarded by a multi-review progression L1 test.
- *On-device SQLite seam not built yet* → the `EngineDb` contract already admits it; it
  is a new seam file + a composition wire, no port/repo change (ADR-0005's deferral).

---

## Supersedes / related

Realizes [ADR-0006](0006-subject-coach-component-protocols.md) (the contracts) on the
substrate of [ADR-0005](0005-subject-coach-engine-home-and-substrate.md). Conforms to
[FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](../Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md)
(F-R3, SDK confinement, composition root) and the dual-dialect DB rule in
[`frontend/lib/adapters/engine/db/README.md`](../../frontend/lib/adapters/engine/db/README.md).
