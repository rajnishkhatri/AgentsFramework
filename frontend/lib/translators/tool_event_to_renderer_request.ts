/**
 * Pure aggregator: AG-UI tool events -> ToolCallRendererRequest list.
 *
 * The reducer pattern keeps the translator pure (T1):
 *   reduce: (state, event) -> state'
 *
 * Each invocation returns a NEW state object; the caller's prior state is
 * never mutated. This makes it trivially testable and friendly to React's
 * `useReducer` / `useSyncExternalStore`.
 *
 * trace_id propagates onto every renderer request (T2 / F-R7).
 *
 * Imports: only `wire/`. No SDK, no React.
 */

import type { AGUIEvent } from "../wire/ag_ui_events";
import type { ToolCallRendererRequest } from "../wire/ui_runtime_events";

export type ToolAggregatorState = {
  readonly renderers: ReadonlyArray<ToolCallRendererRequest>;
  // Per-call buffered args delta (assembled across TOOL_CALL_ARGS events).
  readonly _argsBuffer: Readonly<Record<string, string>>;
};

export function emptyToolAggregatorState(): ToolAggregatorState {
  return Object.freeze({
    renderers: Object.freeze([]),
    _argsBuffer: Object.freeze({}),
  });
}

function traceOf(evt: AGUIEvent): string {
  const t = evt.raw_event?.trace_id;
  if (typeof t !== "string" || t.length === 0) {
    throw new Error(
      "AG-UI event is missing raw_event.trace_id; the SSE client must " +
        "synthesize a RunErrorEvent before this translator is invoked.",
    );
  }
  return t;
}

function replaceById(
  renderers: ReadonlyArray<ToolCallRendererRequest>,
  id: string,
  patch: Partial<ToolCallRendererRequest>,
): ReadonlyArray<ToolCallRendererRequest> {
  return renderers.map((r) => (r.tool_call_id === id ? { ...r, ...patch } : r));
}

export function reduceToolEvent(
  state: ToolAggregatorState,
  evt: AGUIEvent,
): ToolAggregatorState {
  // Ignore non-tool events to keep the call site terse (T3 zero output).
  if (
    evt.type !== "TOOL_CALL_START" &&
    evt.type !== "TOOL_CALL_ARGS" &&
    evt.type !== "TOOL_CALL_END" &&
    evt.type !== "TOOL_RESULT"
  ) {
    return state;
  }

  const trace_id = traceOf(evt);

  if (evt.type === "TOOL_CALL_START") {
    const renderer: ToolCallRendererRequest = {
      trace_id,
      tool_call_id: evt.tool_call_id,
      tool_name: evt.tool_call_name,
      input: {},
      status: "running",
      output: null,
    };
    return Object.freeze({
      renderers: [...state.renderers, renderer],
      _argsBuffer: { ...state._argsBuffer, [evt.tool_call_id]: "" },
    });
  }

  if (evt.type === "TOOL_CALL_ARGS") {
    const prevBuf = state._argsBuffer[evt.tool_call_id] ?? "";
    const buf = prevBuf + evt.delta;
    let parsedInput: Record<string, unknown> | undefined;
    try {
      const v = JSON.parse(buf);
      if (v && typeof v === "object" && !Array.isArray(v)) {
        parsedInput = v as Record<string, unknown>;
      }
    } catch {
      // Args delta is partial / not yet valid JSON -- keep buffering.
    }
    const renderers = parsedInput
      ? replaceById(state.renderers, evt.tool_call_id, { input: parsedInput })
      : state.renderers;
    return Object.freeze({
      renderers,
      _argsBuffer: { ...state._argsBuffer, [evt.tool_call_id]: buf },
    });
  }

  if (evt.type === "TOOL_CALL_END") {
    // The CALL_END envelope is informational; status flips to 'completed'
    // only when TOOL_RESULT arrives.
    return state;
  }

  // TOOL_RESULT
  const renderers = replaceById(state.renderers, evt.tool_call_id, {
    status: "completed",
    output: evt.content,
  });
  return Object.freeze({
    renderers,
    _argsBuffer: state._argsBuffer,
  });
}
