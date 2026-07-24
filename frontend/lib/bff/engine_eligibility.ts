/**
 * Content-fresh eligibility projection (coach-v3 FR-E1 / E4).
 *
 * Already-correct = question ids whose **§6 resolving attempt** (greatest
 * `created_at`, ties by greatest `id`) is `correct === true` — the inverse of
 * outstanding misses. Pure read over attempt rows; no `skill_state` write.
 * Input order does not matter (T R.7).
 */

import { resolvingAttemptForQuestion } from "../translators/resolving_attempt";

export type EligibilityAttemptRow = {
  id: string;
  question_id: string;
  correct: boolean;
  created_at: string;
};

/** FR-E4 — question ids to prefer-exclude from the adaptive pool. */
export function projectAlreadyCorrectQuestionIds(
  attempts: readonly EligibilityAttemptRow[],
): string[] {
  const latestByQuestion = resolvingAttemptForQuestion(attempts);
  const ids: string[] = [];
  for (const row of latestByQuestion.values()) {
    if (row.correct === true) ids.push(row.question_id);
  }
  return ids;
}
