/** AttemptRepo port (ADR-0006 #3) — append-only history + "review my misses". */

import type { Attempt, AttemptInput } from "../../wire/engine_entities";

/**
 * AttemptRepo — append-only attempt history + "review my misses" (ADR-0006 #3).
 *
 * Behavioral contract:
 *   1. APPEND-ONLY. `record()` inserts one attempt; attempts are never updated
 *      or deleted. `correct` comes from the `Grader` `Verdict`; this port does
 *      not re-derive correctness (engine spec FR-D2).
 *   2. `used_hint` is persisted as-is and NEVER changes recorded correctness
 *      (FR-D5) — a hinted correct answer is still correct.
 *   3. `misses()` returns the learner's incorrect attempts (newest-first),
 *      feeding the "review my misses" pool (FR-D4 / FR-A6). Returns `[]` (not
 *      throw) when the learner has no misses.
 *   4. `record()` returns the persisted `Attempt` (with engine-assigned `id`
 *      and `created_at`) so the caller need not re-read.
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface AttemptRepo {
  /** Append one attempt; returns the persisted row (id + created_at assigned). */
  record(attempt: AttemptInput): Promise<Attempt>;

  /** The learner's incorrect attempts for a subject, newest-first. */
  misses(subject: string, learnerId: string): Promise<Attempt[]>;
}
