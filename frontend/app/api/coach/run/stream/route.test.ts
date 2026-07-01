/**
 * Phase 2.1 — coach BFF stream route (FR-F, §5; L1).
 *
 * The coach rides the CHAT runtime (plan OD-3), so this route is the same thin
 * auth-gate + byte-forward as /api/run/stream (B6/F-R4/FE-AP-3): authenticate via
 * the AuthProvider port, forward to the middleware with the WorkOS bearer + SSE
 * accept, pipe the response through proxySSE. No business logic; no secrets
 * (F-R9). The coach `agent_id` rides in the client body, not this route.
 *
 * Failure path first: no session → 401, and the request is NEVER forwarded.
 */

import { describe, expect, it, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const getSession = vi.fn();
const getAccessToken = vi.fn();
const forwardToMiddleware = vi.fn();
const proxySSE = vi.fn();

vi.mock("@/lib/bff/server_composition", () => ({
  serverPortBag: () => ({
    authProvider: { getSession, getAccessToken },
  }),
  forwardToMiddleware: (...args: unknown[]) => forwardToMiddleware(...args),
}));
vi.mock("@/lib/transport/edge_proxy", () => ({
  proxySSE: (...args: unknown[]) => proxySSE(...args),
}));

import { POST } from "./route";

function req(body = '{"thread_id":"t1","input":{},"agent_id":"subject-coach-english"}'): NextRequest {
  return new NextRequest("http://localhost/api/coach/run/stream", {
    method: "POST",
    body,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("coach stream route — failure path first (auth gate)", () => {
  it("returns 401 and does NOT forward when there is no session", async () => {
    getSession.mockResolvedValue(null);
    const res = await POST(req());
    expect(res.status).toBe(401);
    expect(forwardToMiddleware).not.toHaveBeenCalled();
  });

  it("treats a getSession throw as unauthenticated (401, no forward)", async () => {
    getSession.mockRejectedValue(new Error("cookie parse failed"));
    const res = await POST(req());
    expect(res.status).toBe(401);
    expect(forwardToMiddleware).not.toHaveBeenCalled();
  });
});

describe("coach stream route — authed: forward only", () => {
  it("forwards to /run/stream with bearer + SSE accept, pipes through proxySSE", async () => {
    getSession.mockResolvedValue({ user_id: "u1" });
    getAccessToken.mockResolvedValue("tok-123");
    const upstream = new Response("data: hi\n\n");
    forwardToMiddleware.mockResolvedValue(upstream);
    const proxied = new Response("proxied");
    proxySSE.mockReturnValue(proxied);

    const res = await POST(req());

    expect(forwardToMiddleware).toHaveBeenCalledTimes(1);
    const [path, init] = forwardToMiddleware.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/run/stream");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.authorization).toBe("Bearer tok-123");
    expect(headers.accept).toBe("text/event-stream");
    expect(proxySSE).toHaveBeenCalledWith(upstream);
    expect(res).toBe(proxied);
  });
});
