/**
 * NeonThreadRepo — Drizzle/Neon-backed `ThreadRepo` (live-infra Piece C).
 *
 * `NeonFreeThreadStore` depends only on the narrow `ThreadRepo` interface; this
 * is the production implementation of that interface, backed by Postgres via
 * `drizzle-orm` + `@neondatabase/serverless`. Per A4 / F-R8 NO Drizzle or Neon
 * vendor type escapes this module — the repo's public surface is `ThreadRow`
 * in / out, and the only place that touches the SDK is `neonDrizzleDb()` below.
 *
 * Two layers, on purpose:
 *   - `NeonThreadRepo` implements `ThreadRepo` over a narrow `DrizzleLike`
 *     port (4 row-level ops). It owns the error-translation contract
 *     (any rejection → `ThreadStoreError`, A5) and the list pagination math.
 *     It is fully unit-testable with an in-memory `DrizzleLike` fake.
 *   - `neonDrizzleDb(databaseUrl)` is the thin SDK seam: it constructs the
 *     drizzle client over the Neon HTTP driver and adapts it to `DrizzleLike`.
 *     This is the only code that imports the vendor packages.
 *
 * IR-NEON-5: this repo touches ONLY the `threads` table (defined in
 * `lib/adapters/thread_store/db/schema.ts`); it never reads or writes LangGraph
 * checkpoint tables.
 *
 * SDK pin (A9): drizzle-orm ^0.45, @neondatabase/serverless ^1.1 (package.json).
 */

import { and, desc, eq, isNull, lt } from "drizzle-orm";
import { drizzle } from "drizzle-orm/neon-http";
import { neon } from "@neondatabase/serverless";
import {
  InMemoryThreadRepo,
  ThreadStoreError,
  type ThreadRepo,
} from "./neon_free_thread_store";
import { classifyDsn, pgDrizzleDb } from "./pg_thread_repo";
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
 * Narrow row-level port over the Drizzle client. The repo is written against
 * this so the vendor query-builder never leaks into tests or the repo's logic.
 */
export interface DrizzleLike {
  insertThread(row: ThreadRow): Promise<void>;
  findThread(threadId: string): Promise<ThreadRow | null>;
  listThreads(opts: {
    ownerSub: string;
    cursor: string | null;
    limit: number;
  }): Promise<ThreadRow[]>;
  updateThread(
    threadId: string,
    patch: Partial<ThreadRow>,
  ): Promise<ThreadRow | null>;
}

export class NeonThreadRepo implements ThreadRepo {
  private readonly db: DrizzleLike;
  constructor(db: DrizzleLike) {
    this.db = db;
  }

  async insert(thread: ThreadRow): Promise<void> {
    try {
      await this.db.insertThread(thread);
    } catch (err) {
      throw translate("insert", err);
    }
  }

  async findOne(threadId: string): Promise<ThreadRow | null> {
    try {
      return await this.db.findThread(threadId);
    } catch (err) {
      throw translate("findOne", err);
    }
  }

  async list(opts: {
    ownerSub: string;
    cursor: string | null;
    limit: number;
  }): Promise<{ rows: ThreadRow[]; nextCursor: string | null }> {
    let fetched: ThreadRow[];
    try {
      // Fetch one extra row to decide whether a next page exists without a
      // second count query.
      fetched = await this.db.listThreads({ ...opts, limit: opts.limit + 1 });
    } catch (err) {
      throw translate("list", err);
    }
    const hasMore = fetched.length > opts.limit;
    const rows = hasMore ? fetched.slice(0, opts.limit) : fetched;
    const nextCursor = hasMore ? rows[rows.length - 1]!.thread_id : null;
    return { rows, nextCursor };
  }

  async update(
    threadId: string,
    patch: Partial<ThreadRow>,
  ): Promise<ThreadRow | null> {
    try {
      return await this.db.updateThread(threadId, patch);
    } catch (err) {
      throw translate("update", err);
    }
  }
}

function translate(op: string, err: unknown): ThreadStoreError {
  // A5: never let a Drizzle/Neon vendor error escape the adapter boundary.
  if (err instanceof ThreadStoreError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new ThreadStoreError(`thread repo ${op} failed: ${detail}`);
}

/**
 * SDK seam — the ONLY code that imports the Neon/Drizzle vendor packages.
 * Constructs a `DrizzleLike` backed by the Neon HTTP serverless driver. Called
 * by the server composition root when `DATABASE_URL` is set.
 *
 * `created_at` / `updated_at` / `archived_at` are read back as ISO strings so
 * the rest of the stack stays vendor-free (the column type is `timestamptz`).
 */
export function neonDrizzleDb(databaseUrl: string): DrizzleLike {
  if (!databaseUrl) {
    throw new ThreadStoreError("neonDrizzleDb requires a non-empty DATABASE_URL");
  }
  // `neon()` only parses the connection string; no network round-trip happens
  // until a query runs, so constructing the client here is side-effect-free.
  const sql = neon(databaseUrl);
  const db = drizzle(sql);

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

/**
 * Composition-root selector: a durable, driver-correct repo when `DATABASE_URL`
 * is set, else the ephemeral in-memory repo (dev / tests / CI). Pure given its
 * env argument so the choice is unit-testable without `server-only`. Both SDK
 * seams construct lazily — the vendor packages only open a connection when a
 * query runs, so this stays side-effect-free at selection time.
 *
 * The DSN decides the driver (`classifyDsn`), because one `DATABASE_URL` secret
 * must route to the driver that can actually reach that database:
 *   - `/cloudsql/` socket (prod Cloud SQL) → `pgDrizzleDb` (`pg` over the unix
 *     socket). The Neon HTTP driver CANNOT dial a `/cloudsql/` socket, so this
 *     branch is what makes binding the prod `database-url` on the BFF safe.
 *   - `.neon.tech` host → `neonDrizzleDb` (the Neon serverless HTTP/WS driver).
 *   - any other (generic TCP) → `pgDrizzleDb` (`pg` is the safe general driver).
 * `NeonThreadRepo` is driver-agnostic (it wraps a `DrizzleLike`), so both seams
 * feed the same repo class unchanged.
 */
export function selectThreadRepo(
  env: Readonly<Record<string, string | undefined>>,
): ThreadRepo {
  const url = env.DATABASE_URL;
  if (url && url.trim()) {
    const db =
      classifyDsn(url) === "neon" ? neonDrizzleDb(url) : pgDrizzleDb(url);
    return new NeonThreadRepo(db);
  }
  return new InMemoryThreadRepo();
}
