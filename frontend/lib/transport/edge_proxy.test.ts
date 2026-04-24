/**
 * L2 tests for the BFF SSE edge proxy helper.
 *
 * The proxy runs in a Next.js Route Handler; we test it as a pure function
 * over Web standard Request/Response.
 *
 * Failure paths first.
 */

import { describe, expect, it } from "vitest";
import { proxySSE } from "./edge_proxy";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(enc.encode(chunks[i++]!));
    },
  });
}

async function readAllText(stream: ReadableStream<Uint8Array>): Promise<string> {
  const reader = stream.getReader();
  const dec = new TextDecoder();
  let out = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    if (value) out += dec.decode(value);
  }
  return out;
}

// ── Header verification (X6 / FD5.HDR) ────────────────────────────────

describe("proxySSE response headers [X6]", () => {
  const upstream = new Response(streamOf(["data: hi\n\n"]), {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "x-trace-id": "trace-001",
      "content-encoding": "gzip", // intentional: must be stripped on streaming
    },
  });

  it("sets Content-Type: text/event-stream", () => {
    const res = proxySSE(upstream);
    expect(res.headers.get("content-type")).toBe("text/event-stream");
  });

  it("sets Cache-Control: no-cache, no-transform", () => {
    const res = proxySSE(upstream);
    expect(res.headers.get("cache-control")).toBe("no-cache, no-transform");
  });

  it("sets X-Accel-Buffering: no (disable proxy buffering)", () => {
    const res = proxySSE(upstream);
    expect(res.headers.get("x-accel-buffering")).toBe("no");
  });

  it("sets Connection: keep-alive", () => {
    const res = proxySSE(upstream);
    expect(res.headers.get("connection")).toBe("keep-alive");
  });

  it("strips upstream Content-Encoding (would corrupt SSE byte forwarding)", () => {
    const res = proxySSE(upstream);
    expect(res.headers.get("content-encoding")).toBeNull();
  });

  it("forwards upstream X-Trace-ID (and any non-stripped header)", () => {
    const res = proxySSE(upstream);
    expect(res.headers.get("x-trace-id")).toBe("trace-001");
  });
});

// ── Failure path: upstream non-200 short-circuits ─────────────────────

describe("proxySSE failure paths", () => {
  it("propagates non-2xx upstream status without forwarding the body as SSE", async () => {
    const upstream = new Response("Unauthorized", {
      status: 401,
      headers: { "content-type": "text/plain" },
    });
    const res = proxySSE(upstream);
    expect(res.status).toBe(401);
    expect(res.headers.get("content-type")).toBe("text/plain");
  });

  it("throws when upstream has no body for a 200 response (would wedge SSE)", () => {
    const upstream = new Response(null, {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    });
    expect(() => proxySSE(upstream)).toThrowError(/no body/i);
  });
});

// ── Body forwarding (byte-for-byte) ───────────────────────────────────

describe("proxySSE body forwarding", () => {
  it("forwards upstream chunks byte-for-byte (no transformation)", async () => {
    const upstream = new Response(
      streamOf(["data: a\n\n", "data: b\n\n", "data: c\n\n"]),
      {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      },
    );
    const res = proxySSE(upstream);
    const body = await readAllText(res.body!);
    expect(body).toBe("data: a\n\ndata: b\n\ndata: c\n\n");
  });
});
