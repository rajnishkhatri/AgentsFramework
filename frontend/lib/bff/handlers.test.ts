/**
 * L2 tests for BFF Route Handler logic (S3.9.1).
 *
 * Per FRONTEND_STYLE_GUIDE B6 / FE-AP-3: Route Handlers are composition
 * adapters -- port calls and SSE byte-forward only. No business logic
 * `if/else`. We test the handler factories with in-memory ports.
 *
 * Failure paths first.
 */

import { describe, expect, it, vi } from "vitest";
import {
  makeMemoryCreateHandler,
  makeMemoryDeleteHandler,
  makeMemoryListHandler,
  makeMemorySuppressHandler,
  makeRunCancelHandler,
  makeThreadAppendHandler,
  makeThreadArchiveHandler,
  makeThreadCreateHandler,
  makeThreadGetHandler,
  makeThreadListHandler,
  makeThreadRenameHandler,
} from "./handlers";
import type { MemoryStore } from "../ports/memory_store";
import type { MemoryItem, MemoryType } from "../wire/agent_protocol";
import {
  InMemoryThreadRepo,
  NeonFreeThreadStore,
} from "../adapters/thread_store/neon_free_thread_store";
import type { AgentRuntimeClient } from "../ports/agent_runtime_client";
import type { AuthProvider } from "../ports/auth_provider";

const ALICE = { sub: "alice", org_id: null, roles: [], email: null };

function authYielding(claim: typeof ALICE | null): AuthProvider {
  return {
    getSession: async () => claim,
    getAccessToken: async () => "tok",
    signOut: async () => undefined,
  };
}

describe("makeThreadCreateHandler [B6]", () => {
  it("returns 401 when caller has no session (rejection path first)", async () => {
    const handler = makeThreadCreateHandler({
      auth: authYielding(null),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    });
    const res = await handler(
      new Request("http://x/api/threads", {
        method: "POST",
        body: JSON.stringify({ user_id: "alice" }),
      }),
    );
    expect(res.status).toBe(401);
  });

  it("returns 400 when body is malformed", async () => {
    const handler = makeThreadCreateHandler({
      auth: authYielding(ALICE),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    });
    const res = await handler(
      new Request("http://x/api/threads", {
        method: "POST",
        body: "{not-json",
      }),
    );
    expect(res.status).toBe(400);
  });

  it("creates a thread on the happy path and returns its state", async () => {
    const handler = makeThreadCreateHandler({
      auth: authYielding(ALICE),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    });
    const res = await handler(
      new Request("http://x/api/threads", {
        method: "POST",
        body: JSON.stringify({ user_id: "alice", metadata: {} }),
      }),
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { thread_id: string; user_id: string };
    expect(body.user_id).toBe("alice");
    expect(body.thread_id).toMatch(/^t_/);
  });

  it("Cache-Control is no-store on user-scoped routes [B5]", async () => {
    const handler = makeThreadCreateHandler({
      auth: authYielding(ALICE),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    });
    const res = await handler(
      new Request("http://x/api/threads", {
        method: "POST",
        body: JSON.stringify({ user_id: "alice" }),
      }),
    );
    expect(res.headers.get("cache-control")).toBe("no-store");
  });
});

describe("makeThreadListHandler", () => {
  it("returns the caller's threads only (B6)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    await store.create(ALICE, { user_id: "alice", metadata: {} });
    await store.create(
      { sub: "bob", org_id: null, roles: [], email: null },
      { user_id: "bob", metadata: {} },
    );
    const handler = makeThreadListHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    });
    const res = await handler(new Request("http://x/api/threads"));
    expect(res.status).toBe(200);
    const body = (await res.json()) as { threads: { thread_id: string }[] };
    expect(body.threads).toHaveLength(1);
  });
});

describe("makeThreadGetHandler", () => {
  it("returns 404 when caller is not the owner (no existence oracle)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const handler = makeThreadGetHandler({
      auth: authYielding({ sub: "bob", org_id: null, roles: [], email: null }),
      threadStore: store,
    });
    const res = await handler(
      new Request(`http://x/api/threads/${t.thread_id}`),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(404);
  });
});

