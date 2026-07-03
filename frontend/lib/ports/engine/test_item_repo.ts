/** TestItemRepo port (ADR-0015) — the test-item content-family read seam. */

import type { TestItem } from "../../wire/engine_entities";

/**
 * TestItemRepo — read-only access to the governed exam-item bank (ADR-0015,
 * the ADR-0006 third amendment). The 11th engine port.
 *
 * Behavioral contract:
 *   1. THE REVIEWED GATE (spec FR-27.1). `listReviewed()` returns ONLY items
 *      with `reviewed = true`. An ungated row MUST NEVER be served — `reviewed`
 *      is earned by the Python cascade (schema → independent-solver key gate →
 *      duplicate), never asserted at serving time. The assembler filters again
 *      independently (defense in depth at both layers).
 *   2. READ-ONLY. No write surface (the ADR-0014 posture): serving code must
 *      never flip the gate. Rows are written by the generator/importer at the
 *      composition boundary (the seed path).
 *   3. `listReviewed()` returns `[]` (not throw) when the subject has no
 *      reviewed items — the assembler then fails closed on the short stratum.
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface TestItemRepo {
  /** All reviewed exam items for a subject; [] when none. */
  listReviewed(subject: string): Promise<TestItem[]>;
}
