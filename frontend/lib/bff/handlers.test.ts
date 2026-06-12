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
  makeRunCancelHandler,
  makeThreadCreateHandler,
  makeThreadGetHandler,
  makeThreadListHandler,
} from "./handlers";
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
