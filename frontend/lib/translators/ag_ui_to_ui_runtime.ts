/**
 * Pure translator: AG-UI native event -> UIRuntime event(s).
 *
 * Per FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE:
 *   - T1 pure (no I/O, no SDK, no React)
 *   - T2 trace_id forwarded from input to every output
 *   - T3 zero-or-many output (some AG-UI events have no UI counterpart)
 *
 * If `raw_event.trace_id` is missing the translator throws -- per plan
 * §4.3 Option B, an event without a `trace_id` is malformed and the SSE
 * client is responsible for synthesizing a `RunErrorEvent` rather than
 * letting it reach this translator.
 *
 * Imports: only `wire/`. No transport, no adapter, no SDK.
 */

import type { AGUIEvent } from "../wire/ag_ui_events";
import type { UIRuntimeEvent } from "../wire/ui_runtime_events";

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

export function agUiToUiRuntime(evt: AGUIEvent): ReadonlyArray<UIRuntimeEvent> {
  const trace_id = traceOf(evt);

  switch (evt.type) {
    case "RUN_STARTED":
      return [
        {
          type: "run_started",
          trace_id,
          run_id: evt.run_id,
          thread_id: evt.thread_id,
        },
      ];

    case "RUN_FINISHED":
      return [
        {
          type: "run_completed",
          trace_id,
          run_id: evt.run_id,
          thread_id: evt.thread_id,
        },
      ];

    case "RUN_ERROR":
      return [
        {
          type: "run_error",
          trace_id,
          run_id: evt.run_id,
          error_type: "server_error",
          message: evt.message,
        },
      ];

    case "STEP_STARTED":
      return [
        {
          type: "step_progress",
          trace_id,
          step: 0,
          step_name: evt.step_name,
        },
      ];

    case "STEP_FINISHED":
      // STEP_FINISHED is absorbed: the next STEP_STARTED supersedes it
      // visually. Emit nothing per T3 zero-or-many.
      return [];

    case "TEXT_MESSAGE_START":
    case "TEXT_MESSAGE_END":
      // Lifecycle envelopes -- the UI cares only about deltas.
      return [];

    case "TEXT_MESSAGE_CONTENT":
      return [
        {
          type: "chat_message_delta",
          trace_id,
          message_id: evt.message_id,
          delta: evt.delta,
        },
      ];

    case "TOOL_CALL_START":
    case "TOOL_CALL_ARGS":
    case "TOOL_CALL_END":
    case "TOOL_RESULT":
      // Tool events flow through the dedicated `tool_event_to_renderer_request`
      // aggregator -- it owns the call-id-keyed reduction. The plain
      // AG-UI -> UIRuntime channel ignores them.
      return [];

    case "STATE_SNAPSHOT":
      return [
        {
          type: "state_render",
          trace_id,
          key: "snapshot",
          value: evt.snapshot,
        },
      ];

    case "STATE_DELTA":
      return [
        {
          type: "state_render",
          trace_id,
          key: "delta",
          value: evt.delta,
        },
      ];

    case "MESSAGES_SNAPSHOT":
      return [
        {
          type: "state_render",
          trace_id,
          key: "messages",
          value: evt.messages,
        },
      ];

    case "RAW":
      // Debug-only payload, never reaches the UI.
      return [];

    case "CUSTOM": {
      if (evt.name === "step_meter") {
        const v = evt.value as { step?: unknown; step_name?: unknown };
        const step = typeof v.step === "number" ? v.step : 0;
        const step_name = typeof v.step_name === "string" ? v.step_name : "";
        return [
          {
            type: "step_progress",
            trace_id,
            step,
            step_name,
          },
        ];
      }
      // Any other custom event is exposed via state_render with key=name.
      return [
        {
          type: "state_render",
          trace_id,
          key: evt.name,
          value: evt.value,
        },
      ];
    }
  }
}
