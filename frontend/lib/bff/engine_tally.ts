/**
 * Commit-first running/close tally (coach-v3 FR-B10 / §6).
 *
 * numerator = unique questions resolved `first_try`
 * denominator = unique resolved questions (any resolution)
 * Dedup by `question_id` via §6 order (greatest `created_at`, ties by greatest
 * `id`) — same helper as summary / misses / eligibility (T R.7).
 * Ignores client-provided tallies.
 */

import type { Attempt } from "../wire/engine_entities";
import { resolvingAttemptForQuestion } from "../translators/resolving_attempt";

const RESOLUTIONS = new Set(["first_try", "coached", "walked_through"]);

export function commitFirstTally(attempts: readonly Attempt[]): {
  score_correct: number;
  score_total: number;
} {
  const resolved = resolvingAttemptForQuestion(attempts);
  let score_correct = 0;
  let score_total = 0;
  for (const a of resolved.values()) {
    const r = a.resolution;
    if (r == null || !RESOLUTIONS.has(r)) continue;
    score_total += 1;
    if (r === "first_try") score_correct += 1;
  }
  return { score_correct, score_total };
}

/**
 * FR-C2 / T R.3: bounded session has already resolved `target_count` items.
 * Endless sessions (`target_count == null`) never hit this boundary.
 */
export function isAtTargetCount(
  targetCount: number | null | undefined,
  scoreTotal: number,
): boolean {
  return targetCount != null && scoreTotal >= targetCount;
}
