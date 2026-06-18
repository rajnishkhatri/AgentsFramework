# Option B — Cloud SQL–compatible BFF ThreadRepo (durable sidebar on `agent-frontend`)

> **Status:** PLANNED (parallel track). Created 2026-06-18 alongside Piece C option-A doc fixes.
> **Owner:** parallel work — this plan is self-contained.
> **Companion:** [`docs/deploy/DEPLOY_PIECE_C.md`](../deploy/DEPLOY_PIECE_C.md) §BFF (which, after option A, will say the BFF stays on `InMemoryThreadRepo` until *this* lands).

---

## Why this exists (the bug option A documents but does not fix)

The BFF sidebar needs `DATABASE_URL` to persist threads. The prod DB (`database-url`
secret) is a **Cloud SQL** Postgres connection over a unix socket
(`postgresql://…@/agent?host=/cloudsql/agent-prod-gcp-dev:us-central1:agent-db`).

But the *only* production `ThreadRepo` today, `NeonThreadRepo`, is wired to the
**Neon HTTP serverless driver**:

- [`neon_thread_repo.ts:27-28`](../../frontend/lib/adapters/thread_store/neon_thread_repo.ts) — `import { drizzle } from "drizzle-orm/neon-http"` + `import { neon } from "@neondatabase/serverless"`.
- [`neon_thread_repo.ts:139`](../../frontend/lib/adapters/thread_store/neon_thread_repo.ts) — `const sql = neon(databaseUrl)`.
- [`selectThreadRepo()` :232-240](../../frontend/lib/adapters/thread_store/neon_thread_repo.ts) — picks `NeonThreadRepo` whenever `DATABASE_URL` is set, else `InMemoryThreadRepo`.

**`@neondatabase/serverless` speaks Neon's HTTP/WebSocket protocol over a
`https://…neon.tech` URL. It cannot dial a Cloud SQL `/cloudsql/` unix socket.**
(Neon's own docs: using it against non-Neon Postgres requires self-hosting a
WebSocket proxy — explicitly *not recommended*; for Cloud SQL they point at
`pg`/`postgres.js`.) So binding `database-url` on `agent-frontend` today would make
`selectThreadRepo` pick `NeonThreadRepo`, which then **throws on the first thread
query** — the DSN parses, but `neon()` can't reach a unix socket.

### Research basis (2026-06, external scan)

- **Neon serverless driver** — connects to Neon over HTTP/WS; non-Neon use needs a
  self-hosted WS proxy (not recommended). Source: `github.com/neondatabase/serverless`,
  Neon docs "serverless-driver" / "choose-connection".
- **Cloud SQL → Node on Cloud Run** — two supported drivers (Google docs
  `sql/docs/postgres/connect-run`):
  1. **`pg` over the unix socket** — `host: '/cloudsql/PROJECT:REGION:INSTANCE'`,
     requires `--add-cloudsql-instances`. Password auth. **← chosen for v1.**
  2. **`@google-cloud/cloud-sql-connector`** — newer npm pkg, IAM auth, no socket
     flag. More moving parts; deferred (see "Deferred").
- **Drizzle** supports `pg` natively but via a **different import**:
  `drizzle-orm/node-postgres` (vs the current `drizzle-orm/neon-http`). So this is a
  genuine adapter swap, not a config toggle. Source: orm.drizzle.team
  "get-started-postgresql" / "connect-overview".

### Why `pg` + unix socket (not the IAM connector, not Neon)

| | `pg` over `/cloudsql/` socket (v1) | `@google-cloud/cloud-sql-connector` | provision a Neon DB (option C) |
|---|---|---|---|
| New deps | `pg` + `@types/pg` (1 runtime dep) | `@google-cloud/cloud-sql-connector` (heavier) | none |
| Auth | password (the secret we already have) | IAM (extra service-account plumbing) | Neon string |
| Reuses existing infra | ✅ same `--add-cloudsql-instances` the BFF doc already calls for | partial | ❌ resurrects abandoned Neon stack |
| # DB engines | 1 (Cloud SQL) | 1 (Cloud SQL) | **2** (Cloud SQL + Neon) |
| Drizzle import | `drizzle-orm/node-postgres` | `drizzle-orm/node-postgres` (+ connector for the pool) | unchanged |

