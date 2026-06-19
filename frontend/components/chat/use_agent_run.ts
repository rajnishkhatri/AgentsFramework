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
 * Phase 4 soft-gate edit round trip (task_understanding plan §4.6):
 * `pauseForEdit` aborts the in-flight stream (the checkpoint survives
 * server-side), `saveUnderstanding` POSTs the edited artifact through the
 * port and resumes the SAME turn with `input: {_resume: true}` --
 * `performUnderstandingEdit` is the React-free orchestration of that
 * sequence. While paused, the dispatch swallows the abort-induced
 * `run_error` so the view stays `streaming` (the reducer would otherwise
 * freeze the turn).
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

/** The card's editable fields; trace_id/thread_id are supplied by the hook. */
export interface UnderstandingEditPayload {
  readonly restated_intent: string;
  readonly success_conditions: ReadonlyArray<string>;
}

/**
 * Durable-persistence seam (plan §A3). The hook owns the run lifecycle and
 * thread id; it does NOT fetch — these callbacks delegate the BFF writes to
 * `useChatSidebars` (F-R2: the fetch stays in the adapter-backed hook, F-R9:
 * same-origin cookie auth). Both are fire-and-forget — the implementation must
 * never throw into the run (a persistence miss must not break the live chat).
 */
export interface PersistHooks {
  /** Called once, on the first send of a new chat, with the just-minted id. */
  onFirstSend?: (threadId: string, firstMessage: string) => void;
  /** Called after a run completes, with the final assistant text. */
  onTurnComplete?: (
    threadId: string,
    turn: { user: string; assistant: string; turnId: string },
  ) => void;
}

