/**
 * Pure reducer: UIRuntimeEvent stream -> per-assistant-message view state
 * (eval-UI F1, plan §3-F1).
 *
 * This is the F-R1 seam: run-lifecycle logic lives HERE (a pure translator
 * over `ui_runtime_events`), never in components. The React layer feeds
 * each streamed event through `reduceRunView` and renders the resulting
 * view as props.
 *
 *   reduce: (view, event) -> view'   -- prior view never mutated (T1).
 *
 * Invariants:
 * - `traceId` is captured from forwarded events only, never generated
 *   browser-side (F-R7 / FE-AP-7).
 * - Segments append in trajectory order so the render mirrors the real
 *   ReAct loop; a `tool_render` update for a known tool_call_id replaces
 *   that segment in place (one card per call).
 * - After a terminal event (`run_completed`/`run_error`) the view is
 *   frozen: late events are ignored so eval captures stay stable.
 * - `state_render` feeds the F9 todo checklist via
 *   `todo_list_projection`; payloads without a usable `/todos` shape are
 *   tolerated unchanged.
 *
 * Imports: `wire/` + sibling translators. No SDK, no React.
 */

import type {
  ToolCallRendererRequest,
  UIRuntimeEvent,
} from "../wire/ui_runtime_events";
import { projectTodoList, type TodoListView } from "./todo_list_projection";

export type MessageSegment =
  | { readonly kind: "text"; readonly text: string }
  | { readonly kind: "tool"; readonly request: ToolCallRendererRequest };

export type RunViewStatus = "streaming" | "complete" | "error";

export interface AssistantRunView {
  readonly status: RunViewStatus;
  readonly segments: ReadonlyArray<MessageSegment>;
  readonly step: { readonly count: number; readonly name: string } | null;
  readonly todos: TodoListView | null;
  readonly traceId: string | null;
  readonly runId: string | null;
  readonly threadId: string | null;
  readonly errorMessage: string | null;
}

export function emptyRunView(): AssistantRunView {
  return Object.freeze({
    status: "streaming" as const,
    segments: Object.freeze([]),
    step: null,
    todos: null,
    traceId: null,
    runId: null,
    threadId: null,
    errorMessage: null,
  });
}

function appendText(
  segments: ReadonlyArray<MessageSegment>,
  delta: string,
): ReadonlyArray<MessageSegment> {
  const last = segments[segments.length - 1];
  if (last && last.kind === "text") {
    return [...segments.slice(0, -1), { kind: "text", text: last.text + delta }];
  }
  return [...segments, { kind: "text", text: delta }];
}

function upsertTool(
  segments: ReadonlyArray<MessageSegment>,
  request: ToolCallRendererRequest,
): ReadonlyArray<MessageSegment> {
  const idx = segments.findIndex(
    (s) => s.kind === "tool" && s.request.tool_call_id === request.tool_call_id,
  );
  if (idx === -1) return [...segments, { kind: "tool", request }];
  const next = [...segments];
  next[idx] = { kind: "tool", request };
  return next;
}

export function reduceRunView(
  view: AssistantRunView,
  evt: UIRuntimeEvent,
): AssistantRunView {
  // Terminal views are frozen -- late events never reshape captured evidence.
  if (view.status !== "streaming") return view;

  switch (evt.type) {
    case "run_started":
      return {
        ...view,
        traceId: evt.trace_id,
        runId: evt.run_id,
        threadId: evt.thread_id,
      };

    case "chat_message_delta":
      return { ...view, segments: appendText(view.segments, evt.delta) };

    case "tool_render":
      return {
        ...view,
        traceId: view.traceId ?? evt.trace_id,
        segments: upsertTool(view.segments, evt.request),
      };

    case "step_progress":
      return { ...view, step: { count: evt.step, name: evt.step_name } };

    case "run_completed":
      return { ...view, status: "complete" };

    case "run_error":
      return { ...view, status: "error", errorMessage: evt.message };

    case "state_render": {
      const todos = projectTodoList(view.todos, evt);
      return todos === view.todos ? view : { ...view, todos };
    }
  }
}