describe("makeRunCancelHandler [A6 idempotent]", () => {
  it("returns 204 even when called twice for the same run", async () => {
    const cancel = vi.fn(async () => undefined);
    const runtime: AgentRuntimeClient = {
      streamRun: vi.fn() as never,
      updateUnderstanding: vi.fn() as never,
      cancel,
    };
    const handler = makeRunCancelHandler({
      auth: authYielding(ALICE),
      agentRuntimeClient: runtime,
    });
    const req = () =>
      new Request("http://x/api/run/cancel", {
        method: "POST",
        body: JSON.stringify({ run_id: "r1" }),
      });
    expect((await handler(req())).status).toBe(204);
    expect((await handler(req())).status).toBe(204);
    expect(cancel).toHaveBeenCalledTimes(2);
  });

  it("rejects unauthenticated cancel with 401", async () => {
    const handler = makeRunCancelHandler({
      auth: authYielding(null),
      agentRuntimeClient: {
        streamRun: vi.fn() as never,
        updateUnderstanding: vi.fn() as never,
        cancel: vi.fn() as never,
      },
    });
    const res = await handler(
      new Request("http://x/api/run/cancel", {
        method: "POST",
        body: JSON.stringify({ run_id: "r1" }),
      }),
    );
    expect(res.status).toBe(401);
  });
});

describe("makeUnderstandingEditHandler (Phase 4 edit seam)", () => {
  const validBody = {
    trace_id: "tr-1",
    restated_intent: "Create the file and verify it.",
    success_conditions: ["file exists", "contents verified"],
  };
  const req = (body: unknown) =>
    new Request("http://x/api/run/understanding/thread-1", {
      method: "POST",
      body: JSON.stringify(body),
    });

  it("returns 401 when caller has no session (rejection path first)", async () => {
    const { makeUnderstandingEditHandler } = await import("./handlers");
    const forward = vi.fn();
    const handler = makeUnderstandingEditHandler({
      auth: authYielding(null),
      forward,
    });
    const res = await handler(req(validBody), "thread-1");
    expect(res.status).toBe(401);
    expect(forward).not.toHaveBeenCalled();
  });

  it("returns 422 on a malformed edit (single condition) without forwarding", async () => {
    const { makeUnderstandingEditHandler } = await import("./handlers");
    const forward = vi.fn();
    const handler = makeUnderstandingEditHandler({
      auth: authYielding(ALICE),
      forward,
    });
    const res = await handler(
      req({ ...validBody, success_conditions: ["only one"] }),
      "thread-1",
    );
    expect(res.status).toBe(422);
    expect(forward).not.toHaveBeenCalled();
  });

  it("forwards a valid edit with the bearer token and relays the upstream response", async () => {
    const { makeUnderstandingEditHandler } = await import("./handlers");
    const forward = vi.fn(async () =>
      new Response(JSON.stringify({ ok: true, source: "user_edited" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const handler = makeUnderstandingEditHandler({
      auth: authYielding(ALICE),
      forward,
    });
    const res = await handler(req(validBody), "thread-1");
    expect(res.status).toBe(200);
    expect((await res.json()).source).toBe("user_edited");
    expect(forward).toHaveBeenCalledWith(
      "/run/understanding/thread-1",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          authorization: "Bearer tok",
        }),
      }),
    );
  });
});

// ── Memory panel handlers (Phase 3) ────────────────────────────────────

class FakeMemoryStore implements MemoryStore {
  items: MemoryItem[] = [];
  removed: string[] = [];
  suppressed: Array<{ key: string; suppressed: boolean }> = [];
  async list() {
    return this.items;
  }
  async add(content: string, type: MemoryType) {
    const item: MemoryItem = { key: "k1", type, content, salience: null };
    this.items.push(item);
    return item;
  }
  async remove(key: string) {
    this.removed.push(key);
  }
  async suppress(key: string, suppressed: boolean) {
    this.suppressed.push({ key, suppressed });
  }
}

describe("makeMemoryListHandler [B6]", () => {
  it("returns 401 with no session (rejection first)", async () => {
    const res = await makeMemoryListHandler({
      auth: authYielding(null),
      memoryStore: new FakeMemoryStore(),
    })(new Request("http://x/api/memory"));
    expect(res.status).toBe(401);
  });

  it("returns the caller's items on the happy path", async () => {
    const store = new FakeMemoryStore();
    store.items = [
      { key: "k1", type: "semantic", content: "metric units", salience: 0.7 },
    ];
    const res = await makeMemoryListHandler({
      auth: authYielding(ALICE),
      memoryStore: store,
    })(new Request("http://x/api/memory"));
    expect(res.status).toBe(200);
    expect((await res.json()).items).toHaveLength(1);
  });
});

