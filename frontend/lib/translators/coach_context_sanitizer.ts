/**
 * Coach-context sanitizer — the BFF layer of ADR-0012's two-layer assembly
 * (FR-19/FR-21/FR-22).
 *
 * Pure functions (T1: imports `wire/` only; no I/O, no SDK). The route
 * handler reads the coach-session marker store, derives the AUTHORITATIVE
 * mode with `deriveCoachMode` (the client-supplied `coach_context.mode` is
 * advisory and never trusted), then `sanitizeCoachRunBody` strips the four
 * answer-bearing `Question` fields when the derived mode is pre-submit and
 * overwrites the advisory mode with the derived one.
 *
 * Zero-or-many rule (T3): 1 input body → exactly 1 output body. Bodies
 * without a `coach_context` (plain chat runs) pass through unchanged.
 * `trace_id` is not applicable — this is the request direction
 * (`RunCreateRequest` precedent), not the event stream.
 */

import { QUESTION_ANSWER_BEARING_FIELDS } from "@/lib/wire/engine_entities";

export type CoachMode = "pre_submit" | "post_feedback";

/**
 * Marker present ⇒ post_feedback, and monotonically so (once submitted,
 * always post-feedback for that item — ADR-0012 Amendment). No marker ⇒
 * pre_submit, which fails CLOSED: a spoofing client that claims
 * post_feedback without having submitted still gets the stripped context.
 */
export function deriveCoachMode(args: {
  readonly hasSubmittedMarker: boolean;
}): CoachMode {
  return args.hasSubmittedMarker ? "post_feedback" : "pre_submit";
}

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Return a new run body with the coach context sanitized for `derivedMode`.
 * Never mutates the input. Non-coach bodies (no `input.coach_context`)
 * are returned as-is so the shared chat runtime is unaffected.
 */
export function sanitizeCoachRunBody<T>(rawBody: T, derivedMode: CoachMode): T {
  if (!isRecord(rawBody)) return rawBody;
  const input = rawBody.input;
  if (!isRecord(input)) return rawBody;
  const context = input.coach_context;
  if (!isRecord(context)) return rawBody;

  const sanitizedContext: JsonRecord = { ...context, mode: derivedMode };

  if (derivedMode === "pre_submit" && isRecord(context.question)) {
    const question: JsonRecord = { ...context.question };
    for (const field of QUESTION_ANSWER_BEARING_FIELDS) {
      delete question[field];
    }
    sanitizedContext.question = question;
  }

  return {
    ...rawBody,
    input: { ...input, coach_context: sanitizedContext },
  } as T;
}
