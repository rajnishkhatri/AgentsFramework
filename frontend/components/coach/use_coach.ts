/**
 * useCoach — the Coach screen's seam onto the CHAT runtime (FR-F).
 *
 * The coach is NOT an engine port (plan OD-3 / design §7 divergence #1): there
 * is no `CoachAgentClient`. The coach is a *consumer of the chat runtime port*
 * (`AgentRuntimeClient`), so this hook wraps `useAgentRun` and projects each
 * streaming assistant turn (`AssistantRunView`) to a coach bubble via the pure
 * `toCoachMessage` translator (Phase 0.5). It inherits the chat pipeline's
 * terminal-state safety for free: a dropped stream surfaces as a synthetic
 * `run_error` → `toCoachMessage` maps it to `error + canRetry` (FR-F4: retry,
 * never an infinite spinner).
 *
 * Per F-R1 the CoachView owns no run logic. The React-free mapping
 * `coachTurnsFromChat` is exported so the projection is testable in node without
 * React (the analogue of `consumeRunStream`).
 */

"use client";

import * as React from "react";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import { useAgentRun, type ChatTurn } from "@/components/chat/use_agent_run";
import { toCoachMessage, type CoachMessage } from "@/lib/translators/coach_message_vm";

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
 * Thin React wrapper: drives the chat runtime and exposes the coach projection.
 * The CoachView calls `ask`/`retry` and renders `turns`; it holds no run logic.
 * `retry` re-sends the last user ask (FR-F4) — the runtime keys the checkpoint by
 * thread id, so a resend continues the same coach thread server-side.
 */
export function useCoach(runtime: AgentRuntimeClient): {
  turns: ReadonlyArray<CoachTurn>;
  busy: boolean;
  ask: (body: string) => Promise<void>;
  retry: () => Promise<void>;
} {
  const { turns, busy, send } = useAgentRun(runtime, undefined, {
    agentId: SUBJECT_COACH_AGENT_ID,
  });
  const coachTurns = React.useMemo(() => coachTurnsFromChat(turns), [turns]);

  const ask = React.useCallback((body: string) => send(body), [send]);

  const retry = React.useCallback((): Promise<void> => {
    const last = turns.at(-1);
    // Only a terminal error is retryable; a resend of the last ask continues the
    // same thread (FR-F4). Nothing to retry on an empty/streaming transcript.
    if (last == null || last.assistant.status !== "error") return Promise.resolve();
    return send(last.user);
  }, [turns, send]);

  return { turns: coachTurns, busy, ask, retry };
}
