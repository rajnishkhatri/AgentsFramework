/** ProgressRepo port (ADR-0028) — the progress-trend read seam. */

import type { ProgressPoint } from "../../wire/engine_entities";

/**
 * ProgressRepo — read-only access to a learner's progress points (ADR-0028).
 *
 * Behavioral contract:
 *   1. READ-ONLY. There is deliberately NO write surface on this port.
 *      Progress rows are written by analytics/seed at the composition
 *      boundary, never through serving code.
 *   2. `list()` returns `[]` (not throw) when the learner has no points —
 *      the caller treats that as "no trend yet", never fabricates one.
 *   3. Returns `wire/engine_entities` shapes only — no SDK type escapes (F-R8).
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface ProgressRepo {
  /** Progress points for a learner, oldest-first; [] when none. */
  list(subject: string, learnerId: string): Promise<ProgressPoint[]>;
}
