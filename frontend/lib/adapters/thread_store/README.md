# `adapters/thread_store/` — ThreadStore family

Per Rule **A10**, every adapter family carries a one-page README declaring
the port it satisfies, current implementations, and the substrate-swap
trigger.

## Port

[`ThreadStore`](../../ports/thread_store.ts) — vendor-neutral CRUD over
chat threads. All methods take an [`IdentityClaim`](../../trust-view/identity.ts)
as the first parameter for ownership scoping at the port level (defense
in depth: even if a route handler forgets to authenticate, the store
will still filter to the caller's `sub`).

## Current implementations

| Profile | Adapter | SDK pin |
|---------|---------|---------|
| **V3-Dev-Tier** (default) | [`NeonFreeThreadStore`](./neon_free_thread_store.ts) | `drizzle-orm ^0.x` + `@neondatabase/serverless ^0.x` (production wiring; tests use `InMemoryThreadRepo`) |
| V2-Frontier (graduation) | `CloudSQLThreadStore` (not yet implemented) | same Drizzle pin, different connection string |

The store depends only on the narrow `ThreadRepo` interface defined in
the same file. The composition root constructs a `NeonThreadRepo`
(production) or an `InMemoryThreadRepo` (tests) and injects it as the
`repo` dependency. Drizzle / Neon types never appear in the adapter's
public surface (Rule **A4 / F-R8**).

## Drizzle config note

`tablesFilter` MUST exclude LangGraph checkpoint tables — the
`THREAD_TABLE_NAME` constant is the inclusion list. LangGraph manages
its own checkpoints in the same Postgres instance; the app schema and
the checkpoint schema must not collide.

## Soft-delete policy

`archive()` flips the `archived_at` column; `list()` and `get()` filter
on `archived_at IS NULL`. Hard-delete is intentionally not exposed.

## Existence-oracle prevention (FD3.SEC)

`get()` returns `null` for both "not found" and "not the owner" so the
URL space cannot be used to discover other users' thread IDs.

## Logger

`frontend:adapter:thread_store` (Rule **A7 / O3**). Emitted lines:

| Event | Meta | When |
|-------|------|------|
| `rename rejected` | `thread_id`, `error_type=not_found_or_not_owner` | rename target absent or owned by someone else |
| `archive idempotent no-op` | `thread_id` | archive target absent or owned by someone else (silent success per A6) |

No PII (Rule **O2**). Title text and message bodies are never logged.

## Error translation table (Rule A5)

| repo condition | Adapter behavior |
|----------------|------------------|
| `findOne` returns `null` OR ownership mismatch on `get` | returns `null` (no existence oracle) |
| `findOne` returns `null` OR ownership mismatch on `rename` | throws `ThreadStoreError` |
| `update` returns `null` after successful `findOne` | throws `ThreadStoreError` (race / concurrent delete) |
| `archive` on missing-or-non-owner | resolves silently (idempotent, A6) |
| Any underlying repo rejection | propagated; production `NeonThreadRepo` is responsible for translating Drizzle/Neon errors to `ThreadStoreError` so vendor types never reach this layer |

## Substrate swap trigger

| When | Swap to | How |
|------|---------|-----|
| Neon Free DB > 0.5 GB or CU-hr exhausted | `CloudSQLThreadStore` (V2) | new adapter file + composition selector update; no `ports/`, `wire/`, `trust-view/` files change (**F3**) |

## Tests

- [`neon_free_thread_store.test.ts`](./neon_free_thread_store.test.ts) —
  failure-paths-first (unknown id, non-owner, missing-on-rename) per
  Rule **FD6.ADAPTER**, then ownership isolation, pagination, and CRUD
  happy paths.
