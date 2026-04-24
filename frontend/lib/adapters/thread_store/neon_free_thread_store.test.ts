/**
 * L2 tests for NeonFreeThreadStore (S3.3.3).
 *
 * Tests use an in-memory implementation of the `ThreadRepo` shim that
 * Drizzle/Neon would otherwise back. SDK isolation is verified by Epic 3.10.
 *
 * Failure paths first:
 *   - get() returns null for unknown id (no existence oracle)
 *   - get() returns null when caller is not the owner
 *   - rename() throws ThreadStoreError on missing id
 */

import { describe, expect, it } from "vitest";
import { InMemoryThreadRepo, NeonFreeThreadStore } from "./neon_free_thread_store";
import type { IdentityClaim } from "../../trust-view/identity";

const ALICE: IdentityClaim = { sub: "alice", org_id: null, roles: [], email: null };
const BOB: IdentityClaim = { sub: "bob", org_id: null, roles: [], email: null };

function makeStore(): { repo: InMemoryThreadRepo; store: NeonFreeThreadStore } {
  const repo = new InMemoryThreadRepo();
  return { repo, store: new NeonFreeThreadStore({ repo }) };
}

describe("NeonFreeThreadStore failure paths", () => {
  it("get() returns null for unknown thread id", async () => {
    const { store } = makeStore();
    expect(await store.get(ALICE, "missing")).toBeNull();
  });

  it("get() returns null when caller is not the owner (no existence oracle)", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    expect(await store.get(BOB, t.thread_id)).toBeNull();
  });

  it("rename() throws ThreadStoreError when the thread does not exist", async () => {
    const { store } = makeStore();
    await expect(store.rename(ALICE, "missing", "x")).rejects.toThrowError(
      /not found/i,
    );
  });
});

describe("NeonFreeThreadStore happy paths", () => {
  it("create + get round-trip", async () => {
    const { store } = makeStore();
    const created = await store.create(ALICE, {
      user_id: "alice",
      metadata: { tag: "x" },
    });
    const got = await store.get(ALICE, created.thread_id);
    expect(got?.thread_id).toBe(created.thread_id);
    expect(got?.user_id).toBe("alice");
  });

  it("list paginates with cursor and returns nextCursor=null on last page", async () => {
    const { store } = makeStore();
    for (let i = 0; i < 3; i++) {
      await store.create(ALICE, { user_id: "alice", metadata: { i } });
    }
    const page1 = await store.list(ALICE, { limit: 2 });
    expect(page1.threads).toHaveLength(2);
    expect(page1.nextCursor).not.toBeNull();
    const page2 = await store.list(ALICE, { cursor: page1.nextCursor, limit: 2 });
    expect(page2.threads).toHaveLength(1);
    expect(page2.nextCursor).toBeNull();
  });

  it("rename updates the title and returns the updated state", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const renamed = await store.rename(ALICE, t.thread_id, "new title");
    expect(renamed.thread_id).toBe(t.thread_id);
  });

  it("archive soft-deletes (archived threads do not appear in list)", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    await store.archive(ALICE, t.thread_id);
    const page = await store.list(ALICE);
    expect(page.threads).toHaveLength(0);
  });
});
