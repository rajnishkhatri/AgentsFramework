/**
 * connectFetchSSE tests (eval-UI F1, plan §8.6-E Option A).
 *
 * Failure paths first (FD6 / TAP-4): HTTP errors, fetch rejection,
 * mid-stream drops, malformed frames -- before the happy path.
 *
 * The transport reads the BFF POST /run/stream response body as an SSE
 * stream over fetch+ReadableStream (never EventSource) so Playwright
 * `page.route` mocks keep intercepting (Playwright #15353).
 */

import { describe, expect, it } from "vitest";
import {
  connectFetchSSE,
  isFetchSSEParseError,
  isSSEHttpError,
  isSSEStreamDrop,
  type FetchSSEYield,
} from "./fetch_sse_client";

const TRACE = "trace-f1-test";

function frame(eventName: string, data: unknown): string {
  return `event: ${eventName}\ndata: ${JSON.stringify(data)}\n\n`;
}

function textEvent(delta: string): Record<string, unknown> {
  return {
    type: "TEXT_MESSAGE_CONTENT",
    message_id: "m1",
    delta,
    raw_event: { trace_id: TRACE },
  };
}

function sseResponse(
  chunks: string[],
  init: { status?: number } = {},
): Response {
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

function fetchReturning(res: Response): typeof fetch {
  return (() => Promise.resolve(res)) as typeof fetch;
}

async function collect(fetchImpl: typeof fetch): Promise<FetchSSEYield[]> {
  const out: FetchSSEYield[] = [];
  for await (const y of connectFetchSSE({
    url: "/api/run/stream",
    body: { thread_id: "t1", input: { messages: [] } },
    fetchImpl,
  })) {
    out.push(y);
  }
  return out;
}

describe("connectFetchSSE — failure paths first", () => {
  it("yields an http-error sentinel (and nothing else) on 401", async () => {
    const out = await collect(
      fetchReturning(new Response("unauthorized", { status: 401 })),
    );
    expect(out).toHaveLength(1);
    expect(isSSEHttpError(out[0]!)).toBe(true);
    if (isSSEHttpError(out[0]!)) expect(out[0]!.status).toBe(401);
  });

  it("yields a stream-drop sentinel when fetch itself rejects", async () => {
    const rejecting = (() =>
      Promise.reject(new Error("ECONNREFUSED"))) as typeof fetch;
    const out = await collect(rejecting);
    expect(out).toHaveLength(1);
    expect(isSSEStreamDrop(out[0]!)).toBe(true);
  });

  it("yields a stream-drop sentinel when the body reader throws mid-stream", async () => {
    const encoder = new TextEncoder();
    // Deliver one chunk, then fail the next read -- erroring in start()
    // would discard the queued chunk per the Streams spec.
    let delivered = false;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (!delivered) {
          delivered = true;
          controller.enqueue(
            encoder.encode(frame("TEXT_MESSAGE_CONTENT", textEvent("hi"))),
          );
        } else {
          controller.error(new Error("connection reset"));
        }
      },
    });
    const out = await collect(
      fetchReturning(new Response(stream, { status: 200 })),
    );
    expect(out).toHaveLength(2);
    expect(isSSEStreamDrop(out[1]!)).toBe(true);
  });

  it("yields a parse-error sentinel for non-JSON data", async () => {
    const out = await collect(
      fetchReturning(sseResponse(["event: message\ndata: not-json\n\n"])),
    );
    expect(out).toHaveLength(1);
    expect(isFetchSSEParseError(out[0]!)).toBe(true);
  });

  it("yields a parse-error sentinel for JSON that fails the AGUI schema", async () => {
    const out = await collect(
      fetchReturning(sseResponse([frame("message", { type: "NOT_A_TYPE" })])),
    );
    expect(out).toHaveLength(1);
    expect(isFetchSSEParseError(out[0]!)).toBe(true);
  });

  it("translates a server `event: error` frame into a stream-drop sentinel", async () => {
    const out = await collect(
      fetchReturning(
        sseResponse([frame("error", { message: "agent exploded", code: null })]),
      ),
    );
    expect(out).toHaveLength(1);
    expect(isSSEStreamDrop(out[0]!)).toBe(true);
    if (isSSEStreamDrop(out[0]!)) {
      expect(out[0]!.message).toContain("agent exploded");
    }
  });
});

describe("connectFetchSSE — happy path", () => {
  it("parses well-formed frames into AGUIEvents in order", async () => {
    const out = await collect(
      fetchReturning(
        sseResponse([
          frame("TEXT_MESSAGE_CONTENT", textEvent("Hel")),
          frame("TEXT_MESSAGE_CONTENT", textEvent("lo")),
        ]),
      ),
    );
    expect(out).toHaveLength(2);
    expect(out.every((y) => "type" in y)).toBe(true);
    const deltas = out.map((y) => ("delta" in y ? y.delta : ""));
    expect(deltas).toEqual(["Hel", "lo"]);
  });

  it("reassembles a frame split across two network chunks", async () => {
    const whole = frame("TEXT_MESSAGE_CONTENT", textEvent("split"));
    const cut = Math.floor(whole.length / 2);
    const out = await collect(
      fetchReturning(sseResponse([whole.slice(0, cut), whole.slice(cut)])),
    );
    expect(out).toHaveLength(1);
    expect("delta" in out[0]! && out[0]!.delta).toBe("split");
  });

  it("skips the `event: done` / [DONE] sentinel frame silently", async () => {
    const out = await collect(
      fetchReturning(
        sseResponse([
          frame("TEXT_MESSAGE_CONTENT", textEvent("x")),
          "event: done\ndata: [DONE]\n\n",
        ]),
      ),
    );
    expect(out).toHaveLength(1);
  });

  it("flushes a trailing frame that arrives without the final blank line", async () => {
    const whole = frame("TEXT_MESSAGE_CONTENT", textEvent("tail"));
    const out = await collect(
      fetchReturning(sseResponse([whole.slice(0, whole.length - 2)])),
    );
    expect(out).toHaveLength(1);
    expect("delta" in out[0]! && out[0]!.delta).toBe("tail");
  });

  it("POSTs the JSON body with credentials include and SSE accept header", async () => {
    let captured: { url: unknown; init: RequestInit | undefined } | null = null;
    const spying = ((url: unknown, init?: RequestInit) => {
      captured = { url, init };
      return Promise.resolve(sseResponse([]));
    }) as typeof fetch;
    await collect(spying);
    expect(captured).not.toBeNull();
    expect(captured!.url).toBe("/api/run/stream");
    expect(captured!.init?.method).toBe("POST");
    expect(captured!.init?.credentials).toBe("include");
    const headers = captured!.init?.headers as Record<string, string>;
    expect(headers.accept).toContain("text/event-stream");
    expect(JSON.parse(String(captured!.init?.body))).toEqual({
      thread_id: "t1",
      input: { messages: [] },
    });
  });
});
