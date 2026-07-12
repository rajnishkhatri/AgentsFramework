/**
 * DrizzleTutorialRepo — the `TutorialRepo` adapter (ADR-0028).
 *
 * Carries the hard invariant: `getTutorial()` returns a `reviewed=true` row
 * ONLY (E1a FR-1). Defense-in-depth filter even if the store seam regresses.
 * Read-only: writes happen at the composition boundary (seed), never through
 * this port. Rejections → `EngineRepoError` (A5).
 */

import type { TutorialRepo } from "../../../ports/engine/tutorial_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { Tutorial } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleTutorialRepo implements TutorialRepo {
  constructor(private readonly db: EngineDb) {}

  async getTutorial(subject: string, skillId: string): Promise<Tutorial | null> {
    try {
      const row = await this.db.getTutorial(subject, skillId);
      // Defense in depth: never hand a learner an unreviewed tutorial.
      if (row == null || row.reviewed !== true) return null;
      return row;
    } catch (err) {
      throw translate("getTutorial", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`tutorial repo ${op} failed: ${detail}`);
}
