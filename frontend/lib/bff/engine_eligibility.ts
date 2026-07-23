/**
 * Content-fresh eligibility projection (coach-v3 FR-E1 / E4).
 *
 * Already-correct = question ids whose **latest** attempt (by `created_at`) is
 * `correct === true` — the inverse of outstanding misses (`listMisses`). Pure
 * read over attempt rows; no `skill_state` write. Callers must scope input to
 * one learner+subject and pass rows newest-first (first sighting wins).
 */

export type EligibilityAttemptRow = {
  question_id: string;
  correct: boolean;
  created_at: string;
};

/** FR-E4 — question ids to prefer-exclude from the adaptive pool. */
export function projectAlreadyCorrectQuestionIds(
  attemptsNewestFirst: readonly EligibilityAttemptRow[],
): string[] {
  const latestByQuestion = new Map<string, EligibilityAttemptRow>();
  for (const row of attemptsNewestFirst) {
    if (!latestByQuestion.has(row.question_id)) {
      latestByQuestion.set(row.question_id, row);
    }
  }
  const ids: string[] = [];
  for (const row of latestByQuestion.values()) {
    if (row.correct === true) ids.push(row.question_id);
  }
  return ids;
}
