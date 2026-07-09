/** Scheduler port (ADR-0006 #5) — FSRS adaptivity; sole writer of skill_state. */

import type {
  Attempt,
  NextItem,
  SkillState,
} from "../../wire/engine_entities";

/**
 * Scheduler — adaptivity (FSRS); the ONLY writer of `skill_state` (ADR-0006 #5).
 *
 * Behavioral contract:
 *   1. SOLE WRITER OF `skill_state` (engine spec FR-A2). No other port mutates
 *      `skill_state`. `review()` is the only method that persists a mastery /
 *      stability / difficulty / due_at update.
 *   2. `next()` picks the next (skill, question) to serve: the most-due skill
 *      determined from `skill_state` (lowest mastery among `due_at <= now`),
 *      then a reviewed question for it (FR-A1). The algorithm is
 *      SUBJECT-AGNOSTIC — it reads `skill_state`, not subject content.
 *   2a. `servedIds` (S3, FR-9/10/11): question ids already served this session.
 *      `next()` never returns a question in `servedIds`; when the most-due
 *      skill's reviewed items are all served it falls through to the next-weakest
 *      skill (FR-10), and when EVERY skill is exhausted it throws
 *      `EngineNotFoundError` (FR-11 — end early, never repeat). Passing
 *      `servedIds` performs NO `skill_state` write (the set is read-only,
 *      FR-13). Omitted / empty → today's behaviour exactly.
 *   2b. `servedSkillIds` (S3.1, FR-1/2/3/4 — round-robin rotation, ADR-0024):
 *      this session's served skills, NEWEST-FIRST. When supplied, least-recently-
 *      served becomes the PRIMARY ordering of the candidate pool (a never-served
 *      eligible skill first; among served, the oldest most-recent-serve first),
 *      with the weakest-mastery → `due_at` → `skill_id` order breaking ties ONLY
 *      after rotation — so a just-finished skill is not served again while another
 *      eligible skill exists. Read-only like `servedIds` (no `skill_state` write,
 *      FR-7). Omitted / empty → weakest-first exactly (FR-1). Rotation only
 *      reorders which eligible skill is tried first; it never re-serves a question
 *      or changes the exhaustion condition (FR-6).
 *   3. `review(attempt)` applies the FSRS update for the attempt's skill and
 *      returns the new `SkillState`. Deterministic given the prior state + the
 *      attempt + the review time (the adapter owns the clock; the FSRS math is
 *      pure and is the SDK seam — Rule A1).
 *   4. SEEDING (FR-A7): a brand-new learner with no `skill_state` rows is seeded
 *      with default state per skill on first `next()`; the adapter, not the
 *      caller, owns seeding.
 *   5. Returned values are `wire/engine_entities` shapes — no FSRS SDK type
 *      escapes (Rule A4 / F-R8).
 *
 * @throws SchedulerError on persistence or scheduling failure.
 * @throws EngineNotFoundError when no schedulable item exists for the learner.
 */
export interface Scheduler {
  /**
   * Pick the next (skill, question) for a learner; seeds new learners (FR-A7).
   * `servedIds` are this session's already-served question ids: never returned,
   * fall through to the next-weakest skill when a skill is exhausted, and throw
   * `EngineNotFoundError` when all are exhausted (FR-9/10/11). `servedSkillIds`
   * are this session's served skills newest-first: when supplied, least-recently-
   * served is the primary pool order (round-robin rotation, S3.1/ADR-0024) so a
   * finished skill isn't served again while another is eligible; omitted/empty →
   * weakest-first (FR-1). Read-only — no `skill_state` write (FR-13/FR-7).
   */
  next(
    subject: string,
    learnerId: string,
    servedIds?: readonly string[],
    servedSkillIds?: readonly string[],
  ): Promise<NextItem>;

  /** Apply the FSRS update for an attempt; the sole `skill_state` write (FR-A2). */
  review(attempt: Attempt): Promise<SkillState>;
}
