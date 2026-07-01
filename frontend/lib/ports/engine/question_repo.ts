/** QuestionRepo port (ADR-0006 #2) — item persistence + the reviewed gate. */

import type { Question } from "../../wire/engine_entities";

/**
 * QuestionRepo — persistence for items, with the reviewed gate (ADR-0006 #2).
 *
 * Behavioral contract:
 *   1. THE REVIEWED GATE (engine spec FR-B*). `nextReviewed()` returns ONLY
 *      questions with `reviewed = true`. A `reviewed = false` row MUST NEVER be
 *      returned from `nextReviewed()` — that is the single hard invariant of
 *      this port. `get(id)` may return an unreviewed row (admin/generation
 *      paths use it); only the learner-facing `nextReviewed()` is gated.
 *   2. NEVER GRADES. This port persists and retrieves; correctness is the
 *      `Grader`'s concern. It must not inspect `answer_letter` to decide
 *      anything beyond returning the row.
 *   3. `nextReviewed()` returns `null` (not throw) when no reviewed item exists
 *      for the (subject, skillId) — the caller treats that as "nothing due".
 *   4. `save()` is the generation/seed write path; it accepts unreviewed rows
 *      (the reviewed flag is set by the generation self-consistency gate,
 *      FR-E2, not here).
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface QuestionRepo {
  /** Next reviewed item for a skill, or null if none. Returns reviewed=true ONLY. */
  nextReviewed(subject: string, skillId: string): Promise<Question | null>;

  /** Fetch one question by id (may be unreviewed — non-learner paths). */
  get(id: string): Promise<Question | null>;

  /** Persist a question (generation/seed path; reviewed flag set upstream). */
  save(question: Question): Promise<void>;
}
