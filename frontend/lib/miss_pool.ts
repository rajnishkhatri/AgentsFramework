/**
 * Unique missed question ids, newest-incorrect first (FR-A6 pool order).
 * Shared by Dashboard badge count (FR-C5) and review-session open/draw.
 */
export function uniqueMissQuestionIds(
  misses: ReadonlyArray<{ readonly question_id: string }>,
): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const m of misses) {
    if (seen.has(m.question_id)) continue;
    seen.add(m.question_id);
    ids.push(m.question_id);
  }
  return ids;
}
