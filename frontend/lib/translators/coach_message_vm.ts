/**
 * coach_message_vm — AssistantRunView → CoachMessage (FR-F1..F5).
 *
 * Pure T1 map. The coach reuses the chat run pipeline (plan §Coach reuse:
 * `use_coach` wraps `use_agent_run`), so the streaming assistant turn arrives as
 * the same `AssistantRunView` the chat reducer produces. This map projects it to
 * the coach bubble:
 *
 *   - markdown: the text segments flattened (prose only — tool segments dropped;
 *     the coach speaks, it does not render tool cards);
 *   - status/pending: "streaming" → typing indicator (FR-F3); a terminal status
 *     clears the spinner;
 *   - error/canRetry: an "error" terminal view is a RECOVERABLE error with a
 *     retry affordance, never a permanent spinner (FR-F4);
 *   - traceId: forwarded verbatim (F-R7).
 *
 * Imports the sibling reducer's TYPE + `wire/` only. No I/O, no React, no SDK.
 */

import type { AssistantRunView } from "./run_view_reducer";

export interface CoachMessage {
  readonly role: "coach";
  readonly markdown: string;
  readonly status: AssistantRunView["status"];
  /** True while the reply is still streaming — drives the typing indicator (FR-F3). */
  readonly pending: boolean;
  /** True on a terminal error — drives the recoverable error state (FR-F4). */
  readonly error: boolean;
  /** An error is always recoverable in this UX (retry the turn), never a dead end (FR-F4). */
  readonly canRetry: boolean;
  readonly traceId: string | null;
}

export function toCoachMessage(viewState: AssistantRunView): CoachMessage {
  const markdown = viewState.segments
    .filter((s): s is { kind: "text"; text: string } => s.kind === "text")
    .map((s) => s.text)
    .join("");

  const isError = viewState.status === "error";
  const bubbleText =
    isError && markdown === ""
      ? (viewState.errorMessage ?? "The coach could not respond.")
      : isError && viewState.errorMessage
        ? // Partial reply streamed, then the stream dropped: separate the
          // salvaged prose from the error with a blank line (markdown) so the
          // two don't glue into one run ("…semicolon.stream dropped").
          `${markdown}\n\n${viewState.errorMessage}`
        : markdown;

  return {
    role: "coach",
    markdown: bubbleText,
    status: viewState.status,
    pending: viewState.status === "streaming",
    error: isError,
    canRetry: isError,
    traceId: viewState.traceId,
  };
}
