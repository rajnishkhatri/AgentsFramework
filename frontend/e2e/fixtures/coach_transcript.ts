/**
 * Coach SSE transcript fixtures (PreAct Phase 2.1 — mocked-stream T1).
 *
 * The Coach surface rides the CHAT runtime (design §7 divergence #1): it POSTs to
 * `/api/coach/run/stream` and consumes the same AG-UI event stream chat does
 * (`use_coach` wraps `use_agent_run`). Phase-2 backend flags are OFF, so there is
 * no live coach persona to stream from — these canned `AGUIEvent[]` sequences let
 * a Playwright spec intercept `/api/coach/run/stream` with `page.route(...)` +
 * `buildSSEBody(...)` and render a believable Socratic exchange with no backend.
 *
 * The reply is deliberately SOCRATIC and NON-REVEALING (FR-D5 parity): the coach
 * asks the learner to reason about the rule, never naming the answer letter — so
 * the fixture doubles as a guard that the surface renders a coach-shaped turn, not
 * an answer key.
 *
 * Event shape mirrors `scenarios.ts` exactly (AG-UI uppercase type names,
 * `raw_event.trace_id` on every event per W5). Imports `wire/` only — no SDK, no
 * React, no Playwright.
 */

import type { AGUIEvent } from "../../lib/wire/ag_ui_events";

export const COACH_TRACE_ID = "coach-trace-e2e-1";
export const COACH_RUN_ID = "coach-run-1";
export const COACH_THREAD_ID = "coach-thread-1";

interface CoachTurnOpts {
  readonly traceId?: string;
  readonly runId?: string;
  readonly threadId?: string;
  readonly messageId?: string;
}

function header(traceId: string): { raw_event: { trace_id: string } } {
  return { raw_event: { trace_id: traceId } };
}

/** Break a reply into small deltas so the stream renders token-by-token. */
function contentDeltas(
  text: string,
  messageId: string,
  h: { raw_event: { trace_id: string } },
): AGUIEvent[] {
  // Split on spaces but keep the trailing space so the reassembled text matches.
  const words = text.match(/\S+\s*/g) ?? [text];
  return words.map<AGUIEvent>((delta) => ({
    type: "TEXT_MESSAGE_CONTENT",
    message_id: messageId,
    delta,
    ...h,
  }));
}

/**
 * A single Socratic coach turn: RUN_STARTED → message start → content deltas →
 * message end → RUN_FINISHED. `reply` defaults to a punctuation-rule nudge that
 * never states the answer.
 */
export function coachTurn(opts: CoachTurnOpts & { reply?: string } = {}): ReadonlyArray<AGUIEvent> {
  const traceId = opts.traceId ?? COACH_TRACE_ID;
  const runId = opts.runId ?? COACH_RUN_ID;
  const threadId = opts.threadId ?? COACH_THREAD_ID;
  const messageId = opts.messageId ?? "coach-msg-1";
  const h = header(traceId);
  const reply =
    opts.reply ??
    "Good question. Before I say more — what job is that comma doing in the sentence? " +
      "Try reading it aloud and notice where you naturally pause. Which clause could stand on its own?";

  return [
    { type: "RUN_STARTED", run_id: runId, thread_id: threadId, ...h },
    { type: "TEXT_MESSAGE_START", message_id: messageId, role: "assistant", ...h },
    ...contentDeltas(reply, messageId, h),
    { type: "TEXT_MESSAGE_END", message_id: messageId, ...h },
    { type: "RUN_FINISHED", run_id: runId, thread_id: threadId, ...h },
  ];
}

/** The full reply text of the default coach turn (for a settle/contains assertion). */
export const COACH_TURN_1_TEXT =
  "Good question. Before I say more — what job is that comma doing in the sentence? " +
  "Try reading it aloud and notice where you naturally pause. Which clause could stand on its own?";

/** A second, distinct Socratic turn — used to prove the log accretes across turns. */
export const COACH_TURN_2_TEXT =
  "You're close. Notice that both halves are complete sentences on their own — " +
  "so what punctuation is strong enough to join two independent clauses?";

export function coachTurnTwo(opts: CoachTurnOpts = {}): ReadonlyArray<AGUIEvent> {
  return coachTurn({
    ...opts,
    runId: opts.runId ?? "coach-run-2",
    messageId: opts.messageId ?? "coach-msg-2",
    reply: COACH_TURN_2_TEXT,
  });
}
