/**
 * SelfHostedLangGraphDevClient tests.
 *
 * Failure paths first (FD6). Since eval-UI F1, the adapter is a thin
 * seam: `streamRun(req)` delegates to the composition-injected stream
 * factory (Rule A3; HTTP-status -> run_error mapping is covered in
 * `composition_browser.test.ts`), and `cancel` keeps the typed-error
 * contract.
 */

import { describe, expect, it } from "vitest";
import { SelfHostedLangGraphDevClient } from "./self_hosted_langgraph_dev_client";
import type { RunCreateRequest } from "../../wire/agent_protocol";

const REQ: RunCreateRequest = {
  thread_id: "t1",
  input: { messages: [{ role: "user", content: "hi" }] },
};

function fakeFetch(res: Response): typeof fetch {
  return (() => Promise.resolve(res)) as typeof fetch;
}

describe("SelfHostedLangGraphDevClient.streamRun — failure path first [A3 injection]", () => {
  it("throws when streamRun is invoked without an injected factory", () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
    });
    expect(() => client.streamRun(REQ)).toThrow(/openUIRuntimeStream/);
  });

  it("delegates the full run request to the composition-injected factory", async () => {
    const seenRequests: RunCreateRequest[] = [];
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
      openUIRuntimeStream: (req) => {
        seenRequests.push(req);
        return (async function* () {
          yield {
            type: "run_completed" as const,
            trace_id: "trace-1",
            run_id: "r1",
            thread_id: req.thread_id,
          };
        })();
      },
    });
    const collected = [];
    for await (const evt of client.streamRun(REQ)) {
      collected.push(evt);
    }
    expect(seenRequests).toEqual([REQ]);
    expect(collected).toHaveLength(1);
    expect(collected[0]?.trace_id).toBe("trace-1");
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
    });
    await client.cancel("r1");
    await client.cancel("r1");
    expect(calls).toBe(2);
  });

  it("does not throw when the backend returns 404 (already gone)", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("not found", { status: 404 })),
    });
    await expect(client.cancel("r1")).resolves.toBeUndefined();
  });

  it("does not throw when the network is down (swallow per A6)", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: (() => Promise.reject(new Error("offline"))) as typeof fetch,
    });
    await expect(client.cancel("r1")).resolves.toBeUndefined();
  });

  it("surfaces AgentAuthError on 401", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("nope", { status: 401 })),
    });
    await expect(client.cancel("r1")).rejects.toThrow(/auth/i);
  });
});

describe("SelfHostedLangGraphDevClient port conformance", () => {
  it("implements AgentRuntimeClient (compile-time check via assignment)", () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
    });
    const _typed: import("../../ports/agent_runtime_client").AgentRuntimeClient =
      client;
    expect(typeof _typed.streamRun).toBe("function");
    expect(typeof _typed.cancel).toBe("function");
  });
});

describe("SelfHostedLangGraphDevClient.updateUnderstanding — failure path first (Phase 4)", () => {
  const EDIT = {
    trace_id: "tr-1",
    restated_intent: "Only compare the options.",
    success_conditions: ["compares options", "grounded in task"],
  };

  it("throws AgentAuthError on 401", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response("nope", { status: 401 })),
    });
    await expect(client.updateUnderstanding("t1", EDIT)).rejects.toThrow(
      /auth/i,
    );
  });

  it("throws with the upstream detail on 409 (run already completed)", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(
        new Response(JSON.stringify({ detail: "run already completed" }), {
          status: 409,
        }),
      ),
    });
    await expect(client.updateUnderstanding("t1", EDIT)).rejects.toThrow(
      /already completed/,
    );
  });

  it("throws AgentNetworkError when the network is down", async () => {
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: (() => Promise.reject(new Error("offline"))) as typeof fetch,
    });
    await expect(client.updateUnderstanding("t1", EDIT)).rejects.toThrow(
      /offline/,
    );
  });

  it("POSTs the edit to /run/understanding/{threadId} and resolves on 200", async () => {
    const seen: Array<{ url: string; body: unknown }> = [];
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: ((url: string, init?: RequestInit) => {
        seen.push({ url, body: JSON.parse(String(init?.body)) });
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true }), { status: 200 }),
        );
      }) as typeof fetch,
    });
    await client.updateUnderstanding("thread/1", EDIT);
    expect(seen).toHaveLength(1);
    // Thread id is URL-encoded (it lands in a path segment).
    expect(seen[0]?.url).toBe("/api/run/understanding/thread%2F1");
    expect(seen[0]?.body).toEqual(EDIT);
  });
});

describe("SelfHostedLangGraphDevClient.streamRun — abort signal passthrough (Phase 4 pause)", () => {
  it("forwards the AbortSignal to the composition-injected factory", async () => {
    const seenSignals: Array<AbortSignal | undefined> = [];
    const client = new SelfHostedLangGraphDevClient({
      baseUrl: "/api",
      fetchImpl: fakeFetch(new Response(null, { status: 204 })),
      openUIRuntimeStream: (req, opts) => {
        seenSignals.push(opts?.signal);
        return (async function* () {
          yield {
            type: "run_completed" as const,
            trace_id: "trace-1",
            run_id: "r1",
            thread_id: req.thread_id,
          };
        })();
      },
    });
    const controller = new AbortController();
    for await (const _evt of client.streamRun(REQ, { signal: controller.signal })) {
      /* drain */
    }
    expect(seenSignals).toEqual([controller.signal]);
  });
});
