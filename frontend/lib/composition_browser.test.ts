/**
 * Browser composition root tests (eval-UI F1, plan §8.6-E Option A).
 *
 * L2 contract tests over the assembled stream: connectFetchSSE (real
 * transport) + agUiToUiRuntime (real translator) + tool aggregator (real),
 * driven by a recorded SSE byte stream behind a fake `fetch` -- no
 * hand-stubbed reducers (Anti-Pattern: Mock Addiction) and no live agent.
 *
 * Failure paths first: HTTP status mapping, parse failure, mid-stream
 * drop, missing terminal event (Runtime Contract §1), missing trace_id.
 */

import { describe, expect, it } from "vitest";
import { makeFetchUIRuntimeStream, buildBrowserRuntimeClient } from "./composition_browser";
import type { UIRuntimeEvent } from "./wire/ui_runtime_events";

const TRACE = "trace-cb-1";

function frame(eventName: string, data: unknown): string {
  return `event: ${eventName}\ndata: ${JSON.stringify(data)}\n\n`;
}

function sseResponse(chunks: string[], init: { status?: number } = {}): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return new Response(stream, {
    status: init.status ?? 200,
    headers: { "content-type": "text/event-stream" },
  });
}

const REQ = { thread_id: "t1", input: { messages: [{ role: "user", content: "hi" }] } };

async function run(chunks: string[], status = 200): Promise<UIRuntimeEvent[]> {
  const fetchImpl = (() =>
    Promise.resolve(sseResponse(chunks, { status }))) as typeof fetch;
  const open = makeFetchUIRuntimeStream("/api", fetchImpl);
  const out: UIRuntimeEvent[] = [];
  for await (const evt of open(REQ)) out.push(evt);
  return out;
}

function raw(extra: Record<string, unknown>): Record<string, unknown> {
  return { raw_event: { trace_id: TRACE }, ...extra };
}

const RUN_STARTED = frame(
  "RUN_STARTED",
  raw({ type: "RUN_STARTED", run_id: "r1", thread_id: "t1" }),
);
const RUN_FINISHED = frame(
  "RUN_FINISHED",
  raw({ type: "RUN_FINISHED", run_id: "r1", thread_id: "t1" }),
);

function text(delta: string): string {
  return frame(
    "TEXT_MESSAGE_CONTENT",
    raw({ type: "TEXT_MESSAGE_CONTENT", message_id: "m1", delta }),
  );
}

describe("makeFetchUIRuntimeStream — failure paths first", () => {
  it("maps HTTP 401 to a single terminal run_error{auth_error}", async () => {
    const out = await run([], 401);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ type: "run_error", error_type: "auth_error" });
  });

  it("maps HTTP 429 to run_error{rate_limit_error}", async () => {
    const out = await run([], 429);
    expect(out[0]).toMatchObject({ type: "run_error", error_type: "rate_limit_error" });
  });

  it("maps HTTP 503 to run_error{server_error}", async () => {
    const out = await run([], 503);
    expect(out[0]).toMatchObject({ type: "run_error", error_type: "server_error" });
  });

  it("maps a malformed frame to run_error{wire_parse_error} and stops", async () => {
    const out = await run([RUN_STARTED, "event: message\ndata: ???\n\n", text("x")]);
    expect(out.at(-1)).toMatchObject({
      type: "run_error",
      error_type: "wire_parse_error",
    });
    // Nothing after the error -- the stream is terminal.
    expect(out.filter((e) => e.type === "chat_message_delta")).toHaveLength(0);
  });

  it("synthesizes run_error{network_error} when the stream ends without a terminal event (Runtime Contract §1)", async () => {
    const out = await run([RUN_STARTED, text("partial")]);
    const last = out.at(-1);
    expect(last).toMatchObject({ type: "run_error", error_type: "network_error" });
    expect(
      "message" in (last as object) ? (last as { message: string }).message : "",
    ).toContain("terminal");
  });

  it("maps a fetch rejection to run_error{network_error}", async () => {
    const rejecting = (() => Promise.reject(new Error("offline"))) as typeof fetch;
    const open = makeFetchUIRuntimeStream("/api", rejecting);
    const out: UIRuntimeEvent[] = [];
    for await (const evt of open(REQ)) out.push(evt);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({ type: "run_error", error_type: "network_error" });
  });

  it("a tool event missing raw_event.trace_id becomes run_error{wire_parse_error} (F-R7)", async () => {
    const out = await run([
      RUN_STARTED,
      frame("TOOL_CALL_START", {
        type: "TOOL_CALL_START",
        tool_call_id: "tc1",
        tool_call_name: "file_io",
      }),
    ]);
    expect(out.at(-1)).toMatchObject({
      type: "run_error",
      error_type: "wire_parse_error",
    });
  });
});

