/**
 * quiz_why_item_vm — "why this item" annotation (SEQ-2 / VOICE-5).
 *
 * Pure T1 map: composes an honest one-line annotation from real session state
 * — skill name (taxonomy join), difficulty (question metadata), position
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
  readonly line: string;
}

export function toQuizWhyItemVM(input: QuizWhyItemInput): QuizWhyItemVM {
  const positionPart =
    input.total != null
      ? `Question ${input.position} of ${input.total}`
      : `Question ${input.position}`;
  const difficultyPart = `difficulty ${input.difficulty}`;
  const segments = [positionPart];
  if (input.skillName != null && input.skillName.length > 0) {
    segments.push(input.skillName);
  }
  segments.push(difficultyPart);
  return { line: segments.join(" · ") };
}
