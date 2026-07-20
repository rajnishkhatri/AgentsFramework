/**
 * quiz_why_item_vm — SEQ-2 purpose card (VOICE-5).
 *
 * Pure T1 map: composes an honest purpose card from real session state —
 * skill name (taxonomy join), difficulty (question metadata), position
 * (session tally + target). VOICE-5: every number is sourced; no decorative
 * figures, and no claim about interleaving/ordering the scheduler doesn't
 * guarantee (never "because you missed this last" or "next up"). VOICE-3: no
 * engine vocabulary in learner-facing copy.
 *
 * Imports nothing. No I/O, no React, no SDK.
 */

export interface QuizWhyItemInput {
  /** Joined skill display name; null when the taxonomy join failed (FR-Q7-1). */
  readonly skillName: string | null;
  /** Question difficulty 1..5 (author metadata, not answer-bearing). */
  readonly difficulty: number;
  /** 1-based position from the progress VM (session tally). */
  readonly position: number;
  /** Display denominator (target_count), or null when endless / over-run. */
  readonly total: number | null;
}

export interface QuizWhyItemVM {
  /** Card eyebrow — prototype: "THIS ITEM WAS PICKED ON PURPOSE". */
  readonly eyebrow: string;
  /** Sourced body line under the eyebrow. */
  readonly body: string;
  /**
   * Flat single-line form (eyebrow + body) for callers that still render a
   * one-liner; prefer eyebrow/body for the purpose card.
   */
  readonly line: string;
}

export const WHY_ITEM_EYEBROW = "THIS ITEM WAS PICKED ON PURPOSE";

function positionPhrase(position: number, total: number | null): string {
  if (total == null) {
    return position === 1
      ? "the first reviewed item in this session"
      : `reviewed item ${position} in this session`;
  }
  if (position === 1) {
    return `the first of ${total} reviewed items`;
  }
  return `item ${position} of ${total} reviewed items`;
}

export function toQuizWhyItemVM(input: QuizWhyItemInput): QuizWhyItemVM {
  const opening =
    input.skillName != null && input.skillName.length > 0
      ? `Opening in ${input.skillName} at difficulty ${input.difficulty}`
      : `Opening at difficulty ${input.difficulty}`;
  const body = `${opening} — ${positionPhrase(input.position, input.total)}.`;
  return {
    eyebrow: WHY_ITEM_EYEBROW,
    body,
    line: `${WHY_ITEM_EYEBROW} — ${body}`,
  };
}
