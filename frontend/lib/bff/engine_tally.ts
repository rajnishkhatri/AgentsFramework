/**
 * Commit-first running/close tally (coach-v3 FR-B10 / §6).
 *
 * numerator = unique questions resolved `first_try`
 * denominator = unique resolved questions (any resolution)
 * Dedup by `question_id`. Ignores client-provided tallies.
 */

import type { Attempt } from "../wire/engine_entities";

const RESOLUTIONS = new Set(["first_try", "coached", "walked_through"]);

export function commitFirstTally(attempts: readonly Attempt[]): {
  score_correct: number;
  score_total: number;
} {
  const resolved = new Map<string, string>(); // question_id → resolution
  for (const a of attempts) {
    const r = a.resolution;
    if (r == null || !RESOLUTIONS.has(r)) continue;
    // First resolving attempt wins (append-only; later rows shouldn't re-resolve).
    if (!resolved.has(a.question_id)) {
      resolved.set(a.question_id, r);
    }
  }
  let score_correct = 0;
  for (const r of resolved.values()) {
    if (r === "first_try") score_correct += 1;
  }
  return { score_correct, score_total: resolved.size };
}
