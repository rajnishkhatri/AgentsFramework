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
  /** Pick the next (skill, question) for a learner; seeds new learners (FR-A7). */
  next(subject: string, learnerId: string): Promise<NextItem>;

  /** Apply the FSRS update for an attempt; the sole `skill_state` write (FR-A2). */
  review(attempt: Attempt): Promise<SkillState>;
}