`pg` over the socket is the smallest honest fix and reuses the exact
`--add-cloudsql-instances` step §BFF already documents. The IAM connector is a
later hardening, not a v1 requirement.

---

## Architecture constraints (test-enforced — must hold)

From [`tests/architecture/test_frontend_layering.test.ts`](../../frontend/tests/architecture/test_frontend_layering.test.ts):

1. **F-R2 SDK confinement.** Vendor SDK imports may appear ONLY in `lib/adapters/**`.
   The test maintains a `SDK_PACKAGES` allow-set (line ~39-49) that currently lists
   `drizzle-orm`, `@neondatabase/serverless`, etc. **`pg` must be added to that set**,
   or the new import is flagged. Deep subpaths are matched too
   (`drizzle-orm/node-postgres` is already covered by the `drizzle-orm` entry +
   the subpath logic at line ~154-161).
2. **C1/F1 — only the composition seam names concrete adapters.** `selectThreadRepo`
   already lives in the adapter and is called from
   [`bff/server_composition.ts:48`](../../frontend/lib/bff/server_composition.ts)
   (recognised as the "composition" ring at line ~122). Keep the new repo behind
   `selectThreadRepo`; do not name it from a route handler.
3. **A4 / F-R8 — no vendor type escapes the adapter boundary.** The new SDK seam
   returns the existing narrow `DrizzleLike` port (4 row ops); `ThreadRow` in/out
   only. Mirror `neonDrizzleDb`'s contract exactly.
4. **A5 — error translation.** Any driver rejection → `ThreadStoreError`. Reuse the
   existing `translate()` in `neon_thread_repo.ts` (the `NeonThreadRepo` class is
   driver-agnostic — it wraps a `DrizzleLike` — so it can sit on top of the new
   seam unchanged).
5. **IR-NEON-5.** The repo touches ONLY `threads` (+ reserved `thread_messages`),
   never the LangGraph checkpoint tables. The schema + `drizzle.config.ts`
   `tablesFilter` whitelist already enforce this; no change needed.

---

## Design: where `pg` plugs in

The seam split already exists and is the win — `NeonThreadRepo` is **driver-agnostic**
(it consumes a `DrizzleLike`); only `neonDrizzleDb()` touches the vendor SDK. So
option B = **add a sibling SDK seam + a selector branch**, reusing the repo class,
the row mapping shape, the error translation, and all the repo unit tests.

```
selectThreadRepo(env)
  ├─ DATABASE_URL is a /cloudsql/ socket DSN  → NeonThreadRepo( pgDrizzleDb(url) )   ← NEW
  ├─ DATABASE_URL is a neon.tech URL          → NeonThreadRepo( neonDrizzleDb(url) ) ← existing
  └─ unset                                    → InMemoryThreadRepo                   ← existing
```

