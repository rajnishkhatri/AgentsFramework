/**
 * useCoach — the Coach surfaces' seam onto the CHAT runtime (FR-F, FR-J3, BP-3).
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
 *
 * BP-3: when the store holds a pin and engine ports are supplied, the ask
 * attaches assembled `input.coach_context` (advisory mode — BFF overwrites).
 */

"use client";

import * as React from "react";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import type { EnginePortBag } from "@/lib/composition_engine";
import { useEngine } from "@/app/engine-provider";
import { consumeRunStream, type ChatTurn } from "@/components/chat/use_agent_run";
import { uiInputToAgentRequest } from "@/lib/translators/ui_input_to_agent_request";
import { assembleCoachContext } from "@/lib/translators/assemble_coach_context";
import type { CoachMode } from "@/lib/translators/coach_context_sanitizer";
import { toCoachMessage, type CoachMessage } from "@/lib/translators/coach_message_vm";
import { DEFAULT_SUBJECT } from "@/lib/wire/engine_entities";
import {
  applyCoachEvent,
  beginCoachTurn,
  coachThreadSnapshot,
  endCoachTurn,
  subscribeCoachThread,
} from "./coach_thread_store";
import { countMissesOnSkill } from "./use_coach_surface";
import { useLearnIdentity } from "@/components/learn/LearnIdentityProvider";

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

export interface SendCoachAskOptions {
  /** Advisory mode only — BFF overwrites (FR-11 / ADR-0012). */
  readonly mode?: CoachMode;
  readonly ports?: Pick<
    EnginePortBag,
    "questionRepo" | "attemptRepo" | "learnerRead"
  >;
  readonly learnerId?: string;
  readonly subject?: string;
  /**
   * ADR-0035: wrong letter for Gen2 ladders. Omit → read from coach thread
   * store (quiz moment router). Explicit null clears.
   */
  readonly choiceLetter?: "A" | "B" | "C" | "D" | null;
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
 *
 * When `opts.ports` + store pin are present, attaches honest `coach_context`
 * (FR-10); otherwise messages-only (FR-9).
 */
export async function sendCoachAsk(
  runtime: AgentRuntimeClient,
  body: string,
  opts: SendCoachAskOptions = {},
): Promise<void> {
  const { threadId, turnId } = beginCoachTurn(body);
  try {
    const snap = coachThreadSnapshot();
    const pin = snap.pin;
    const mode = opts.mode ?? snap.mode;
    const choiceLetter =
      opts.choiceLetter !== undefined ? opts.choiceLetter : snap.choiceLetter;
    let coach_context = null as ReturnType<typeof assembleCoachContext>;

    if (pin != null && opts.ports != null) {
      const subject = opts.subject ?? DEFAULT_SUBJECT;
      if (opts.learnerId == null || opts.learnerId === "") {
        throw new Error(
          "sendCoachAsk: learnerId is required when assembling coach_context " +
            "(pass session identity — never invent Garvit)",
        );
      }
      const learnerId = opts.learnerId;
      // Lesson pins: skip questionRepo (no questionId — ADR-0030 honest-null).
      const question =
        pin.kind === "item"
          ? await opts.ports.questionRepo.get(pin.questionId)
          : null;
      const missesOnSkill = await countMissesOnSkill(opts.ports, {
        subject,
        learnerId,
        skillId: pin.skillId,
      });
      let skillStates = null as Awaited<
        ReturnType<EnginePortBag["learnerRead"]["listSkillState"]>
      > | null;
      try {
        skillStates = await opts.ports.learnerRead.listSkillState(
          subject,
          learnerId,
        );
      } catch {
        skillStates = null;
      }
      coach_context = assembleCoachContext({
        pin,
        question,
        mode,
        missesOnSkill,
        skillStates,
        choiceLetter,
      });
    }

    const req = uiInputToAgentRequest({
      thread_id: threadId,
      body,
      agent_id: SUBJECT_COACH_AGENT_ID,
      coach_context,
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
export function useCoach(
  runtime: AgentRuntimeClient,
  options: { mode?: CoachMode } = {},
): {
  turns: ReadonlyArray<CoachTurn>;
  busy: boolean;
  ask: (body: string) => Promise<void>;
  retry: () => Promise<void>;
} {
  const ports = useEngine();
  const { learnerId } = useLearnIdentity();
  const mode = options.mode ?? "pre_submit";
  const snap = React.useSyncExternalStore(
    subscribeCoachThread,
    coachThreadSnapshot,
    coachThreadSnapshot,
  );
  const coachTurns = React.useMemo(
    () => coachTurnsFromChat(snap.turns),
    [snap.turns],
  );

  const askOpts = React.useMemo(
    (): SendCoachAskOptions => ({
      mode,
      ports: {
        questionRepo: ports.questionRepo,
        attemptRepo: ports.attemptRepo,
        learnerRead: ports.learnerRead,
      },
      learnerId,
      subject: DEFAULT_SUBJECT,
    }),
    [mode, ports, learnerId],
  );

  const ask = React.useCallback(
    (body: string) => sendCoachAsk(runtime, body, askOpts),
    [runtime, askOpts],
  );

  const retry = React.useCallback((): Promise<void> => {
    const last = snap.turns.at(-1);
    // Only a terminal error is retryable; a resend of the last ask continues
    // the same thread (FR-F4). Nothing to retry on an empty/streaming transcript.
    if (last == null || last.assistant.status !== "error") return Promise.resolve();
    return sendCoachAsk(runtime, last.user, askOpts);
  }, [snap.turns, runtime, askOpts]);

  return { turns: coachTurns, busy: snap.busy, ask, retry };
}
