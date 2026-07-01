/** SkillTaxonomy port (ADR-0006 #1) — read-only subject skill buckets. */

import type { Skill } from "../../wire/engine_entities";

/**
 * SkillTaxonomy — read-only access to the subject's skill buckets (ADR-0006 #1).
 *
 * Behavioral contract:
 *   1. READ-ONLY. This port never exposes or writes mastery — mastery lives in
 *      `skill_state` and is the `Scheduler`'s concern (engine spec FR-A2). A
 *      `Skill` returned here carries taxonomy + weighting only.
 *   2. `get()` resolves a skill by its stable `key` ('punctuation', ...), not by
 *      uuid, because content + code reference skills by key.
 *   3. `list()` returns the buckets in display `order` (FR for the mastery grid).
 *   4. All values returned are `wire/engine_entities` shapes — no Drizzle row
 *      type escapes the adapter (Rule A4 / F-R8).
 *
 * @throws EngineRepoError on persistence failure.
 * @throws EngineNotFoundError from `get()` when no skill has the given key.
 */
export interface SkillTaxonomy {
  /** All skills for a subject, ordered by display `order`. */
  list(subject: string): Promise<Skill[]>;

  /** One skill by its stable `key`. */
  get(subject: string, skillKey: string): Promise<Skill>;
}
