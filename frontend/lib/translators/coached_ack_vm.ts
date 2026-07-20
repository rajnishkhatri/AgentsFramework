/**
 * coached_ack_vm — wrong-pick acknowledgment composer v2 (MOM-3 / V2 / LEAK-1).
 *
 * Pure T1 map: (Question, picked wrong letter) → the distinct coach statement
 * that precedes ladder rung 1 after a wrong commit.
 *
 * Shape (T20 / V2): verdict → specific diagnosis → "So —" hand-off into the
 * pump. The prior re-read hand-off competed with rung-1 and is retired.
 * VOICE-3 forbids engine vocabulary in learner-facing copy. LEAK-1 forbids
 * naming the correct letter or restating the key — a diagnosis that would
 * leak is substituted with a neutral fallback.
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
  /** Soft negative + usefulness framing. */
  readonly verdict: string;
  /** Item-specific trap / misconception (never the answer). */
  readonly diagnosis: string;
  /** Lead-in to the pump — not a second question. */
  readonly handoff: string;
  /** The three parts joined in verdict → diagnosis → handoff order. */
  readonly body: string;
  /** LEAK-1: true if diagnosis was substituted to avoid naming the answer. */
  readonly leaked: boolean;
}

const VERDICT = "Not quite — and it's a telling miss.";

const GENERIC_DIAGNOSIS =
  "There's a small detail here that's easy to overlook.";

const HANDOFF = "So —";

const NEUTRAL_DIAGNOSIS =
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

function pickDiagnosis(question: Question, pickedLetter: string): string {
  const mc = question.misconception;
  if (mc != null && mc.trim().length > 0) return mc.trim();
  const r = question.per_choice_rationale[pickedLetter] ?? "";
  if (r.trim().length > 0) return r.trim();
  return GENERIC_DIAGNOSIS;
}

export function composeCoachedAck(input: CoachedAckInput): CoachedAckVM {
  const { question: q, pickedLetter } = input;
  const diagnosis = pickDiagnosis(q, pickedLetter);
  const leaked = leaks(diagnosis, q);
  const safeDiagnosis = leaked ? NEUTRAL_DIAGNOSIS : diagnosis;
  const body = `${VERDICT} ${safeDiagnosis} ${HANDOFF}`;
  return {
    verdict: VERDICT,
    diagnosis: safeDiagnosis,
    handoff: HANDOFF,
    body,
    leaked,
  };
}
