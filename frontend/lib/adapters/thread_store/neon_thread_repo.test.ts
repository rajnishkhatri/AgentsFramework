/**
 * L2 tests for NeonThreadRepo (live-infra Piece C).
 *
 * The repo is the Drizzle/Neon-backed implementation of the narrow
 * `ThreadRepo` shim that `NeonFreeThreadStore` depends on. Per A4 / F-R8 no
 * Drizzle or Neon vendor type may escape the adapter boundary — the repo's
 * public surface is `ThreadRepo` (rows in/out are plain `ThreadRow`).
 *
 * We inject a `FakeDb` that mimics the tiny slice of the drizzle query builder
 * the repo uses (insert/select/update chains resolving to rows). This keeps the
 * test fast + offline while still exercising the row⇄state mapping, the
 * ownership-aware list filter, the soft-delete filter, and error translation
 * (a rejecting db → ThreadStoreError, never a raw vendor error).
 *
 * Failure paths first (TAP-4): findOne miss → null; db rejection → translated.
 */

import { describe, expect, it } from "vitest";
import {
  NeonThreadRepo,
  selectThreadRepo,
  type DrizzleLike,
} from "./neon_thread_repo";
import {
  InMemoryThreadRepo,
  ThreadStoreError,
} from "./neon_free_thread_store";

