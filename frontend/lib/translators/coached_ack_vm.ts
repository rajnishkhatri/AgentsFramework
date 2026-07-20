/**
 * coached_ack_vm — wrong-pick acknowledgment composer (MOM-3 / VOICE-1 / LEAK-1).
 *
 * Pure T1 map: (Question, picked wrong letter) → the distinct coach statement
 * that precedes ladder rung 1 after a wrong commit. VOICE-1 orders it
 * shared ground → specific complication → hand off to the question. VOICE-3
 * forbids engine vocabulary (ladder, rung, moment, wrong-pick, assertion rung)
 * in learner-facing copy. LEAK-1 forbids naming the correct letter or restating
 * the key — a body that would leak is substituted with a neutral fallback.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type { Question } from "../wire/engine_entities";

export interface CoachedAckInput {
  readonly question: Question;
  /** The wrong letter the learner just submitted. */
  readonly pickedLetter: string;
}

export interface CoachedAckVM {
  readonly sharedGround: string;
  readonly complication: string;
  readonly handoff: string;
  /** The three parts joined in VOICE-1 order. */
  readonly body: string;
  /** LEAK-1: true if any part was substituted to avoid naming the answer. */
  readonly leaked: boolean;
}

const SHARED_GROUND =
  "You read the sentence and saw something to fix — that's the right instinct.";

const GENERIC_COMPLICATION =
  "This one turns on a detail that's easy to miss.";

const HANDOFF =
  "Re-read the sentence with that in mind — what is it actually testing?";

const NEUTRAL_COMPLICATION =
  "There's a small detail here that's easy to overlook — let's look closer.";

/**
 * LEAK-1: a body names the answer if the correct letter appears as a
 * standalone uppercase word (e.g. "A" surrounded by non-letters), or restates
 * the key by containing a long substring of the correct rationale /
 * `why_correct_md`. Conservative: a false positive is honest degradation, not a
 * reveal.
 */
function leaks(body: string, question: Question): boolean {
  const answer = question.answer_letter;
  if (new RegExp(`\\b${escapeRegExp(answer)}\\b`).test(body)) {
    return true;
  }
  const correctRationale = question.per_choice_rationale[answer] ?? "";
  const keySources = [question.why_correct_md, correctRationale]
    .map((s) => s.trim())
    .filter((s) => s.length >= 20);
  for (const src of keySources) {
    // A 24-char run shared with the key is a restate, not coincidence.
    const fragment = src.slice(0, Math.min(src.length, 24));
    if (fragment.length >= 20 && body.includes(fragment)) return true;
  }
  return false;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function pickComplication(question: Question, pickedLetter: string): string {
  const mc = question.misconception;
  if (mc != null && mc.trim().length > 0) return mc.trim();
  const r = question.per_choice_rationale[pickedLetter] ?? "";
  if (r.trim().length > 0) return r.trim();
  return GENERIC_COMPLICATION;
}

export function composeCoachedAck(input: CoachedAckInput): CoachedAckVM {
  const { question: q, pickedLetter } = input;
  const complication = pickComplication(q, pickedLetter);
  const leaked = leaks(complication, q);
  const safeComplication = leaked ? NEUTRAL_COMPLICATION : complication;
  const body = `${SHARED_GROUND} ${safeComplication} ${HANDOFF}`;
  return {
    sharedGround: SHARED_GROUND,
    complication: safeComplication,
    handoff: HANDOFF,
    body,
    leaked,
  };
}