/** Flatten an assistant view's text segments into one plain string. */
function assistantText(view: AssistantRunView): string {
  return view.segments
    .map((s) => (s.kind === "text" ? s.text : ""))
    .join("");
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

/**
 * React-free Phase 4 edit-and-resume sequence: POST the edited artifact,
 * then continue the paused thread by re-invoking the stream with the
 * `_resume` sentinel (the runtime recovers the trace from the checkpoint;
 * the browser sends no trace on the resume leg -- F-R7).
 *
 * The POST happens BEFORE the resume so the judge can only ever see the
 * edited conditions. If the POST rejects, the thread stays paused and the
 * error propagates to the caller (the card surfaces it; resume is not
 * attempted against an unedited artifact the user believes is corrected).
 */
export async function performUnderstandingEdit(opts: {
  runtime: AgentRuntimeClient;
  threadId: string;
  traceId: string;
  edit: UnderstandingEditPayload;
  dispatch: (evt: UIRuntimeEvent) => void;
  /** Called after the POST is accepted, before the resume stream opens
   *  (the hook clears its paused state here so resume events flow). */
  onEditAccepted?: () => void;
  signal?: AbortSignal;
}): Promise<void> {
  await opts.runtime.updateUnderstanding(opts.threadId, {
    trace_id: opts.traceId,
    restated_intent: opts.edit.restated_intent,
    success_conditions: [...opts.edit.success_conditions],
  });
  opts.onEditAccepted?.();
  await resumeRunStream(opts);
}

/** Continue a paused thread without an edit (the cancel-edit path). */
export async function resumeRunStream(opts: {
  runtime: AgentRuntimeClient;
  threadId: string;
  dispatch: (evt: UIRuntimeEvent) => void;
  signal?: AbortSignal;
}): Promise<void> {
  await consumeRunStream(
    opts.runtime.streamRun(
      { thread_id: opts.threadId, input: { _resume: true } },
      opts.signal ? { signal: opts.signal } : undefined,
    ),
    opts.dispatch,
  );
}

export function useAgentRun(
  runtime: AgentRuntimeClient,
  persist?: PersistHooks,
): {
  turns: ReadonlyArray<ChatTurn>;
  busy: boolean;
  send: (body: string) => Promise<void>;
  /** Turn currently paused for a card edit, or null. */
  pausedTurnId: string | null;
  /** Last edit-POST failure (the card renders it); cleared on retry/cancel. */
  editError: string | null;
  pauseForEdit: (turnId: string) => void;
  saveUnderstanding: (
    turnId: string,
    edit: UnderstandingEditPayload,
  ) => Promise<void>;
  cancelEditAndResume: (turnId: string) => Promise<void>;
  /**
   * Click-to-resume a past thread: replace the displayed turns with that
   * thread's replayed history and bind the hook's thread id to it, so the
   * next `send` continues that LangGraph checkpoint server-side.
   */
  resumeThread: (
    threadId: string,
    replayTurns: ReadonlyArray<ChatTurn>,
  ) => void;
  /**
   * Start a fresh conversation: abort any in-flight run, clear the transcript,
   * and drop the thread id so the NEXT `send` mints a new `crypto.randomUUID()`
   * (lazy creation — no BFF POST on click). UI refresh Phase 3 / plan §D3.
   */
  startNewChat: () => void;
} {
  const [turns, setTurns] = React.useState<ReadonlyArray<ChatTurn>>([]);
  const [busy, setBusy] = React.useState(false);
  const [pausedTurnId, setPausedTurnId] = React.useState<string | null>(null);
  const [editError, setEditError] = React.useState<string | null>(null);
  /** Stable LangGraph thread id for checkpointer multiturn continuity. */
  const threadIdRef = React.useRef<string | null>(null);
  /** Abort handle for the in-flight stream (pause = abort, F1 transport). */
  const controllerRef = React.useRef<AbortController | null>(null);
  /** True between pauseForEdit and the resume leg: swallow abort fallout. */
  const pausedRef = React.useRef(false);
  /** Render-time mirror so callbacks read current turns without re-binding. */
  const turnsRef = React.useRef<ReadonlyArray<ChatTurn>>(turns);
  turnsRef.current = turns;
  /** Latest persist hooks (identity may change per render; read via ref). */
  const persistRef = React.useRef<PersistHooks | undefined>(persist);
  persistRef.current = persist;

  const dispatchFor = React.useCallback(
    (turnId: string) =>
      (evt: UIRuntimeEvent): void => {
        // An intentional pause aborts the fetch; the transport surfaces
        // that as run_error. Swallow it so the view stays `streaming`
        // and the resume leg can fold into the same turn.
        if (pausedRef.current && evt.type === "run_error") return;
        setTurns((prev) =>
          prev.map((t) =>
            t.id === turnId
              ? { ...t, assistant: reduceRunView(t.assistant, evt) }
              : t,
          ),
        );
      },
    [],
  );

  const send = React.useCallback(
    async (body: string): Promise<void> => {
      // First send of a new chat: mint the id AND auto-create the durable row
      // (D1) so the conversation is saved from turn one. `isFirstSend` is true
      // only when the ref was null before this assignment.
      const isFirstSend = threadIdRef.current == null;
      threadIdRef.current ??= crypto.randomUUID();
      const threadId = threadIdRef.current;
      if (isFirstSend) persistRef.current?.onFirstSend?.(threadId, body);
      const turnId = crypto.randomUUID();
      setTurns((prev) => [
        ...prev,
        { id: turnId, user: body, assistant: emptyRunView() },
      ]);
      setBusy(true);
      // Track the latest reduced view for THIS turn synchronously alongside the
      // React state, so the completed answer is available the instant the
      // stream resolves (the render-mirror `turnsRef` lags a commit).
      let latestView = emptyRunView();
      const dispatch = (evt: UIRuntimeEvent): void => {
        if (pausedRef.current && evt.type === "run_error") return;
        latestView = reduceRunView(latestView, evt);
        dispatchFor(turnId)(evt);
      };
      const controller = new AbortController();
      controllerRef.current = controller;
      try {
        // Only the new user line: the middleware keys checkpoint state by
        // `thread_id`, so LangGraph appends to prior turns server-side.
        const req = uiInputToAgentRequest({
          thread_id: threadId,
          body,
        });
        await consumeRunStream(
          runtime.streamRun(req, { signal: controller.signal }),
          dispatch,
        );
        // Persist the completed turn (D2) — but never a turn that errored or
        // is paused mid-edit (a pause aborts the stream; the resume leg will
        // persist the final answer).
        if (latestView.status === "complete" && !pausedRef.current) {
          persistRef.current?.onTurnComplete?.(threadId, {
            user: body,
            assistant: assistantText(latestView),
            turnId,
          });
        }
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
        if (controllerRef.current === controller) controllerRef.current = null;
        setBusy(false);
      }
    },
    [runtime, dispatchFor],
  );

  const pauseForEdit = React.useCallback((turnId: string): void => {
    pausedRef.current = true;
    setPausedTurnId(turnId);
    setEditError(null);
    controllerRef.current?.abort();
  }, []);

  const resumeInto = React.useCallback(
    async (
      turnId: string,
      edit: UnderstandingEditPayload | null,
    ): Promise<void> => {
      const threadId = threadIdRef.current;
      if (!threadId) return;
      const dispatch = dispatchFor(turnId);
      const controller = new AbortController();
      controllerRef.current = controller;
      const clearPause = (): void => {
        pausedRef.current = false;
        setPausedTurnId(null);
        setEditError(null);
      };
      setBusy(true);
      try {
        if (edit) {
          const traceId = turnsRef.current.find((t) => t.id === turnId)
            ?.assistant.traceId;
          if (!traceId) {
            throw new Error("no trace_id on this turn yet; cannot edit");
          }
          // POST first; only an accepted edit clears the pause and resumes.
          await performUnderstandingEdit({
            runtime,
            threadId,
            traceId,
            edit,
            dispatch,
            onEditAccepted: clearPause,
            signal: controller.signal,
          });
        } else {
          clearPause();
          await resumeRunStream({
            runtime,
            threadId,
            dispatch,
            signal: controller.signal,
          });
        }
      } catch (e) {
        // Only the edit POST can throw (resume failures arrive as
        // run_error events). Stay paused; the user can retry or cancel.
        setEditError(e instanceof Error ? e.message : String(e));
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null;
        setBusy(false);
      }
    },
    [runtime, dispatchFor],
  );

  const saveUnderstanding = React.useCallback(
    async (turnId: string, edit: UnderstandingEditPayload): Promise<void> =>
      resumeInto(turnId, edit),
    [resumeInto],
  );

  const cancelEditAndResume = React.useCallback(
    async (turnId: string): Promise<void> => resumeInto(turnId, null),
    [resumeInto],
  );

  const resumeThread = React.useCallback(
    (threadId: string, replayTurns: ReadonlyArray<ChatTurn>): void => {
      // Abandon any run in flight for the previous thread before swapping.
      controllerRef.current?.abort();
      controllerRef.current = null;
      pausedRef.current = false;
      setPausedTurnId(null);
      setEditError(null);
      setBusy(false);
      // Bind to the selected checkpoint so the next `send` continues it.
      threadIdRef.current = threadId;
      setTurns(replayTurns);
    },
    [],
  );

  const startNewChat = React.useCallback((): void => {
    // Same teardown as resumeThread, but bind to NO thread: nulling the ref
    // makes the next `send` mint a fresh id (lazy creation).
    controllerRef.current?.abort();
    controllerRef.current = null;
    pausedRef.current = false;
    setPausedTurnId(null);
    setEditError(null);
    setBusy(false);
    threadIdRef.current = null;
    setTurns([]);
  }, []);

  return {
    turns,
    busy,
    send,
    pausedTurnId,
    editError,
    pauseForEdit,
    saveUnderstanding,
    cancelEditAndResume,
    resumeThread,
    startNewChat,
  };
}