interface Row {
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
 * Minimal in-memory fake of the drizzle query-builder surface the repo calls.
 * The repo passes plain predicate objects; the fake interprets them. This is a
 * behavioral fake (records + answers), not a mock of internal calls.
 */
function makeFakeDb(seed: Row[] = []): { db: DrizzleLike; rows: Row[] } {
  const rows: Row[] = [...seed];
  const db: DrizzleLike = {
    async insertThread(row: Row): Promise<void> {
      rows.push({ ...row });
    },
    async findThread(threadId: string): Promise<Row | null> {
      return rows.find((r) => r.thread_id === threadId) ?? null;
    },
    async listThreads(opts): Promise<Row[]> {
      const visible = rows
        .filter((r) => r.user_id === opts.ownerSub && r.archived_at == null)
        .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
      let start = 0;
      if (opts.cursor) {
        const idx = visible.findIndex((r) => r.thread_id === opts.cursor);
        start = idx === -1 ? visible.length : idx + 1;
      }
      return visible.slice(start, start + opts.limit);
    },
    async updateThread(threadId, patch): Promise<Row | null> {
      const r = rows.find((x) => x.thread_id === threadId);
      if (!r) return null;
      Object.assign(r, patch, { updated_at: new Date().toISOString() });
      return { ...r };
    },
  };
  return { db, rows };
}

function rejectingDb(): DrizzleLike {
  const boom = () => Promise.reject(new Error("ECONNRESET neon vendor noise"));
  return {
    insertThread: boom,
    findThread: boom,
    listThreads: boom,
    updateThread: boom,
  };
}

const baseRow = (over: Partial<Row> = {}): Row => ({
  thread_id: "t1",
  user_id: "alice",
  title: "New chat",
  messages: [],
  metadata: {},
  created_at: "2026-06-17T00:00:00.000Z",
  updated_at: "2026-06-17T00:00:00.000Z",
  archived_at: null,
  ...over,
});

describe("NeonThreadRepo — failure paths first", () => {
  it("findOne returns null for an unknown id", async () => {
    const { db } = makeFakeDb();
    const repo = new NeonThreadRepo(db);
    expect(await repo.findOne("missing")).toBeNull();
  });

  it("update returns null for an unknown id", async () => {
    const { db } = makeFakeDb();
    const repo = new NeonThreadRepo(db);
    expect(await repo.update("missing", { title: "x" })).toBeNull();
  });

  it("translates a db rejection to ThreadStoreError (no vendor type escapes)", async () => {
    const repo = new NeonThreadRepo(rejectingDb());
    await expect(repo.findOne("t1")).rejects.toBeInstanceOf(ThreadStoreError);
    await expect(
      repo.list({ ownerSub: "alice", cursor: null, limit: 10 }),
    ).rejects.toBeInstanceOf(ThreadStoreError);
    await expect(repo.insert(baseRow())).rejects.toBeInstanceOf(
      ThreadStoreError,
    );
  });
});

describe("NeonThreadRepo — CRUD + mapping", () => {
  it("insert then findOne round-trips the row shape", async () => {
    const { db } = makeFakeDb();
    const repo = new NeonThreadRepo(db);
    await repo.insert(baseRow({ title: "Hello", messages: [{ role: "user" }] }));
    const got = await repo.findOne("t1");
    expect(got).not.toBeNull();
    expect(got!.title).toBe("Hello");
    expect(got!.messages).toEqual([{ role: "user" }]);
    expect(got!.archived_at).toBeNull();
  });

  it("list is owner-scoped, newest-first, and hides archived rows", async () => {
    const { db } = makeFakeDb([
      baseRow({ thread_id: "t1", created_at: "2026-06-17T00:00:01.000Z" }),
      baseRow({ thread_id: "t2", created_at: "2026-06-17T00:00:02.000Z" }),
      baseRow({
        thread_id: "t3",
        archived_at: "2026-06-17T00:00:03.000Z",
      }),
      baseRow({ thread_id: "t4", user_id: "bob" }),
    ]);
    const repo = new NeonThreadRepo(db);
    const { rows, nextCursor } = await repo.list({
      ownerSub: "alice",
      cursor: null,
      limit: 10,
    });
    const ids = rows.map((r) => r.thread_id);
    expect(ids).toEqual(["t2", "t1"]); // newest-first, no archived, no bob
    expect(nextCursor).toBeNull();
  });

  it("list paginates with a cursor and reports nextCursor on a full page", async () => {
    const seed = [1, 2, 3].map((i) =>
      baseRow({
        thread_id: `t${i}`,
        created_at: `2026-06-17T00:00:0${i}.000Z`,
      }),
    );
    const repo = new NeonThreadRepo(makeFakeDb(seed).db);
    const page1 = await repo.list({ ownerSub: "alice", cursor: null, limit: 2 });
    expect(page1.rows.map((r) => r.thread_id)).toEqual(["t3", "t2"]);
    expect(page1.nextCursor).toBe("t2");
    const page2 = await repo.list({
      ownerSub: "alice",
      cursor: page1.nextCursor,
      limit: 2,
    });
    expect(page2.rows.map((r) => r.thread_id)).toEqual(["t1"]);
    expect(page2.nextCursor).toBeNull();
  });

  it("update patches the row and returns the merged shape", async () => {
    const { db } = makeFakeDb([baseRow()]);
    const repo = new NeonThreadRepo(db);
    const updated = await repo.update("t1", { title: "Renamed" });
    expect(updated!.title).toBe("Renamed");
  });

  it("selectThreadRepo falls back to in-memory without DATABASE_URL", () => {
    expect(selectThreadRepo({})).toBeInstanceOf(InMemoryThreadRepo);
    expect(selectThreadRepo({ DATABASE_URL: "" })).toBeInstanceOf(
      InMemoryThreadRepo,
    );
    expect(selectThreadRepo({ DATABASE_URL: "   " })).toBeInstanceOf(
      InMemoryThreadRepo,
    );
  });

  it("selectThreadRepo builds a NeonThreadRepo when DATABASE_URL is set", () => {
    // A syntactically-valid Neon URL: neonDrizzleDb constructs the client
    // lazily (no network on construction), so this asserts the SELECTION.
    const repo = selectThreadRepo({
      DATABASE_URL: "postgresql://u:p@ep-test.neon.tech/db?sslmode=require",
    });
    expect(repo).toBeInstanceOf(NeonThreadRepo);
  });

  it("works end-to-end through NeonFreeThreadStore", async () => {
    // The repo is the dependency NeonFreeThreadStore was designed for; prove the
    // seam by driving the store with a NeonThreadRepo over the fake db.
    const { NeonFreeThreadStore } = await import("./neon_free_thread_store");
    const repo = new NeonThreadRepo(makeFakeDb().db);
    const store = new NeonFreeThreadStore({ repo });
    const id: import("../../trust-view/identity").IdentityClaim = {
      sub: "alice",
      org_id: null,
      roles: [],
      email: null,
    };
    const created = await store.create(id, { user_id: "alice", metadata: {} });
    const got = await store.get(id, created.thread_id);
    expect(got?.thread_id).toBe(created.thread_id);
  });
});
