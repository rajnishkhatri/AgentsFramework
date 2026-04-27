/**
 * SSE client (S3.5.1) -- Last-Event-ID resumption, heartbeat detection,
 * backpressure (drop-oldest 100-event buffer), and Zod-parse on receive.
 *
 * Per X1: `EventSource` is used in this file ONLY. Per X2: every inbound
 * frame is Zod-parsed; failures emit a transport-local `SSEParseError`
 * sentinel rather than throwing into the consumer. The adapter consuming
 * `connectSSE` is responsible for translating the sentinel into a
 * `RunErrorEvent { error_type: "wire_parse_error" }` -- transport CANNOT
 * import translators (architecture test S3.10.1).
 *
 * Imports: `wire/` only. No translators, no adapters, no SDK.
 */

import { AGUIEventSchema, type AGUIEvent } from "../wire/ag_ui_events";

export interface SSEMessage {
  data: string;
  lastEventId: string;
}

export type EventSourceFactory = (
  url: string,
  init?: { withCredentials?: boolean; headers?: Record<string, string> },
) => EventSource;

/**
 * Transport-local error sentinel. The adapter (SelfHostedLangGraphDevClient)
 * narrows this to a `RunErrorEvent` UIRuntime event so the React tree sees
 * a structured failure rather than a raw exception.
 */
export type SSEParseError = {
  readonly __kind: "sse_parse_error";
  readonly message: string;
};

export type SSEHeartbeatTimeout = {
  readonly __kind: "sse_heartbeat_timeout";
  readonly message: string;
};

export type SSEYield = AGUIEvent | SSEParseError | SSEHeartbeatTimeout;

export function isSSEParseError(v: SSEYield): v is SSEParseError {
  return (v as SSEParseError).__kind === "sse_parse_error";
}
export function isSSEHeartbeatTimeout(v: SSEYield): v is SSEHeartbeatTimeout {
  return (v as SSEHeartbeatTimeout).__kind === "sse_heartbeat_timeout";
}

export interface ConnectSSEOptions {
  readonly url: string;
  readonly runId: string;
  readonly eventSourceFactory: EventSourceFactory;
  /**
   * Client-side heartbeat *detect* timeout (default 30 000 ms).
   *
   * Per Rule X4 the contract is "15 s send / 30 s detect": the Python
   * server in `agent_ui_adapter/transport/heartbeat.py` emits a `: ping`
   * comment every `DEFAULT_INTERVAL_SECONDS = 15.0`, so a 30 s client
   * detect window gives exactly one missed-heartbeat margin before the
   * connection is declared dead. The 15 s send threshold is server-side
   * and has no client implementation; the only client knob is *detect*.
   */
  readonly heartbeatTimeoutMs?: number;
  readonly bufferSize?: number; // default 100, drop-oldest (X5)
  readonly reconnectDelayMs?: number; // default 1_000
}

/**
 * Client *detect* threshold for the X4 heartbeat contract. Server *send*
 * cadence is 15 s (`agent_ui_adapter/transport/heartbeat.py
 * DEFAULT_INTERVAL_SECONDS`); we tolerate exactly one missed heartbeat.
 */
const DEFAULT_HEARTBEAT_MS = 30_000;
const DEFAULT_BUFFER = 100;
const DEFAULT_RECONNECT_DELAY = 1_000;

/**
 * Open an SSE stream against `url`, parsing each frame into one
 * `AGUIEvent`, a parse-error sentinel, or a heartbeat-timeout sentinel.
 * The async iterable terminates when the consumer breaks out OR a heartbeat
 * timeout sentinel is yielded (callers may break early on RUN_FINISHED /
 * RUN_ERROR).
 */
export async function* connectSSE(
  opts: ConnectSSEOptions,
): AsyncGenerator<SSEYield, void, void> {
  const heartbeatMs = opts.heartbeatTimeoutMs ?? DEFAULT_HEARTBEAT_MS;
  const bufferSize = opts.bufferSize ?? DEFAULT_BUFFER;
  const reconnectMs = opts.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY;

  const buffer: SSEYield[] = [];
  let waiter: ((v: void) => void) | null = null;
  let lastEventId = "";
  let terminated = false;

  function push(evt: SSEYield): void {
    if (buffer.length >= bufferSize) buffer.shift();
    buffer.push(evt);
    if (waiter) {
      const w = waiter;
      waiter = null;
      w();
    }
  }

  function attach(): EventSource {
    const headers: Record<string, string> = {};
    if (lastEventId) headers["Last-Event-ID"] = lastEventId;
    const es = opts.eventSourceFactory(opts.url, { headers });

    let hbTimer: ReturnType<typeof setTimeout> | null = null;
    function resetHeartbeat(): void {
      if (hbTimer) clearTimeout(hbTimer);
      hbTimer = setTimeout(() => {
        push({
          __kind: "sse_heartbeat_timeout",
          message: `No SSE event received for ${heartbeatMs}ms.`,
        });
        terminated = true;
        try {
          es.close();
        } catch {
          /* swallow */
        }
      }, heartbeatMs);
    }

    es.addEventListener("open", () => resetHeartbeat());
    es.addEventListener("message", (raw: MessageEvent) => {
      resetHeartbeat();
      if (raw.lastEventId) lastEventId = raw.lastEventId;
      try {
        const parsed = AGUIEventSchema.parse(JSON.parse(raw.data as string));
        push(parsed);
      } catch (e) {
        push({
          __kind: "sse_parse_error",
          message: e instanceof Error ? e.message : String(e),
        });
      }
    });
    es.addEventListener("error", () => {
      if (hbTimer) clearTimeout(hbTimer);
      try {
        es.close();
      } catch {
        /* swallow */
      }
      if (!terminated) {
        setTimeout(() => attach(), reconnectMs);
      }
    });
    return es;
  }

  attach();

  while (!terminated || buffer.length > 0) {
    if (buffer.length === 0) {
      await new Promise<void>((r) => {
        waiter = r;
      });
      continue;
    }
    yield buffer.shift()!;
  }
}
