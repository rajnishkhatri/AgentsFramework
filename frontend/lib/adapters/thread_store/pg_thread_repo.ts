/**
 * pg_thread_repo — Cloud SQL–compatible SDK seam for the thread store (option B).
 *
 * The prod `database-url` secret is a Cloud SQL Postgres connection over a unix
 * socket (`postgresql://…@/agent?host=/cloudsql/PROJECT:REGION:INSTANCE`). The
 * Neon HTTP driver in `neon_thread_repo.ts` cannot dial that socket, so this
 * module provides a sibling SDK seam built on `pg` + `drizzle-orm/node-postgres`.
 *
 * Seam split (the dividend that makes this small): `NeonThreadRepo` is already
 * driver-agnostic — it consumes the narrow `DrizzleLike` port (4 row ops) and
 * owns the pagination math + the A5 error-translation contract. So option B is
 * ONLY a new `DrizzleLike` factory (`pgDrizzleDb`) plus a DSN classifier; the
 * repo class, schema, migration, and the repo's own unit tests are reused
 * unchanged. Per A4 / F-R8 no `pg` / Drizzle vendor type escapes this module —
 * the public surface is `ThreadRow` in / out.
 *
 * IR-NEON-5: this seam touches ONLY the `threads` table; it never reads or
 * writes LangGraph checkpoint tables.
 *
 * SDK pin (A9): pg ^8, drizzle-orm ^0.45 (package.json). `pg` is confined to
 * `lib/adapters/thread_store/` (STYLE_GUIDE_FRONTEND.md §2; SDK_PACKAGES set in
 * tests/architecture/test_frontend_layering.test.ts).
 */

import { and, desc, eq, isNull, lt } from "drizzle-orm";
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { pgPoolMax, toNodePgConnectionString } from "@/lib/adapters/db/node_pg_url";
import { ThreadStoreError } from "./neon_free_thread_store";
import type { DrizzleLike } from "./neon_thread_repo";
import { threads } from "./db/schema";

