/**
 * §6 Per-question resolution order (coach-v3 / T R.7).
 *
 * When a question has multiple attempt rows, the canonical row is the one with
 * the greatest `created_at`, ties broken by the greatest `id`. ONE helper —
 * reused by FR-B10 tally, FR-D1/D2 summary misses + panels, and FR-E1 eligibility.
 *
 * Pure translator (T1): wire shapes only; no I/O.
 */

export type ResolvingAttemptIdentity = {
  readonly id: string;
  readonly question_id: string;
  readonly created_at: string;
};

/** True when `a` should replace `b` under §6 order. */
export function isNewerResolvingAttempt(
  a: ResolvingAttemptIdentity,
  b: ResolvingAttemptIdentity,
): boolean {
  if (a.created_at !== b.created_at) {
    return a.created_at > b.created_at;
  }
  return a.id > b.id;
}

/**
 * Dedup attempts by `question_id` using §6 order.
 * Input order does not matter.
 */
export function resolvingAttemptForQuestion<T extends ResolvingAttemptIdentity>(
  attempts: readonly T[],
): ReadonlyMap<string, T> {
  const byQuestion = new Map<string, T>();
  for (const attempt of attempts) {
    const previous = byQuestion.get(attempt.question_id);
    if (previous == null || isNewerResolvingAttempt(attempt, previous)) {
      byQuestion.set(attempt.question_id, attempt);
    }
  }
  return byQuestion;
}
