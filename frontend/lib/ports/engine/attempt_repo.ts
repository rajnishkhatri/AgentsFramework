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
 *   5. `servedQuestionIds()` returns the question ids ALREADY answered in one
 *      session — every attempt regardless of correctness (unlike `misses`),
 *      derived from the append-only `attempt` rows (S3, FR-13). It is the
 *      caller-owned, ephemeral served-set the play loop passes to
 *      `Scheduler.next(…, servedIds)` so a session never repeats a question.
 *      This history is NEVER written to `skill_state` (FR-A2 purity). Returns
 *      `[]` (not throw) for a session with no attempts.
 *   6. `servedSkillIds()` returns the DISTINCT skills served in one session,
 *      NEWEST-FIRST (S3.1, FR-5) — the round-robin rotation signal (ADR-0024).
 *      Same provenance as `servedQuestionIds` (derived from `attempt`, joined to
 *      each question's `skill_id`; NEVER `skill_state`), passed to
 *      `Scheduler.next(…, servedSkillIds)` so a finished skill rotates to the
 *      back. Returns `[]` for a session with no attempts.
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface AttemptRepo {
  /** Append one attempt; returns the persisted row (id + created_at assigned). */
  record(attempt: AttemptInput): Promise<Attempt>;

  /** The learner's incorrect attempts for a subject, newest-first. */
  misses(subject: string, learnerId: string): Promise<Attempt[]>;

  /**
   * The question ids already answered in `sessionId` (any correctness), for the
   * within-session no-repeat guarantee (FR-13). Ephemeral + caller-owned;
   * derived from `attempt`, never persisted on `skill_state`.
   */
  servedQuestionIds(sessionId: string): Promise<readonly string[]>;

  /**
   * The distinct skills served in `sessionId`, newest-first, for round-robin
   * rotation (S3.1 FR-5). Ephemeral + caller-owned; derived from `attempt`
   * joined to each question's skill, never persisted on `skill_state`.
   */
  servedSkillIds(sessionId: string): Promise<readonly string[]>;
}
