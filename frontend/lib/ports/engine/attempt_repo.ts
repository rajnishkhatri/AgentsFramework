/** AttemptRepo port (ADR-0006 #3) — append-only history + "review my misses". */

import type {
  AccuracyBySkill,
  Attempt,
  AttemptInput,
} from "../../wire/engine_entities";

/**
 * AttemptRepo — append-only attempt history + "review my misses" (ADR-0006 #3).
 *
 * Behavioral contract:
 *   1. APPEND-ONLY. `record()` inserts one attempt; attempts are never updated
 *      or deleted. `correct` comes from the `Grader` `Verdict`; this port does
 *      not re-derive correctness (engine spec FR-D2).
 *   2. `used_hint` is persisted as-is and NEVER changes recorded correctness
 *      (FR-D5) — a hinted correct answer is still correct.
 *   3. `misses()` returns **outstanding** misses (newest-first): for each
 *      `question_id`, the learner's latest attempt is included iff it is
 *      incorrect. A later correct answer clears that item from the review pool
 *      (FR-D4 / FR-A6 / FR-C5). Append-only history is unchanged — this is a
 *      read projection. Returns `[]` (not throw) when none are outstanding.
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
 *   7. `accuracyBySkill()` returns per-skill answer-accuracy over the last N
 *      qualifying sessions (default 6), newest-first bars (E1b-D1). Derived
 *      from append-only `attempt` only — NEVER reads/writes `skill_state`
 *      (FR-7 / FR-13 purity). Hinted-correct counts as correct (FR-8 / FR-D5).
 *      Returns `null` when the learner has no on-skill attempts (self-omit).
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface AttemptRepo {
  /** Append one attempt; returns the persisted row (id + created_at assigned). */
  record(attempt: AttemptInput): Promise<Attempt>;

  /**
   * Outstanding misses for a subject, newest-first (latest attempt per question
   * is incorrect). Cleared when the learner later answers that question correctly.
   */
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

  /**
   * Per-skill answer-accuracy over the last `opts.sessions` (default 6)
   * qualifying sessions (E1b-D1). Append-only `attempt` source; `null` when
   * no on-skill attempts exist.
   */
  accuracyBySkill(
    subject: string,
    learnerId: string,
    skillId: string,
    opts?: { sessions?: number },
  ): Promise<AccuracyBySkill>;
}
