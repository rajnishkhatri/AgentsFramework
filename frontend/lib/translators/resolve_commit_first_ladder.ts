/**
 * Commit-first ladder source chain (FR-8): choice-keyed → item-level →
 * generic single-rung. Silent fallback; never reveals the answer.
 */

import type { Hint } from "../wire/engine_entities";

/**
 * Resolve the ladder for a wrong letter under commit-first.
 * `load(letter)` should return reviewed rungs for that choice (or item-level
 * when `letter` is null). Empty arrays trigger the next fallback.
 */
export async function resolveCommitFirstLadder(
  load: (choiceLetter: string | null) => Promise<readonly Hint[]>,
  wrongLetter: string,
  genericBody: string,
  questionId: string,
  subject: string,
): Promise<readonly Hint[]> {
  const choiceLadder = await load(wrongLetter);
  if (choiceLadder.length > 0) return choiceLadder;

  const itemLadder = await load(null);
  if (itemLadder.length > 0) return itemLadder;

  // Single-rung generic — exhaustion still offers FR-5 actions.
  const generic: Hint = {
    id: `generic-${questionId}`,
    subject,
    question_id: questionId,
    choice_letter: null,
    rung: 1,
    body_md: genericBody,
    reviewed: true,
    generated_by: "commit-first-fallback",
  };
  return [generic];
}