**DSN discrimination** (so one secret value routes to the right driver):
- Cloud SQL socket → the DSN contains `host=/cloudsql/` (or `/cloudsql/` anywhere,
  matching `deploy_piece_c.sh`'s `case "$DATABASE_URL" in *"/cloudsql/"*`).
- Neon → host ends in `.neon.tech` (or `neon.` substring), or `sslmode=require`
  with a TCP host. Default the *ambiguous TCP* case to `pg` (the safe general
  Postgres driver) and reserve `neon-http` for explicit `.neon.tech` hosts.
- Keep this in a small pure `classifyDsn(url): "cloudsql" | "neon" | "tcp"` helper so
  it is unit-testable without a live DB.

**`pg` unix-socket config** (Google docs form): `pg` reads `host` as the socket
*directory*; pass the connection string and let `pg` parse `host=/cloudsql/…`, OR
construct a `Pool({ host: '/cloudsql/INSTANCE', user, password, database })`. The
parsed-DSN form keeps the seam signature identical to `neonDrizzleDb(url)` — prefer
it; fall back to explicit fields only if `pg` won't parse the socket host from the
URL.

---

## Files to change

**New:**
- `frontend/lib/adapters/thread_store/pg_thread_repo.ts` — `pgDrizzleDb(databaseUrl): DrizzleLike`
  using `import { drizzle } from "drizzle-orm/node-postgres"` + `import { Pool } from "pg"`.
  Body is a near-copy of `neonDrizzleDb` (same `toRow`, same 4 ops, same `threads`
  schema import). Export a `classifyDsn` helper or co-locate it.
  - Pooling note: construct a single module-scoped `Pool` (Cloud Run keeps the
    instance warm; a per-call pool leaks sockets). Mirror the existing
    "constructing the client is side-effect-free; no round-trip until a query"
    comment — with `pg` the `Pool` is lazy-connect, so this still holds.
- `frontend/lib/adapters/thread_store/pg_thread_repo.test.ts` — conformance tests
  against the `DrizzleLike` contract using a **mock `pg` Pool** (no live DB). Assert:
  insert/find/list/update round-trip the `ThreadRow` shape; list keyset pagination
  matches `neonDrizzleDb`; a driver rejection surfaces as `ThreadStoreError` (A5);
  `classifyDsn` maps `/cloudsql/` → "cloudsql", `.neon.tech` → "neon", bare TCP → "tcp".
- (optional) `frontend/lib/adapters/thread_store/select_thread_repo.test.ts` — if
  `selectThreadRepo` isn't already directly tested, add: socket DSN → pg branch,
  neon URL → neon branch, unset → in-memory. (Pure given its env arg, per the
  existing docstring — no DB needed; you can spy on the seam constructors.)

**Modified:**
- `frontend/lib/adapters/thread_store/neon_thread_repo.ts` — in `selectThreadRepo`
  (line ~232), branch on `classifyDsn(url)`:
  ```ts
  const url = env.DATABASE_URL;
  if (url && url.trim()) {
    return new NeonThreadRepo(
      classifyDsn(url) === "neon" ? neonDrizzleDb(url) : pgDrizzleDb(url),
    );
  }
  return new InMemoryThreadRepo();
  ```
  Update the function docstring (currently "durable Neon repo when DATABASE_URL is
  set") to describe the three-way choice. `NeonThreadRepo` the class is renamed in
  spirit only — it's already driver-agnostic; leaving the class name avoids churn,
  but a follow-up could rename it `DrizzleThreadRepo` (NON-goal here — see Deferred).
- `frontend/package.json` — add `"pg": "^8.x"` (runtime dep) and
  `"@types/pg": "^8.x"` (devDependency). **`pg` is a new dependency → this is an
  ask-first item; confirm before adding.**
- `frontend/tests/architecture/test_frontend_layering.test.ts` — add `"pg"` to the
  `SDK_PACKAGES` set (line ~39-49) so the new vendor import is recognised as a
  confined SDK, not an illegal leak. (`drizzle-orm/node-postgres` is already covered
  by the existing `drizzle-orm` entry + subpath matching.)
- `frontend/STYLE_GUIDE_FRONTEND.md` — add `pg` to the `THIRD_PARTY_SDK_PACKAGES`
  list §2 (the architecture test mirrors this list; keep them in sync).

**Reused unchanged (the seam-split dividend):** `NeonThreadRepo` class +
`translate()` (A5), `DrizzleLike` port, `ThreadRow`, `NeonFreeThreadStore`,
`db/schema.ts`, `drizzle.config.ts`, `0000_init_threads.sql`, all existing repo
unit tests, and `server_composition.ts` (it calls `selectThreadRepo` — the branch
is internal).

---

## Verification

1. **Unit/contract** (`pnpm test`, no live DB):
   - `pgDrizzleDb` round-trips `ThreadRow` through a mock `pg.Pool`; pagination +
     soft-delete filtering match `neonDrizzleDb`'s tested behaviour.
   - Driver rejection → `ThreadStoreError` (A5 boundary holds; no `pg` type escapes).
   - `classifyDsn` table test (cloudsql / neon / tcp).
   - `selectThreadRepo`: socket DSN → pg, neon URL → neon, unset → in-memory.
2. **Typecheck:** `pnpm tsc --noEmit` clean (the `drizzle-orm/node-postgres` types
   resolve; `@types/pg` present).
3. **Architecture gate:** `pnpm test tests/architecture/test_frontend_layering.test.ts`
   — `pg` import is allowed only from `lib/adapters/**`; nothing names the concrete
   repo outside the composition seam.
4. **Lint:** `pnpm lint` clean.
5. **Full frontend suite:** `pnpm test` — no regressions against the current baseline.
6. **Local end-to-end (optional, against the Cloud SQL Auth Proxy):**
   - `cloud-sql-proxy --unix-socket /tmp/cloudsql agent-prod-gcp-dev:us-central1:agent-db &`
   - `DATABASE_URL="postgresql://agent_runtime:…@/agent?host=/tmp/cloudsql/agent-prod-gcp-dev:us-central1:agent-db" pnpm dev`
   - create a thread, restart the dev server, confirm it persists (sidebar list).
7. **Live (after merge, when ready to flip the BFF):**
   - `gcloud run services update agent-frontend --update-secrets=DATABASE_URL=database-url:latest --add-cloudsql-instances=agent-prod-gcp-dev:us-central1:agent-db`
   - This is now safe: `selectThreadRepo` routes the socket DSN to `pgDrizzleDb`,
     not the Neon driver. Update DEPLOY_PIECE_C.md §BFF to re-enable the bind step
     (option A had removed it).

---

## Deferred (designed-for, not built here)

- **`@google-cloud/cloud-sql-connector` + IAM auth** — drop password auth, no
  `--add-cloudsql-instances`. A later hardening; v1 uses `pg` + the socket + the
  existing password secret.
- **Rename `NeonThreadRepo` → `DrizzleThreadRepo`** — accurate now that it backs two
  drivers, but pure churn; do it in a dedicated rename commit if at all.
- **Durable Terraform** — add the `agent-frontend` `DATABASE_URL` secret-env + the
  Cloud SQL volume/annotation to `infra/gcp/` (mirroring `cloud-run-backend.tf`) so
  the BFF binding survives a `tofu apply`. The §BFF doc already flags this as the
  durable form.
- **Connection-pool tuning** — `pg.Pool` max/idle sizing for Cloud Run concurrency;
  start with defaults.

---

## One-paragraph summary for the parallel worker

Add `frontend/lib/adapters/thread_store/pg_thread_repo.ts` exporting
`pgDrizzleDb(url): DrizzleLike` (a near-copy of `neonDrizzleDb` using
`drizzle-orm/node-postgres` + `pg.Pool`) and a pure `classifyDsn(url)` helper;
branch `selectThreadRepo` (in `neon_thread_repo.ts:232`) so a `/cloudsql/` socket
DSN routes to `pgDrizzleDb` while `.neon.tech` URLs keep `neonDrizzleDb`. Add `pg`
+ `@types/pg` to `package.json` (ask-first dep), add `"pg"` to the `SDK_PACKAGES`
allow-set in `test_frontend_layering.test.ts` and the STYLE_GUIDE list. The
`NeonThreadRepo` class, error translation, schema, migration, and all repo tests are
reused unchanged — the existing `DrizzleLike` seam split means only the SDK-touching
factory is new. Gate with the four-pillar frontend checks (vitest + tsc + arch +
lint). When green, re-enable the §BFF bind step that option A removed.
