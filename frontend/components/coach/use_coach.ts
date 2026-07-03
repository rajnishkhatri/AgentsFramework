/**
 * useCoach — the Coach surfaces' seam onto the CHAT runtime (FR-F, FR-J3).
 *
 * The coach is NOT an engine port (plan OD-3 / design §7 divergence #1): there
 * is no `CoachAgentClient`. The coach is a *consumer of the chat runtime port*
 * (`AgentRuntimeClient`); each streaming assistant turn is projected to a
 * coach bubble via the pure `toCoachMessage` translator (Phase 0.5).
 *
 * Phase 4.3 (FR-J3): the transcript + thread id moved out of per-mount React
 * state into `coach_thread_store`, because the iPad split renders the SAME
 * thread in two mounts (the quiz page's CoachPanel and the Coach screen) and
 * the thread must survive the client-side navigation between them. This hook
 * is now a thin `useSyncExternalStore` view over that store; the send loop
 * (`sendCoachAsk`) is a React-free orchestration reusing the chat pipeline's
 * pure pieces (`uiInputToAgentRequest`, `consumeRunStream`), so it keeps the
 * terminal-state safety for free: a dropped stream surfaces as a synthetic
 * `run_error` → `toCoachMessage` maps it to `error + canRetry` (FR-F4: retry,
 * never an infinite spinner).
 */

"use client";

import * as React from "react";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import { consumeRunStream, type ChatTurn } from "@/components/chat/use_agent_run";
import { uiInputToAgentRequest } from "@/lib/translators/ui_input_to_agent_request";
import { toCoachMessage, type CoachMessage } from "@/lib/translators/coach_message_vm";
import {
  applyCoachEvent,
  beginCoachTurn,
  coachThreadSnapshot,
  endCoachTurn,
  subscribeCoachThread,
} from "./coach_thread_store";

/**
 * The coach's AgentFacts id (services/governance/subject_coach_identity.py).
 * Stamped on every run body so the middleware selects the identity-bound
 * coach graph (ADR-0007/0012 — 1B-10); the BFF coach route forwards it
 * untouched (see app/api/coach/run/stream/route.ts).
 */
export const SUBJECT_COACH_AGENT_ID = "subject-coach-english";

/** One coach exchange: the learner's ask + the coach's (streaming) reply. */
export interface CoachTurn {
  readonly id: string;
  readonly user: string;
  readonly coach: CoachMessage;
}

/**
 * Pure: project the chat transcript to coach turns. Order-preserving, 1:1 — each
 * `ChatTurn.assistant` view becomes a `CoachMessage`; the user ask rides along.
 */
export function coachTurnsFromChat(
  turns: ReadonlyArray<ChatTurn>,
): ReadonlyArray<CoachTurn> {
  return turns.map((t) => ({
    id: t.id,
    user: t.user,
    coach: toCoachMessage(t.assistant),
  }));
}

/**
 * React-free: send one learner ask on the SHARED coach thread. Any mount may
 * call it (panel or Coach screen); the turn appears in every subscriber. The
 * middleware keys checkpoint state by `thread_id`, so consecutive asks — from
 * either mount — continue one server-side conversation (FR-J3).
 */
export async function sendCoachAsk(
  runtime: AgentRuntimeClient,
  body: string,
): Promise<void> {
  const { threadId, turnId } = beginCoachTurn(body);
  try {
    const req = uiInputToAgentRequest({
      thread_id: threadId,
      body,
      agent_id: SUBJECT_COACH_AGENT_ID,
    });
    await consumeRunStream(runtime.streamRun(req), (evt) =>
      applyCoachEvent(turnId, evt),
    );
  } catch (e) {
    // streamRun threw synchronously (e.g. missing composition wiring) —
    // stream-iteration failures already arrive as run_error via consumeRunStream.
    applyCoachEvent(turnId, {
      type: "run_error",
      trace_id: "no-trace",
      run_id: "",
      error_type: "network_error",
      message: e instanceof Error ? e.message : String(e),
    });
  } finally {
    endCoachTurn();
  }
}

/**
 * Thin React view over the shared thread: subscribes to the store and exposes
 * the coach projection. The views call `ask`/`retry` and render `turns`; they
 * hold no run logic. `retry` re-sends the last user ask (FR-F4) — same thread
 * id, so the resend continues the same coach conversation server-side.
 */
export function useCoach(runtime: AgentRuntimeClient): {
  turns: ReadonlyArray<CoachTurn>;
  busy: boolean;
  ask: (body: string) => Promise<void>;
  retry: () => Promise<void>;
} {
  const snap = React.useSyncExternalStore(
    subscribeCoachThread,
    coachThreadSnapshot,
    coachThreadSnapshot,
  );
  const coachTurns = React.useMemo(
    () => coachTurnsFromChat(snap.turns),
    [snap.turns],
  );

  const ask = React.useCallback(
    (body: string) => sendCoachAsk(runtime, body),
    [runtime],
  );

  const retry = React.useCallback((): Promise<void> => {
    const last = snap.turns.at(-1);
    // Only a terminal error is retryable; a resend of the last ask continues
    // the same thread (FR-F4). Nothing to retry on an empty/streaming transcript.
    if (last == null || last.assistant.status !== "error") return Promise.resolve();
    return sendCoachAsk(runtime, last.user);
  }, [snap.turns, runtime]);

  return { turns: coachTurns, busy: snap.busy, ask, retry };
}
