# Subject-Coach engine adapters (`adapters/engine/`)

The concrete implementations of the eight engine ports (7 ADR-0006 +
`LearnerReadRepo`, ADR-0011) ([`lib/ports/engine/`](../../ports/engine/)). Per
Rule A10 this README lists the ports the family implements, the current
implementations, and the swap triggers.

## Ports → adapters

| Port (`ports/engine/`) | Adapter | Vendor / SDK | Notes |
|---|---|---|---|
| `SkillTaxonomy` | [`repos/drizzle_skill_taxonomy.ts`](repos/drizzle_skill_taxonomy.ts) | (via `EngineDb`) | read-only; no mastery |
| `QuestionRepo` | [`repos/drizzle_question_repo.ts`](repos/drizzle_question_repo.ts) | (via `EngineDb`) | **the reviewed gate** lives here |
| `AttemptRepo` | [`repos/drizzle_attempt_repo.ts`](repos/drizzle_attempt_repo.ts) | (via `EngineDb`) | append-only; owns id+clock |
| `SessionRepo` | [`repos/drizzle_session_repo.ts`](repos/drizzle_session_repo.ts) | (via `EngineDb`) | lifecycle + scoring tally |
| `Scheduler` | [`scheduler/fsrs_scheduler.ts`](scheduler/fsrs_scheduler.ts) | **`ts-fsrs`** | sole `skill_state` writer; seeding |
| `Grader` | [`grader/exact_letter_grader.ts`](grader/exact_letter_grader.ts) | none (pure) | exact-letter-match; verifier-first |
| `ContentRepo` | [`repos/drizzle_content_repo.ts`](repos/drizzle_content_repo.ts) | (via `EngineDb`) | objective-plane UI strings |
| `LearnerReadRepo` | [`repos/drizzle_learner_read_repo.ts`](repos/drizzle_learner_read_repo.ts) | (via `ReadableEngineDb`) | **read-only** `skill_state` (ADR-0011); Scheduler stays sole writer |

The DB-backed ports are written against the narrow **`EngineDb`** row-level
port ([`db/engine_db.ts`](db/engine_db.ts)) — the engine analogue of
`thread_store`'s `DrizzleLike`. Two `EngineDb` implementations satisfy it:

| `EngineDb` impl | File | Role |
|---|---|---|
| `InMemoryEngineDb` | [`db/in_memory_engine_db.ts`](db/in_memory_engine_db.ts) | behavioral fake — L1 tests, dev, the on-device-before-DB path |
| `pgEngineDb` / `pgEngineDbFrom` | [`db/drizzle_engine_db.ts`](db/drizzle_engine_db.ts) | **the only SDK seam** (drizzle-orm + pg); maps rows → wire shapes |

## SDK confinement (F-R2 / Rule A1)

The vendor SDKs appear in exactly two files, both under `adapters/engine/`:

- `drizzle-orm` + `pg` → [`db/drizzle_engine_db.ts`](db/drizzle_engine_db.ts)
- `ts-fsrs` → [`scheduler/fsrs_scheduler.ts`](scheduler/fsrs_scheduler.ts)

No vendor type escapes: every port method returns a
[`wire/engine_entities`](../../wire/engine_entities.ts) shape. The Grader has no
vendor dependency at all — it lives here because it is a concrete port
implementation, not because it wraps an SDK.

## Composition

Wired by the engine composition root
[`lib/composition_engine.ts`](../../composition_engine.ts) — the only file that
names these classes (Rule C2). It selects the `EngineDb` seam by `DATABASE_URL`
(absent → in-memory; set → `pgEngineDb`), mirroring `selectThreadRepo`.

## Schema + dual dialect (ADR-0005)

The Drizzle schemas the seam queries live in [`db/`](db/) — see
[`db/README.md`](db/README.md) for the dual-dialect (Postgres canonical / SQLite
on-device twin) rule and the IR-NEON-5 `tablesFilter` whitelist.

## Verification posture

- **Grader, repos, Scheduler** are fully L1-tested against `InMemoryEngineDb`
  (`*.test.ts` co-located). Failure paths first (TAP-4): the reviewed gate, typed
  error translation, and not-found are tested before the happy paths.
- **The live `pgEngineDb` seam** is `tsc`-checked against the real schemas but is
  **not** exercised in CI (no database on the deterministic gate). It must
  reproduce the `InMemoryEngineDb` behavior the repos are tested against; a live
  `DATABASE_URL`-gated integration test is the documented follow-up (engine spec
  §8.2 coverage gap) — never on the CI hot path.

## Swap triggers

| Change | Touches |
|---|---|
| New subject (Math/Science) | a **new** `Grader` adapter + a **new** renderer-registry entry + new rows — **zero edits here** (FR-H1, OCP) |
| On-device SQLite store | add the SQLite `EngineDb` seam (same contract) in `db/`, wire in `composition_engine.ts` |
| Different FSRS / SR library | replace `scheduler/fsrs_scheduler.ts` only (the `Scheduler` port is vendor-neutral) |

## Related

- Ports: [`lib/ports/engine/`](../../ports/engine/) · ADR: [ADR-0006](../../../../docs/adr/0006-subject-coach-component-protocols.md)
- Engine spec: [`preact-english-coach-engine.spec.md`](../../../../docs/plan/preact-english-coach-engine.spec.md)
- Pattern mirrored: [`adapters/thread_store/`](../thread_store/) (narrow DrizzleLike + SDK seam + in-memory fake)
