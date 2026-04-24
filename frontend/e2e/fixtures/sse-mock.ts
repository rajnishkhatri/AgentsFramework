/**
 * SSE mock primitives for Tier 1 (deterministic, CI-safe) Playwright tests.
 *
 * Provides:
 *   - `buildSSEStream`: builds a `ReadableStream<Uint8Array>` of `text/event-stream`
 *     bytes from an array of AG-UI events. Useful when chunked streaming is
 *     supported (T2 mock middleware server).
 *   - `buildSSEBody`: builds the same stream as a single string for use with
 *     Playwright's `route.fulfill({ body })` API at T1.
 *   - `buildSSEHeaders`: returns the streaming response headers that mirror
 *     `proxySSE` in `frontend/lib/transport/edge_proxy.ts`.
 *
 * The Tier 2 mock middleware server (`mock-middleware.ts`) re-uses these helpers
 * to write SSE bytes with controlled inter-event delays, including `: ping`
 * heartbeat comments per the X4 contract (15s send / 30s detect).
 *
 * No imports from `frontend/lib/`: keeping these helpers free of cross-imports
 * means they can be consumed by both browser-side `page.route()` and the
 * standalone Node HTTP server without leaking adapter code.
 */

import type { AGUIEvent } from "../../lib/wire/ag_ui_events";

const ENCODER = new TextEncoder();

/**
 * Build a streaming `ReadableStream<Uint8Array>` of SSE frames. Each event
 * becomes a single `data: <json>\n\n` frame; the stream closes after the
 * last event. Used by the mock middleware HTTP server (T2) where Node's
 * native streaming response can flush bytes incrementally.
 */
export function buildSSEStream(
  events: ReadonlyArray<AGUIEvent>,
  opts?: { delayMs?: number; heartbeatEveryMs?: number },
): ReadableStream<Uint8Array> {
  const delay = opts?.delayMs ?? 50;
  const heartbeatMs = opts?.heartbeatEveryMs;
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
      if (heartbeatMs && heartbeatMs > 0) {
        heartbeatTimer = setInterval(() => {
          try {
            controller.enqueue(ENCODER.encode(": ping\n\n"));
          } catch {
            // controller already closed
          }
        }, heartbeatMs);
      }
      try {
        for (const evt of events) {
          const line = `data: ${JSON.stringify(evt)}\n\n`;
          controller.enqueue(ENCODER.encode(line));
          if (delay > 0) {
            await new Promise((r) => setTimeout(r, delay));
          }
        }
      } finally {
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        controller.close();
      }
    },
  });
}

/**
 * Build a single SSE body string for `route.fulfill({ body })`. Playwright's
 * route handler does not natively chunk streams, so T1 tests use this to
 * deliver the full SSE response in one shot.
 */
export function buildSSEBody(events: ReadonlyArray<AGUIEvent>): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}

/**
 * Streaming response headers matching `proxySSE` in
 * `frontend/lib/transport/edge_proxy.ts`. Used by both T1 (`route.fulfill`)
 * and T2 (mock middleware) so the browser sees the same contract as the
 * production BFF.
 */
export function buildSSEHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    Connection: "keep-alive",
    ...(extra ?? {}),
  };
}
