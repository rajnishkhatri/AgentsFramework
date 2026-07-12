/** TutorialRepo port (ADR-0028) — the lesson-content read seam. */

import type { Tutorial } from "../../wire/engine_entities";

/**
 * TutorialRepo — read-only access to a skill's reviewed tutorial (ADR-0028).
 *
 * Behavioral contract:
 *   1. THE REVIEWED GATE (E1a FR-1). `getTutorial()` returns ONLY a row with
 *      `reviewed = true`. An ungated row MUST NEVER be served — `reviewed` is
 *      earned by the authored-seed provenance confinement (or a future
 *      generator cascade), never asserted at serving time.
 *   2. READ-ONLY. There is deliberately NO write surface on this port:
 *      serving code must never be able to flip the gate. Rows are written by
 *      the seed/importer at the composition boundary.
 *   3. `getTutorial()` returns `null` (not throw) when the skill has no
 *      reviewed tutorial — the caller takes the honest-degrade path (FR-3 /
 *      FR-18), never a fabricated lesson.
 *   4. Returns `wire/engine_entities` shapes only — no SDK type escapes (F-R8).
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface TutorialRepo {
  /** The skill's reviewed tutorial, or null when absent/unreviewed. */
  getTutorial(subject: string, skillId: string): Promise<Tutorial | null>;
}
