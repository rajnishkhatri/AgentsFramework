/** HintRepo port (ADR-0014) — the hint content-family read seam. */

import type { Hint } from "../../wire/engine_entities";

/**
 * HintRepo — read-only access to a question's hint ladder (ADR-0014/ADR-0035,
 * the ADR-0006 amendment ADR-0012 §Consequences committed to).
 *
 * Behavioral contract:
 *   1. THE REVIEWED GATE (spec FR-12/FR-20). `list()` returns ONLY rungs with
 *      `reviewed = true`. An ungated row MUST NEVER be served — `reviewed` is
 *      earned by the generator's verifier cascade (deterministic per-rung
 *      leakage check first), never asserted at serving time.
 *   2. READ-ONLY. There is deliberately NO write surface on this port:
 *      serving code must never be able to flip the gate. Rows are written by
 *      the generator/importer at the composition boundary (the seed path).
 *   3. `list()` returns the ladder ordered by `rung` ascending
 *      (probe → conceptual → directive) and `[]` (not throw) when the
 *      question has no reviewed rungs — the caller treats that as "no ladder"
 *      and falls back to a probing question, never a free-generated hint.
 *   4. At most one rung per level per `(question_id, choice_letter|null)`:
 *      the store enforces unique `(question_id, choice_letter, rung)`
 *      (ADR-0035). Default `choiceLetter` is null (Gen1 item-level ladder).
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface HintRepo {
  /**
   * One reviewed ladder, rung ascending; [] when none.
   * Omit `choiceLetter` (or pass null) for the item-level ladder.
   */
  list(
    subject: string,
    questionId: string,
    choiceLetter?: string | null,
  ): Promise<Hint[]>;
}
