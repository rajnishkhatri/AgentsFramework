/**
 * DrizzleLearnerReadRepo — the `LearnerReadRepo` adapter (ADR-0011).
 *
 * Read-only. It depends on the narrow `ReadableEngineDb` projection, NOT the full
 * `EngineDb` — so `upsertSkillState` (the Scheduler's write, FR-A2) is not even
 * in scope here; read-only is compiler-enforced, not asserted in prose (ADR-0011
 * §Decision). Rejections → `EngineRepoError` (Rule A5), mirroring the sibling
 * repos. No id/clock is owned (a pure read).
 */

import type { LearnerReadRepo } from "../../../ports/engine/learner_read_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { SkillState } from "../../../wire/engine_entities";
import type { ReadableEngineDb } from "../db/engine_db";

export class DrizzleLearnerReadRepo implements LearnerReadRepo {
  private readonly db: ReadableEngineDb;

  constructor(db: ReadableEngineDb) {
    this.db = db;
  }

  async listSkillState(
    subject: string,
    learnerId: string,
  ): Promise<SkillState[]> {
    try {
      return await this.db.listSkillState(subject, learnerId);
    } catch (err) {
      throw translate("listSkillState", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`learner read repo ${op} failed: ${detail}`);
}