describe("makeMemoryCreateHandler [B6]", () => {
  it("returns 401 with no session (rejection first)", async () => {
    const res = await makeMemoryCreateHandler({
      auth: authYielding(null),
      memoryStore: new FakeMemoryStore(),
    })(
      new Request("http://x/api/memory", {
        method: "POST",
        body: JSON.stringify({ content: "x" }),
      }),
    );
    expect(res.status).toBe(401);
  });

  it("returns 400 on malformed body", async () => {
    const res = await makeMemoryCreateHandler({
      auth: authYielding(ALICE),
      memoryStore: new FakeMemoryStore(),
    })(new Request("http://x/api/memory", { method: "POST", body: "{bad" }));
    expect(res.status).toBe(400);
  });

  it("returns 400 on empty content (schema gate)", async () => {
    const res = await makeMemoryCreateHandler({
      auth: authYielding(ALICE),
      memoryStore: new FakeMemoryStore(),
    })(
      new Request("http://x/api/memory", {
        method: "POST",
        body: JSON.stringify({ content: "" }),
      }),
    );
    expect(res.status).toBe(400);
  });

  it("adds a memory and echoes the created item", async () => {
    const store = new FakeMemoryStore();
    const res = await makeMemoryCreateHandler({
      auth: authYielding(ALICE),
      memoryStore: store,
    })(
      new Request("http://x/api/memory", {
        method: "POST",
        body: JSON.stringify({ content: "likes dark mode", type: "semantic" }),
      }),
    );
    expect(res.status).toBe(200);
    expect(store.items[0]?.content).toBe("likes dark mode");
  });
});

describe("makeMemoryDeleteHandler [B6]", () => {
  it("returns 401 with no session", async () => {
    const res = await makeMemoryDeleteHandler({
      auth: authYielding(null),
      memoryStore: new FakeMemoryStore(),
    })(new Request("http://x/api/memory/k", { method: "DELETE" }), {
      params: { key: "k" },
    });
    expect(res.status).toBe(401);
  });

  it("removes the keyed item and returns 204", async () => {
    const store = new FakeMemoryStore();
    const res = await makeMemoryDeleteHandler({
      auth: authYielding(ALICE),
      memoryStore: store,
    })(new Request("http://x/api/memory/k1", { method: "DELETE" }), {
      params: { key: "k1" },
    });
    expect(res.status).toBe(204);
    expect(store.removed).toEqual(["k1"]);
  });
});

describe("makeMemorySuppressHandler [Phase B]", () => {
  it("returns 401 with no session (rejection first)", async () => {
    const res = await makeMemorySuppressHandler({
      auth: authYielding(null),
      memoryStore: new FakeMemoryStore(),
    })(
      new Request("http://x/api/memory/k", {
        method: "PATCH",
        body: JSON.stringify({ suppressed: true }),
      }),
      { params: { key: "k" } },
    );
    expect(res.status).toBe(401);
  });

  it("returns 400 on invalid JSON", async () => {
    const res = await makeMemorySuppressHandler({
      auth: authYielding(ALICE),
      memoryStore: new FakeMemoryStore(),
    })(new Request("http://x/api/memory/k", { method: "PATCH", body: "{bad" }), {
      params: { key: "k" },
    });
    expect(res.status).toBe(400);
  });

  it("returns 400 when 'suppressed' is missing/non-boolean", async () => {
    const res = await makeMemorySuppressHandler({
      auth: authYielding(ALICE),
      memoryStore: new FakeMemoryStore(),
    })(
      new Request("http://x/api/memory/k", {
        method: "PATCH",
        body: JSON.stringify({ nope: 1 }),
      }),
      { params: { key: "k" } },
    );
    expect(res.status).toBe(400);
  });

  it("suppresses the keyed item and returns 204", async () => {
    const store = new FakeMemoryStore();
    const res = await makeMemorySuppressHandler({
      auth: authYielding(ALICE),
      memoryStore: store,
    })(
      new Request("http://x/api/memory/k1", {
        method: "PATCH",
        body: JSON.stringify({ suppressed: true }),
      }),
      { params: { key: "k1" } },
    );
    expect(res.status).toBe(204);
    expect(store.suppressed).toEqual([{ key: "k1", suppressed: true }]);
  });

  it("forwards suppressed=false (un-suppress / reversible)", async () => {
    const store = new FakeMemoryStore();
    await makeMemorySuppressHandler({
      auth: authYielding(ALICE),
      memoryStore: store,
    })(
      new Request("http://x/api/memory/k1", {
        method: "PATCH",
        body: JSON.stringify({ suppressed: false }),
      }),
      { params: { key: "k1" } },
    );
    expect(store.suppressed).toEqual([{ key: "k1", suppressed: false }]);
  });
});

