/**
 * useAgentRun -- the chat shell's seam onto the AgentRuntimeClient port
 * (eval-UI F1, plan §3-F1).
 *
 * Per F-R1 the component owns NO run-lifecycle logic: this hook drives
 * `streamRun(req)` and folds every UIRuntimeEvent through the pure
 * `run_view_reducer`; the shell renders the resulting turns as props.
 *
 * `consumeRunStream` is exported separately so the consumption loop is
 * testable in node without React: it streams events into a dispatch
 * callback and guarantees a terminal view even if iteration throws.
 *
 * The turn `id` is a local React list key only -- never sent anywhere,
 * never a trace_id (F-R7: trace ids arrive from the backend via
 * `run_started`).
 */

"use client";

import * as React from "react";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import { uiInputToAgentRequest } from "@/lib/translators/ui_input_to_agent_request";
import {
  emptyRunView,
  reduceRunView,
  type AssistantRunView,
} from "@/lib/translators/run_view_reducer";
import type { UIRuntimeEvent } from "@/lib/wire/ui_runtime_events";

export interface ChatTurn {
  readonly id: string;
  readonly user: string;
  readonly assistant: AssistantRunView;
}

/**
 * Drive one run to completion, dispatching every event. If the stream
 * iterable itself throws (a port-contract violation -- Runtime Contract §1
 * says failures arrive as run_error events), a synthetic terminal
 * run_error is dispatched so the view never hangs in `streaming`.
 */
export async function consumeRunStream(
  stream: AsyncIterable<UIRuntimeEvent>,
  dispatch: (evt: UIRuntimeEvent) => void,
): Promise<void> {
  try {
    for await (const evt of stream) {
      dispatch(evt);
    }
  } catch (e) {
    dispatch({
      type: "run_error",
      trace_id: "no-trace",
      run_id: "",
      error_type: "network_error",
      message: e instanceof Error ? e.message : String(e),
    });
  }
}

export function useAgentRun(runtime: AgentRuntimeClient): {
  turns: ReadonlyArray<ChatTurn>;
  busy: boolean;
  send: (body: string) => Promise<void>;
} {
  const [turns, setTurns] = React.useState<ReadonlyArray<ChatTurn>>([]);
  const [busy, setBusy] = React.useState(false);
  /** Stable LangGraph thread id for checkpointer multiturn continuity. */
  const threadIdRef = React.useRef<string | null>(null);

  const send = React.useCallback(
    async (body: string): Promise<void> => {
      threadIdRef.current ??= crypto.randomUUID();
      const turnId = crypto.randomUUID();
      setTurns((prev) => [
        ...prev,
        { id: turnId, user: body, assistant: emptyRunView() },
      ]);
      setBusy(true);
      const dispatch = (evt: UIRuntimeEvent): void => {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === turnId
              ? { ...t, assistant: reduceRunView(t.assistant, evt) }
              : t,
          ),
        );
      };
      try {
        // Only the new user line: the middleware keys checkpoint state by
        // `thread_id`, so LangGraph appends to prior turns server-side.
        const req = uiInputToAgentRequest({
          thread_id: threadIdRef.current,
          body,
        });
        await consumeRunStream(runtime.streamRun(req), dispatch);
      } catch (e) {
        // streamRun threw synchronously (e.g. missing composition wiring).
        dispatch({
          type: "run_error",
          trace_id: "no-trace",
          run_id: "",
          error_type: "network_error",
          message: e instanceof Error ? e.message : String(e),
        });
      } finally {
        setBusy(false);
      }
    },
    [runtime],
  );

  return { turns, busy, send };
}
