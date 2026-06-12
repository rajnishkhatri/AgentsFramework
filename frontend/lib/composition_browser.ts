/**
 * Browser composition root (eval-UI F1, plan §8.6-E Option A).
 *
 * The browser-side sibling of `composition.ts` (server PortBag) and
 * `bff/server_composition.ts` (BFF). Like them it may name concrete
 * adapters and assemble `transport/` + `translators/` -- the layering
 * test (`tests/architecture/test_frontend_layering.test.ts`) lists this
 * file in the composition ring.
 *
 * Kept separate from `composition.ts` deliberately: that file constructs
 * the WorkOS auth adapter (server-only SDK), which must never enter the
 * client bundle. The browser slice needs exactly one port:
 * `AgentRuntimeClient`, streaming over `fetch`+`ReadableStream` so
 * Playwright `page.route` T1 mocks keep intercepting (§8.6-E).
 *
 * Stream assembly contract (Runtime Contract §1): the yielded stream
 * ALWAYS ends with `run_completed` or `run_error`. Transport sentinels and
 * EOF-without-terminal are translated into `run_error` here. The
 * `"no-trace"` trace_id on synthesized errors is a documented sentinel,
 * NOT a browser-generated trace (FE-AP-7): there is no real trace to
 * forward when the failure precedes/loses the stream.
 */

import { SelfHostedLangGraphDevClient } from "./adapters/runtime/self_hosted_langgraph_dev_client";
import {
  connectFetchSSE,
  isFetchSSEParseError,
  isSSEHttpError,
  isSSEStreamDrop,
} from "./transport/fetch_sse_client";
import { agUiToUiRuntime } from "./translators/ag_ui_to_ui_runtime";
import {
  emptyToolAggregatorState,
  reduceToolEvent,
} from "./translators/tool_event_to_renderer_request";
import type { RunCreateRequest } from "./wire/agent_protocol";
import type { RunErrorType, UIRuntimeEvent } from "./wire/ui_runtime_events";
import type {
  AgentRuntimeClient,
  StreamRunOptions,
} from "./ports/agent_runtime_client";

function statusToErrorType(status: number): RunErrorType {
  if (status === 401) return "auth_error";
  if (status === 403) return "authorization_error";
  if (status === 429) return "rate_limit_error";
  if (status >= 500) return "server_error";
  return "network_error";
}

const TOOL_EVENT_TYPES = new Set([
  "TOOL_CALL_START",
  "TOOL_CALL_ARGS",
  "TOOL_CALL_END",
  "TOOL_RESULT",
]);

/**
 * Assemble transport + translators into the `(req) => UIRuntimeEvent
 * stream` factory injected into the runtime adapter (Rule A3: the adapter
 * itself imports neither).
 */
export function makeFetchUIRuntimeStream(
  baseUrl: string,
  fetchImpl: typeof fetch,
): (
  req: RunCreateRequest,
  opts?: StreamRunOptions,
) => AsyncIterable<UIRuntimeEvent> {
  const base = baseUrl.replace(/\/$/, "");
  return async function* openUIRuntimeStream(
    req: RunCreateRequest,
    opts?: StreamRunOptions,
  ): AsyncGenerator<UIRuntimeEvent, void, void> {
    let traceId = "no-trace";
    let runId = "";
    let terminalSeen = false;
    let toolState = emptyToolAggregatorState();

    function runError(errorType: RunErrorType, message: string): UIRuntimeEvent {
      return {
        type: "run_error",
        trace_id: traceId,
        run_id: runId,
        error_type: errorType,
        message,
      };
    }

    const stream = connectFetchSSE({
      url: `${base}/run/stream`,
      body: req,
      fetchImpl,
      ...(opts?.signal ? { signal: opts.signal } : {}),
    });

    for await (const yielded of stream) {
      if (isFetchSSEParseError(yielded)) {
        yield runError("wire_parse_error", yielded.message);
        return;
      }
      if (isSSEHttpError(yielded)) {
        yield runError(statusToErrorType(yielded.status), yielded.message);
        return;
      }
      if (isSSEStreamDrop(yielded)) {
        if (terminalSeen) return; // stream already concluded; drop is moot
        yield runError("network_error", yielded.message);
        return;
      }

      if (TOOL_EVENT_TYPES.has(yielded.type)) {
        let touchedId: string;
        try {
          toolState = reduceToolEvent(toolState, yielded);
          touchedId = (yielded as { tool_call_id: string }).tool_call_id;
        } catch (e) {
          yield runError(
            "wire_parse_error",
            e instanceof Error ? e.message : String(e),
          );
          return;
        }
        const renderer = toolState.renderers.find(
          (r) => r.tool_call_id === touchedId,
        );
        if (renderer) {
          yield { type: "tool_render", trace_id: renderer.trace_id, request: renderer };
        }
        continue;
      }

      try {
        for (const ui of agUiToUiRuntime(yielded)) {
          if (ui.type === "run_started") {
            traceId = ui.trace_id;
            runId = ui.run_id;
          }
          if (ui.type === "run_completed" || ui.type === "run_error") {
            terminalSeen = true;
          }
          yield ui;
        }
      } catch (e) {
        yield runError(
          "wire_parse_error",
          e instanceof Error ? e.message : String(e),
        );
        return;
      }
    }

    if (!terminalSeen) {
      yield runError(
        "network_error",
        "stream ended without a terminal event (Runtime Contract §1)",
      );
    }
  };
}

export interface BuildBrowserRuntimeClientOptions {
  readonly baseUrl?: string;
  readonly fetchImpl?: typeof fetch;
}

export function buildBrowserRuntimeClient(
  opts: BuildBrowserRuntimeClientOptions = {},
): AgentRuntimeClient {
  const baseUrl = (opts.baseUrl ?? "/api").replace(/\/$/, "");
  const fetchImpl =
    opts.fetchImpl ??
    (((...args: Parameters<typeof fetch>) => fetch(...args)) as typeof fetch);
  return new SelfHostedLangGraphDevClient({
    baseUrl,
    fetchImpl,
    openUIRuntimeStream: makeFetchUIRuntimeStream(baseUrl, fetchImpl),
  });
}

let singleton: AgentRuntimeClient | null = null;

/** Lazy app-wide runtime client for client components. */
export function browserRuntimeClient(): AgentRuntimeClient {
  singleton ??= buildBrowserRuntimeClient();
  return singleton;
}
