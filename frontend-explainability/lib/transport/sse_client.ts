/**
 * Tiny client-side SSE wrapper around the browser `EventSource` (S4.3.3).
 *
 * Rule X1 (mirror of the agent_ui_adapter rule): `EventSource` is allowed
 * ONLY here -- never in components, ports, adapters, or translators.
 *
 * Rule X2 spirit: a parse failure on an inbound `event: log` frame is
 * surfaced via the `onError` callback so the route can render a toast or
 * fall back to the polled `/api/v1/logs` view.
 *
 * Rule X5 (back-pressure): the caller is responsible for capping the line
 * buffer.  This module only routes events; it does not buffer.
 *
 * @sdk EventSource (built-in)  — the only file in lib/ allowed to construct one.
 */
import { LogRowSchema, type LogRow } from "@/lib/wire/responses";

export interface LogStreamHandle {
  /** Closes the underlying connection.  Safe to call multiple times. */
  close(): void;
}

export interface OpenLogStreamOptions {
  baseUrl: string;
  concerns?: readonly string[] | undefined;
  level?: string | null | undefined;
  search?: string | null | undefined;
  onLog: (row: LogRow) => void;
  onError?: ((message: string) => void) | undefined;
}

/**
 * Open an EventSource against `/api/v1/logs/stream` and forward `event: log`
 * frames to the supplied callback.  Returns a handle whose `close()` ends
 * the connection -- the SSE handler on the server detects the disconnect
 * and stops `tail_logs` cleanly.
 */
export function openLogStream(opts: OpenLogStreamOptions): LogStreamHandle {
  const url = new URL(`${opts.baseUrl}/api/v1/logs/stream`);
  if (opts.concerns !== undefined) {
    for (const concern of opts.concerns) {
      url.searchParams.append("concerns", concern);
    }
  }
  if (opts.level) url.searchParams.set("level", opts.level);
  if (opts.search) url.searchParams.set("search", opts.search);

  const source = new EventSource(url.toString());

  source.addEventListener("log", (event) => {
    const data = (event as MessageEvent).data;
    let raw: unknown;
    try {
      raw = JSON.parse(data);
    } catch (cause) {
      opts.onError?.(
        cause instanceof Error
          ? `Bad SSE log frame: ${cause.message}`
          : "Bad SSE log frame",
      );
      return;
    }
    const result = LogRowSchema.safeParse(raw);
    if (!result.success) {
      opts.onError?.(`SSE log frame failed Zod parse: ${result.error.message}`);
      return;
    }
    opts.onLog(result.data);
  });

  source.addEventListener("error", (event) => {
    const data = (event as MessageEvent | undefined)?.data;
    if (typeof data === "string") {
      opts.onError?.(data);
    } else {
      opts.onError?.("SSE connection error");
    }
  });

  return {
    close() {
      source.close();
    },
  };
}