describe("makeThreadRenameHandler [B6]", () => {
  it("returns 401 with no session (rejection path first)", async () => {
    const res = await makeThreadRenameHandler({
      auth: authYielding(null),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    })(
      new Request("http://x/api/threads/t", {
        method: "PATCH",
        body: JSON.stringify({ title: "New title" }),
      }),
      { params: { id: "t" } },
    );
    expect(res.status).toBe(401);
  });

  it("returns 400 when the title is empty (schema rejects)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadRenameHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: "" }),
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(400);
  });

  it("returns 404 when the caller is not the owner (no existence oracle)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadRenameHandler({
      auth: authYielding({ sub: "bob", org_id: null, roles: [], email: null }),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: "Hijack" }),
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(404);
  });

  it("renames on the happy path and returns the updated state", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadRenameHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: "Trip to Rome" }),
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { title: string };
    expect(body.title).toBe("Trip to Rome");
  });
});

describe("makeThreadArchiveHandler [B6, A6 idempotent]", () => {
  it("returns 401 with no session", async () => {
    const res = await makeThreadArchiveHandler({
      auth: authYielding(null),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    })(new Request("http://x/api/threads/t", { method: "DELETE" }), {
      params: { id: "t" },
    });
    expect(res.status).toBe(401);
  });

  it("archives the thread and returns 204 (hidden from subsequent list)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadArchiveHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}`, { method: "DELETE" }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(204);
    const page = await store.list(ALICE);
    expect(page.threads).toHaveLength(0);
  });

  it("is idempotent for an unknown/non-owned id (still 204)", async () => {
    const res = await makeThreadArchiveHandler({
      auth: authYielding(ALICE),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    })(new Request("http://x/api/threads/nope", { method: "DELETE" }), {
      params: { id: "nope" },
    });
    expect(res.status).toBe(204);
  });
});

describe("makeThreadAppendHandler [B6, durable transcript]", () => {
  const TURN = { user: "plan my trip", assistant: "where to?", turn_id: "tn-1" };

  it("returns 401 with no session (rejection path first)", async () => {
    const res = await makeThreadAppendHandler({
      auth: authYielding(null),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    })(
      new Request("http://x/api/threads/t/messages", {
        method: "POST",
        body: JSON.stringify(TURN),
      }),
      { params: { id: "t" } },
    );
    expect(res.status).toBe(401);
  });

  it("returns 400 when the body is malformed", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadAppendHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}/messages`, {
        method: "POST",
        body: "{not-json",
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(400);
  });

  it("returns 400 when a required field is missing (schema rejects)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadAppendHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}/messages`, {
        method: "POST",
        body: JSON.stringify({ user: "hi", assistant: "yo" }),
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(400);
  });

  it("returns 404 for an unknown thread (no existence oracle)", async () => {
    const res = await makeThreadAppendHandler({
      auth: authYielding(ALICE),
      threadStore: new NeonFreeThreadStore({ repo: new InMemoryThreadRepo() }),
    })(
      new Request("http://x/api/threads/missing/messages", {
        method: "POST",
        body: JSON.stringify(TURN),
      }),
      { params: { id: "missing" } },
    );
    expect(res.status).toBe(404);
  });

  it("returns 404 when the caller is not the owner (collapses with missing)", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadAppendHandler({
      auth: authYielding({ sub: "bob", org_id: null, roles: [], email: null }),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}/messages`, {
        method: "POST",
        body: JSON.stringify(TURN),
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(404);
  });

  it("appends the turn on the happy path and returns 204", async () => {
    const repo = new InMemoryThreadRepo();
    const store = new NeonFreeThreadStore({ repo });
    const t = await store.create(ALICE, { user_id: "alice", metadata: {} });
    const res = await makeThreadAppendHandler({
      auth: authYielding(ALICE),
      threadStore: store,
    })(
      new Request(`http://x/api/threads/${t.thread_id}/messages`, {
        method: "POST",
        body: JSON.stringify(TURN),
      }),
      { params: { id: t.thread_id } },
    );
    expect(res.status).toBe(204);
    const got = await store.get(ALICE, t.thread_id);
    expect(got?.messages).toHaveLength(2);
    expect(res.headers.get("cache-control")).toBe("no-store");
  });
});
