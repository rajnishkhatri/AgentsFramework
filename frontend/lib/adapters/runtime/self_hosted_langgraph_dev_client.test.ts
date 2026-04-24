/**
 * L2 tests for SelfHostedLangGraphDevClient (S3.3.1).
 *
 * Failure paths first (FD6.ADAPTER):
 *   - 401 -> AgentAuthError
 *   - 403 -> AgentAuthorizationError
 *   - 429 -> AgentRateLimitError
 *   - 5xx -> AgentServerError
 *   - timeout -> AgentNetworkError
 *
 * Then idempotent cancel (A6) and the happy path (port conformance).
 */

import { describe, expect, it, vi } from "vitest";
import { SelfHostedLangGraphDevClient } from "./self_hosted_langgraph_dev_client";
import {
  AgentAuthError,
  AgentAuthorizationError,
  AgentNetworkError,
  AgentRateLimitError,
  AgentServerError,
} from "./errors";

function fakeFetch(response: Response | (() => Promise<Response>)): typeof fetch {
  return (async () => {
    if (typeof response === "function") return response();
    return response;
  }) as never;
}

const REQ = {
  thread_id: "t1",
  input: { messages: [{ role: "user", content: "hi" }] },
};

describe("SelfHostedLangGraphDevClient.createRun rejection paths [FD6.ADAPTER]", () => {
  it("translates 401 to AgentAuthError", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("nope", { status: 401 })),
      getAccessToken: async () => "tok",
    });
    await expect(client.createRun(REQ)).rejects.toBeInstanceOf(AgentAuthError);
  });

  it("translates 403 to AgentAuthorizationError", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("forbidden", { status: 403 })),
      getAccessToken: async () => "tok",
    });
    await expect(client.createRun(REQ)).rejects.toBeInstanceOf(
      AgentAuthorizationError,
    );
  });

  it("translates 429 to AgentRateLimitError", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("slow down", { status: 429 })),
      getAccessToken: async () => "tok",
    });
    await expect(client.createRun(REQ)).rejects.toBeInstanceOf(AgentRateLimitError);
  });

  it("translates 500 to AgentServerError", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("oops", { status: 500 })),
      getAccessToken: async () => "tok",
    });
    await expect(client.createRun(REQ)).rejects.toBeInstanceOf(AgentServerError);
  });

  it("translates fetch reject to AgentNetworkError", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: (async () => {
        throw new Error("ECONNRESET");
      }) as never,
      getAccessToken: async () => "tok",
    });
    await expect(client.createRun(REQ)).rejects.toBeInstanceOf(AgentNetworkError);
  });
});

describe("SelfHostedLangGraphDevClient happy path", () => {
  it("returns a parsed RunStateView and sends Bearer token", async () => {
    const seenHeaders: Record<string, string> = {};
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: ((url: string, init?: RequestInit) => {
        for (const [k, v] of new Headers(init?.headers ?? {}).entries()) {
          seenHeaders[k] = v;
        }
        return Promise.resolve(
          new Response(
            JSON.stringify({
              run_id: "r1",
              thread_id: "t1",
              status: "running",
              started_at: "2026-04-24T00:00:00Z",
              completed_at: null,
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          ),
        );
      }) as never,
      getAccessToken: async () => "tok-123",
    });
    const view = await client.createRun(REQ);
    expect(view.run_id).toBe("r1");
    expect(view.status).toBe("running");
    expect(seenHeaders["authorization"]).toBe("Bearer tok-123");
  });
});

describe("SelfHostedLangGraphDevClient.cancel idempotency [A6]", () => {
  it("does not throw when called twice for the same run", async () => {
    let calls = 0;
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: ((_url: string) => {
        calls += 1;
        return Promise.resolve(new Response(null, { status: 204 }));
      }) as never,
      getAccessToken: async () => "tok",
    });
    await client.cancel("r1");
    await client.cancel("r1");
    expect(calls).toBe(2);
  });

  it("does not throw when the backend returns 404 (already gone)", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("not found", { status: 404 })),
      getAccessToken: async () => "tok",
    });
    await expect(client.cancel("r1")).resolves.toBeUndefined();
  });
});

describe("SelfHostedLangGraphDevClient port conformance", () => {
  it("implements AgentRuntimeClient (compile-time check via assignment)", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
      getAccessToken: async () => "tok",
    });
    const _typed: import("../../ports/agent_runtime_client").AgentRuntimeClient = client;
    expect(typeof client.streamRun).toBe("function");
  });
});

describe("SelfHostedLangGraphDevClient.streamRun [A3 injection]", () => {
  it("delegates to the composition-injected openUIRuntimeStream factory", async () => {
    const seenRunIds: string[] = [];
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
      getAccessToken: async () => "tok",
      openUIRuntimeStream: (runId) => {
        seenRunIds.push(runId);
        return (async function* () {
          yield {
            type: "run_completed" as const,
            trace_id: "trace-1",
            run_id: runId,
            thread_id: "t1",
          };
        })();
      },
    });
    const collected = [];
    for await (const evt of client.streamRun("r-42")) {
      collected.push(evt);
    }
    expect(seenRunIds).toEqual(["r-42"]);
    expect(collected).toHaveLength(1);
    expect(collected[0]?.trace_id).toBe("trace-1");
  });

  it("throws when streamRun is invoked without an injected factory", () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
      getAccessToken: async () => "tok",
    });
    expect(() => client.streamRun("r-1")).toThrow(/openUIRuntimeStream/);
  });
});