describe("makeFetchUIRuntimeStream — trajectory happy path", () => {
  it("yields run lifecycle, text deltas, and tool_render updates in trajectory order", async () => {
    const out = await run([
      RUN_STARTED,
      text("Let me check… "),
      frame("TOOL_CALL_START", raw({
        type: "TOOL_CALL_START",
        tool_call_id: "tc1",
        tool_call_name: "file_io",
      })),
      frame("TOOL_CALL_ARGS", raw({
        type: "TOOL_CALL_ARGS",
        tool_call_id: "tc1",
        delta: '{"path":"/tmp/x"}',
      })),
      frame("TOOL_RESULT", raw({
        type: "TOOL_RESULT",
        tool_call_id: "tc1",
        content: "file contents",
        role: "tool",
      })),
      text("Done."),
      RUN_FINISHED,
    ]);

    const types = out.map((e) => e.type);
    expect(types[0]).toBe("run_started");
    expect(types.at(-1)).toBe("run_completed");

    const toolEvents = out.filter((e) => e.type === "tool_render");
    expect(toolEvents.length).toBeGreaterThanOrEqual(2);
    const first = toolEvents[0];
    const last = toolEvents.at(-1);
    if (first?.type !== "tool_render" || last?.type !== "tool_render") {
      throw new Error("expected tool_render events");
    }
    expect(first.request.status).toBe("running");
    expect(first.request.tool_name).toBe("file_io");
    expect(last.request.status).toBe("completed");
    expect(last.request.output).toBe("file contents");
    expect(last.request.input).toEqual({ path: "/tmp/x" });

    // tool_render lands between the two text deltas (trajectory order).
    const idxToolFirst = types.indexOf("tool_render");
    const idxText2 = types.lastIndexOf("chat_message_delta");
    expect(idxToolFirst).toBeLessThan(idxText2);

    // Every event carries the forwarded trace_id (W5 / F-R7).
    for (const evt of out) {
      expect(evt.trace_id).toBe(TRACE);
    }
  });

  it("step_meter CUSTOM events surface as step_progress with the real count", async () => {
    const out = await run([
      RUN_STARTED,
      frame("CUSTOM", raw({
        type: "CUSTOM",
        name: "step_meter",
        value: { step: 3, step_name: "evaluation" },
      })),
      RUN_FINISHED,
    ]);
    expect(out).toContainEqual({
      type: "step_progress",
      trace_id: TRACE,
      step: 3,
      step_name: "evaluation",
    });
  });
});

describe("buildBrowserRuntimeClient", () => {
  it("streams through the injected fetch (proves page.route-able transport)", async () => {
    let posted: string | null = null;
    const fetchImpl = ((url: unknown, init?: RequestInit) => {
      posted = String(url);
      void init;
      return Promise.resolve(sseResponse([RUN_STARTED, RUN_FINISHED]));
    }) as typeof fetch;
    const client = buildBrowserRuntimeClient({ baseUrl: "/api", fetchImpl });
    const out: UIRuntimeEvent[] = [];
    for await (const evt of client.streamRun(REQ)) out.push(evt);
    expect(posted).toBe("/api/run/stream");
    expect(out.map((e) => e.type)).toEqual(["run_started", "run_completed"]);
  });
});
