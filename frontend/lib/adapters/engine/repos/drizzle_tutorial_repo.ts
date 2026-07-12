/**
 * DrizzleTutorialRepo — the `TutorialRepo` adapter (ADR-0028).
 *
 * Carries the hard invariant (E1a FR-1): `getTutorial()` serves a row ONLY when
 * it is BOTH `reviewed=true` AND stamped with earned provenance — a
 * `generated_from` that matches the confinement format (`hand:<author>@<date>`
 * or `llm:<model>@<promptrev>`). Defense-in-depth at the serve seam so a forged
 * stamp that somehow reached the store is still never handed to a learner,
 * mirroring the `DrizzleHintRepo` reviewed filter. Build-time, the same format
 * is gated by `tests/architecture/test_tutorial_provenance_confinement.py`
 * (FR-2) — this is the serve-time twin, not a replacement.
 * Read-only: writes happen at the composition boundary (seed), never through
 * this port. Rejections → `EngineRepoError` (A5).
 */

import type { TutorialRepo } from "../../../ports/engine/tutorial_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { Tutorial } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

// hand:<author>@<date> | llm:<model>@<promptrev> — mirror of the _LEGITIMATE
// pattern in tests/architecture/test_tutorial_provenance_confinement.py.
const EARNED_PROVENANCE = /^(?:hand|llm):[^@\s]+@[^@\s]+$/;

export class DrizzleTutorialRepo implements TutorialRepo {
  constructor(private readonly db: EngineDb) {}

  async getTutorial(subject: string, skillId: string): Promise<Tutorial | null> {
    try {
      const row = await this.db.getTutorial(subject, skillId);
      // Defense in depth: never hand a learner an unreviewed tutorial, nor a
      // reviewed row carrying a stamp that did not earn `reviewed` (FR-1).
      if (row == null || row.reviewed !== true) return null;
      if (!EARNED_PROVENANCE.test(row.generated_from)) return null;
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
