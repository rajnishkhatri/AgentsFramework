/**
 * DrizzleSkillTaxonomy — the `SkillTaxonomy` adapter (ADR-0006 #1).
 *
 * Written against the narrow `EngineDb` port (not the Drizzle client directly),
 * so it is unit-testable with `InMemoryEngineDb` and the live SDK seam feeds the
 * same class unchanged. Read-only: it never touches mastery (that is
 * `skill_state` / the Scheduler, FR-A2). Any backing-store rejection is
 * translated to `EngineRepoError` (Rule A5); a missing skill from `get()` is an
 * `EngineNotFoundError`.
 */

import type { SkillTaxonomy } from "../../../ports/engine/skill_taxonomy";
import { EngineNotFoundError, EngineRepoError } from "../../../ports/engine/errors";
import type { Skill } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleSkillTaxonomy implements SkillTaxonomy {
  constructor(private readonly db: EngineDb) {}

  async list(subject: string): Promise<Skill[]> {
    try {
      return await this.db.listSkills(subject);
    } catch (err) {
      throw translate("list", err);
    }
  }

  async get(subject: string, skillKey: string): Promise<Skill> {
    let skill: Skill | null;
    try {
      skill = await this.db.getSkillByKey(subject, skillKey);
    } catch (err) {
      throw translate("get", err);
    }
    if (!skill) {
      throw new EngineNotFoundError(
        `no skill '${skillKey}' for subject '${subject}'`,
      );
    }
    return skill;
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`skill taxonomy ${op} failed: ${detail}`);
}
