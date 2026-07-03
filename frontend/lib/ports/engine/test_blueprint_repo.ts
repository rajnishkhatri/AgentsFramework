/** TestBlueprintRepo port (ADR-0015) — the test-blueprint read seam. */

import type { TestBlueprint } from "../../wire/engine_entities";

/**
 * TestBlueprintRepo — read-only access to a test-form blueprint (ADR-0015, the
 * ADR-0006 third amendment). The 10th engine port. Separate from
 * `TestItemRepo` (F-R3 one interface per module): blueprint and item have
 * different consumers and lifecycles (config vs review-gated content), the
 * same reason `Grader` is its own port.
 *
 * Behavioral contract:
 *   1. `get()` returns the blueprint or `null` (not throw) when the id is
 *      unknown — the caller treats a missing blueprint as a config error.
 *   2. READ-ONLY. No write surface: blueprints are authored/seeded at the
 *      composition boundary, never mutated by serving code.
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface TestBlueprintRepo {
  /** The blueprint with this id, or null when unknown. */
  get(id: string): Promise<TestBlueprint | null>;
}
