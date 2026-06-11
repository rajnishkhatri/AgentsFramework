/**
 * Fetch-SSE client (eval-UI F1, plan §8.6-E Option A).
 *
 * The browser reads the BFF `POST /run/stream` response body as an SSE
 * stream over `fetch`+`ReadableStream` -- NEVER `EventSource`. This is a
 * binding architecture rule: Playwright `page.route` cannot intercept
 * `EventSource` (Playwright #15353), so the fetch path is what keeps the
 * per-commit T1 mock net alive while testing the real browser transport.
 *
 * The frame-parse loop is promoted from the placeholder
 * `app/chat-shell.tsx` (its lines 90-144), which was the only working
 * fetch-SSE reader in the tree. Heartbeat-timeout and Last-Event-ID
 * resumption are intentionally absent on this path (decided 2026-06-11):
 * eval runs are short and reload-to-retry is acceptable; `connectSSE`
 * (sse_client.ts) remains the home for resumption semantics server-side.
 *
 * Per X2 every data frame is Zod-parsed; failures yield a transport-local
 * sentinel rather than throwing into the consumer. The composition root
 * translates sentinels into `RunErrorEvent`s -- transport CANNOT import
 * translators (architecture test S3.10.1).
 *
 * Imports: `wire/` + sibling transport only. No translators, no adapters,
 * no SDK.
 */

import { AGUIEventSchema } from "../wire/ag_ui_events";
import type { SSEParseError } from "./sse_client";

/** Non-2xx HTTP response before any stream bytes arrived. */
export type SSEHttpError = {
  readonly __kind: "sse_http_error";
  readonly status: number;
  readonly message: string;
};

/**
 * The stream died: fetch rejected, the body reader threw mid-stream, or
 * the server emitted an `event: error` frame (transport-level failure).
 */
export type SSEStreamDrop = {
  readonly __kind: "sse_stream_drop";
  readonly message: string;
};

export type FetchSSEYield =
  | import("../wire/ag_ui_events").AGUIEvent
  | SSEParseError
  | SSEHttpError
  | SSEStreamDrop;

export function isSSEHttpError(v: FetchSSEYield): v is SSEHttpError {
  return (v as SSEHttpError).__kind === "sse_http_error";
}
export function isSSEStreamDrop(v: FetchSSEYield): v is SSEStreamDrop {
  return (v as SSEStreamDrop).__kind === "sse_stream_drop";
}
/** Parse-error guard typed for this transport's yield union. */
export function isFetchSSEParseError(v: FetchSSEYield): v is SSEParseError {
  return (v as SSEParseError).__kind === "sse_parse_error";
}

export interface ConnectFetchSSEOptions {
  readonly url: string;
  /** JSON-serialized as the POST body (the AG-UI run-create request). */
  readonly body: unknown;
  readonly fetchImpl: typeof fetch;
  /** Defaults to "include" -- the BFF authenticates via session cookie. */
  readonly credentials?: RequestCredentials;
  readonly headers?: Record<string, string>;
  readonly signal?: AbortSignal;
}

interface ParsedFrame {
  readonly eventName: string;
  readonly dataStr: string | null;
}

function parseFrame(rawFrame: string): ParsedFrame {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of rawFrame.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  return {
    eventName,
    dataStr: dataLines.length > 0 ? dataLines.join("\n") : null,
  };
}

function* yieldFrame(rawFrame: string): Generator<FetchSSEYield, void, void> {
  const { eventName, dataStr } = parseFrame(rawFrame);
  if (dataStr === null) return;
  // Terminal sentinel from agent_ui_adapter/transport/sse.py SENTINEL_LINE.
  if (eventName === "done" || dataStr === "[DONE]") return;
  if (eventName === "error") {
    // Server-side stream failure (encode_error): {message, code} payload.
    let message = dataStr;
    try {
      const payload = JSON.parse(dataStr) as { message?: unknown };
      if (typeof payload.message === "string") message = payload.message;
    } catch {
      /* keep the raw data as the message */
    }
    yield { __kind: "sse_stream_drop", message };
    return;
  }
  try {
    yield AGUIEventSchema.parse(JSON.parse(dataStr));
  } catch (e) {
    yield {
      __kind: "sse_parse_error",
      message: e instanceof Error ? e.message : String(e),
    };
  }
}

/**
 * POST `opts.body` to `opts.url` and parse the response body as an SSE
 * stream, yielding one `AGUIEvent` (or error sentinel) per frame. Reads
 * to EOF; no resumption (see module header).
 */
export async function* connectFetchSSE(
  opts: ConnectFetchSSEOptions,
): AsyncGenerator<FetchSSEYield, void, void> {
  let res: Response;
  try {
    const init: RequestInit = {
      method: "POST",
      credentials: opts.credentials ?? "include",
      headers: {
        "content-type": "application/json",
        accept: "text/event-stream",
        ...opts.headers,
      },
      body: JSON.stringify(opts.body),
    };
    if (opts.signal) init.signal = opts.signal;
    res = await opts.fetchImpl(opts.url, init);
  } catch (e) {
    yield {
      __kind: "sse_stream_drop",
      message: e instanceof Error ? e.message : String(e),
    };
    return;
  }

  if (!res.ok) {
    let message: string;
    try {
      message = await res.text();
    } catch {
      message = res.statusText;
    }
    yield { __kind: "sse_http_error", status: res.status, message };
    return;
  }
  if (!res.body) {
    yield { __kind: "sse_stream_drop", message: "response had no body" };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sepIdx: number;
      while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
        const rawFrame = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        if (rawFrame.trim().length > 0) yield* yieldFrame(rawFrame);
      }
    }
    if (buffer.trim().length > 0) yield* yieldFrame(buffer);
  } catch (e) {
    yield {
      __kind: "sse_stream_drop",
      message: e instanceof Error ? e.message : String(e),
    };
  }
}
