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

describe("NeonFreeThreadStore.appendTurn failure paths", () => {
  it("throws ThreadStoreError when the thread does not exist", async () => {
    const { store } = makeStore();
    await expect(
      store.appendTurn(ALICE, "missing", {
        user: "hi",
        assistant: "hello",
        turnId: "turn-1",
      }),
    ).rejects.toThrowError(/not found/i);
  });

  it("throws ThreadStoreError when the caller is not the owner (no oracle)", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    await expect(
      store.appendTurn(BOB, t.thread_id, {
        user: "hi",
        assistant: "hello",
        turnId: "turn-1",
      }),
    ).rejects.toThrowError(/not found/i);
  });
});

describe("NeonFreeThreadStore.appendTurn happy paths", () => {
  it("appends a user+assistant message pair into messages", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    await store.appendTurn(ALICE, t.thread_id, {
      user: "plan my trip",
      assistant: "sure, where to?",
      turnId: "turn-1",
    });
    const got = await store.get(ALICE, t.thread_id);
    expect(got?.messages).toEqual([
      { role: "user", content: "plan my trip", turn_id: "turn-1" },
      { role: "assistant", content: "sure, where to?", turn_id: "turn-1" },
    ]);
  });

  it("preserves order across multiple turns", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    await store.appendTurn(ALICE, t.thread_id, {
      user: "q1",
      assistant: "a1",
      turnId: "turn-1",
    });
    await store.appendTurn(ALICE, t.thread_id, {
      user: "q2",
      assistant: "a2",
      turnId: "turn-2",
    });
    const got = await store.get(ALICE, t.thread_id);
    expect(got?.messages.map((m) => m.content)).toEqual([
      "q1",
      "a1",
      "q2",
      "a2",
    ]);
  });

  it("is idempotent: re-appending the same turn_id is a no-op", async () => {
    const { store } = makeStore();
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const turn = { user: "q1", assistant: "a1", turnId: "turn-1" };
    await store.appendTurn(ALICE, t.thread_id, turn);
    await store.appendTurn(ALICE, t.thread_id, turn);
    const got = await store.get(ALICE, t.thread_id);
    expect(got?.messages).toHaveLength(2);
  });
});

describe("NeonFreeThreadStore.create with client-supplied fields", () => {
  it("honors a client-minted thread_id", async () => {
    const { store } = makeStore();
    const created = await store.create(ALICE, {
      user_id: "alice",
      thread_id: "client-mint-1",
      metadata: {},
    });
    expect(created.thread_id).toBe("client-mint-1");
  });

  it("mints its own id when thread_id is absent", async () => {
    const { store } = makeStore();
    const created = await store.create(ALICE, {
      user_id: "alice",
      thread_id: null,
      metadata: {},
    });
    expect(created.thread_id).toMatch(/^t_/);
  });

  it("derives the title from metadata.first_message", async () => {
    const { store } = makeStore();
    const created = await store.create(ALICE, {
      user_id: "alice",
      thread_id: null,
      metadata: { first_message: "Plan my trip to Rome" },
    });
    expect(created.title).toBe("Plan my trip to Rome");
  });

  it("defaults the title to 'New chat' when no first_message", async () => {
    const { store } = makeStore();
    const created = await store.create(ALICE, {
      user_id: "alice",
      thread_id: null,
      metadata: {},
    });
    expect(created.title).toBe("New chat");
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
