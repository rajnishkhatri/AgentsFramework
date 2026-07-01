# Subject-Coach engine — DB schema (`adapters/engine/db/`)

The Drizzle schema for the eight engine entities, authored once per dialect.
This is the concrete DDL that resolves the abstract types in design-doc §2.1.

| File | Dialect | Role |
|------|---------|------|
| [`schema.pg.ts`](schema.pg.ts) | Postgres/Neon | **Canonical / online** store |
| [`schema.sqlite.ts`](schema.sqlite.ts) | SQLite | **On-device** twin (Capacitor, offline) |

**Why two files (ADR-0005):** the learner-facing engine runs local-first
on-device, but Postgres/Neon is the canonical store. One schema, two dialect
targets, **no sync engine yet** — the local store is the working store for the
single learner; a Postgres↔SQLite sync adapter is a later, decision-triggered
addition (first second-device / backup need), not built now.

## The dual-dialect rule (the one hard constraint)

The two files MUST stay **column-for-column identical** in name, nullability,
and default *intent*. Only the dialect-specific column **types** differ. No
Postgres-only column type may appear on a shared table.

| Concept | `schema.pg.ts` | `schema.sqlite.ts` |
|---|---|---|
| id | `uuid(...).defaultRandom()` | `text(...)` (app-supplied uuid) |
| json | `jsonb(col)` | `text(col, { mode: "json" })` |
| boolean | `boolean(col)` | `integer(col, { mode: "boolean" })` |
| timestamp | `timestamp(col, { withTimezone: true })` | `integer(col, { mode: "timestamp" })` |
| number / string | `real` / `integer` / `text` | unchanged |

Engine spec **FR-G3** compiles both with `tsc --noEmit`; a parity test guards
against drift (a column added to one file but not the other).

## IR-NEON-5 analogue

The engine tables are added to the drizzle `tablesFilter` whitelist
(`ENGINE_TABLE_NAMES`, exported from `schema.pg.ts`). The LangGraph checkpoint
tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`,
`checkpoint_migrations`) are owned by the Python `AsyncPostgresSaver` and stay
ABSENT from this schema so drizzle-kit never regenerates them — exactly the
guard `adapters/thread_store/db/schema.ts` already follows.

## The `subject` discriminator (OCP seam)

Every table carries `subject` (default `'act-english'`). That single column is
what keeps the schema open for Math/Science without making it abstract (engine
spec FR-H1). A new subject is **new rows + a new `Grader` adapter + a new
renderer-registry entry** — this schema does not change.

## Related

- WHAT: [`SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md`](../../../../../docs/Architectures/SUBJECT_COACH_ENGINE_DATA_AND_PROTOCOLS.md) §2 (entity model + view-model mapping)
- WHY: [ADR-0005](../../../../../docs/adr/0005-subject-coach-engine-home-and-substrate.md) (home + substrate), [ADR-0006](../../../../../docs/adr/0006-subject-coach-component-protocols.md) (protocols)
- FRs: [`preact-english-coach-engine.spec.md`](../../../../../docs/plan/preact-english-coach-engine.spec.md)
- Pattern mirrored: [`adapters/thread_store/db/schema.ts`](../../thread_store/db/schema.ts) (Drizzle + IR-NEON-5)