interface ThreadRow {
  thread_id: string;
  user_id: string;
  title: string;
  messages: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

/**
 * Which driver a connection string wants. PURE (no I/O) so it is unit-testable
 * without a live DB.
 *
 *   "cloudsql" — DSN contains the `/cloudsql/` socket marker. Matched as a plain
 *                substring to agree with `deploy_piece_c.sh`'s
 *                `case "$DATABASE_URL" in *"/cloudsql/"*`. Highest precedence:
 *                a socket DSN is a socket DSN regardless of other params.
 *   "neon"     — host ends in `.neon.tech` (the Neon serverless HTTP/WS driver).
 *   "tcp"      — any other (generic) Postgres TCP DSN.
 *
 * Routing (see `selectThreadRepo`): "neon" → the Neon HTTP seam; "cloudsql" and
 * "tcp" → this `pg` seam (pg is the correct driver for both a unix socket and a
 * generic TCP host).
 */
export function classifyDsn(url: string): "cloudsql" | "neon" | "tcp" {
  if (url.includes("/cloudsql/")) return "cloudsql";
  if (/\.neon\.tech(?:[:/?]|$)/.test(url)) return "neon";
  return "tcp";
}

// One Pool per distinct connection string, reused across calls. Cloud Run keeps
// the instance warm; a fresh Pool per request would leak sockets. The Pool is
// lazy-connect (no round-trip until a query), so constructing it here is
// side-effect-free — same contract as `neon()` in the Neon seam.
const _pools = new Map<string, Pool>();

function poolFor(databaseUrl: string): Pool {
  let pool = _pools.get(databaseUrl);
  if (!pool) {
    pool = new Pool({
      connectionString: toNodePgConnectionString(databaseUrl),
      // T R.13 — bounded pool (shared Cloud SQL budget). Default 5.
      max: pgPoolMax(process.env, 5),
    });
    _pools.set(databaseUrl, pool);
  }
  return pool;
}

/**
 * The slice of a `pg` client/Pool that drizzle's node-postgres driver actually
 * calls — a single `query(text, params) => { rows }` method. Declared here so
 * tests can inject a scripted fake at the `pg` boundary (Mock Provider pattern)
 * without depending on the full `pg.Pool` type. `pg.Pool` satisfies this.
 */
export interface PgQueryClient {
  query(queryTextOrConfig: unknown, values?: unknown): Promise<{ rows: unknown[] }>;
}

/**
 * SDK seam — the ONLY code that imports the `pg` / `drizzle-orm/node-postgres`
 * vendor packages. Constructs a `DrizzleLike` backed by a `pg.Pool` over a Cloud
 * SQL unix socket (or any TCP Postgres). Called by the server composition root
 * (`selectThreadRepo`) when `DATABASE_URL` is a `/cloudsql/` or generic-TCP DSN.
 *
 * `client` is an optional pre-built `pg` client for test injection (mirrors the
 * `sdk_client` injection seam on `LangfuseCloudExporter`); production passes
 * none and a pooled `pg.Pool` is used. `created_at` / `updated_at` /
 * `archived_at` are read back as ISO strings so the rest of the stack stays
 * vendor-free (the column type is `timestamptz`).
 */
export function pgDrizzleDb(
  databaseUrl: string,
  client?: PgQueryClient,
): DrizzleLike {
  if (!databaseUrl && !client) {
    throw new ThreadStoreError("pgDrizzleDb requires a non-empty DATABASE_URL");
  }
  const db = drizzle({ client: (client ?? poolFor(databaseUrl)) as never });

  const toRow = (r: Record<string, unknown>): ThreadRow => ({
    thread_id: String(r.thread_id),
    user_id: String(r.user_id),
    title: String(r.title ?? "New chat"),
    messages: (r.messages as Array<Record<string, unknown>>) ?? [],
    metadata: (r.metadata as Record<string, unknown>) ?? {},
    created_at: isoOf(r.created_at),
    updated_at: isoOf(r.updated_at),
    archived_at: r.archived_at == null ? null : isoOf(r.archived_at),
  });

  return {
    async insertThread(row: ThreadRow): Promise<void> {
      await db.insert(threads).values({
        thread_id: row.thread_id,
        user_id: row.user_id,
        title: row.title,
        messages: row.messages,
        metadata: row.metadata,
        created_at: new Date(row.created_at),
        updated_at: new Date(row.updated_at),
        archived_at: row.archived_at ? new Date(row.archived_at) : null,
      });
    },
    async findThread(threadId: string): Promise<ThreadRow | null> {
      const out = await db
        .select()
        .from(threads)
        .where(eq(threads.thread_id, threadId))
        .limit(1);
      const first = out[0];
      return first ? toRow(first as Record<string, unknown>) : null;
    },
    async listThreads(opts): Promise<ThreadRow[]> {
      // Keyset pagination on (created_at DESC) using the cursor row's id.
      const conds = [eq(threads.user_id, opts.ownerSub), isNull(threads.archived_at)];
      if (opts.cursor) {
        const cursorRow = await db
          .select({ created_at: threads.created_at })
          .from(threads)
          .where(eq(threads.thread_id, opts.cursor))
          .limit(1);
        const c = cursorRow[0];
        if (c) {
          conds.push(lt(threads.created_at, c.created_at));
        }
      }
      const out = await db
        .select()
        .from(threads)
        .where(and(...conds))
        .orderBy(desc(threads.created_at))
        .limit(opts.limit);
      return out.map((r) => toRow(r as Record<string, unknown>));
    },
    async updateThread(
      threadId: string,
      patch: Partial<ThreadRow>,
    ): Promise<ThreadRow | null> {
      const values: Record<string, unknown> = { updated_at: new Date() };
      if (patch.title !== undefined) values.title = patch.title;
      if (patch.messages !== undefined) values.messages = patch.messages;
      if (patch.metadata !== undefined) values.metadata = patch.metadata;
      if (patch.archived_at !== undefined) {
        values.archived_at = patch.archived_at ? new Date(patch.archived_at) : null;
      }
      const out = await db
        .update(threads)
        .set(values)
        .where(eq(threads.thread_id, threadId))
        .returning();
      const first = out[0];
      return first ? toRow(first as Record<string, unknown>) : null;
    },
  };
}

function isoOf(value: unknown): string {
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  return new Date().toISOString();
}
