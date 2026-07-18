/**
 * DrizzleHintRepo — the `HintRepo` adapter (ADR-0014).
 *
 * Carries the ladder's hard invariant: `list()` returns `reviewed=true` rungs
 * ONLY (spec FR-12/FR-20). The reviewed filter is pushed into
 * `EngineDb.listReviewedHints` so BOTH the in-memory fake and the live seam
 * enforce it identically (the `nextReviewedQuestion` posture), and the repo
 * re-checks it as defense in depth. Read-only: writes happen at the
 * composition boundary (seed/generator), never through this port.
 * Rejections → `EngineRepoError` (A5).
 */

import type { HintRepo } from "../../../ports/engine/hint_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { Hint } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleHintRepo implements HintRepo {
  constructor(private readonly db: EngineDb) {}

  async list(
    subject: string,
    questionId: string,
    choiceLetter?: string | null,
  ): Promise<Hint[]> {
    try {
      const rungs = await this.db.listReviewedHints(
        subject,
        questionId,
        choiceLetter,
      );
      // Defense in depth: the gate is enforced in the store, but the repo
      // must never hand a learner an unreviewed rung even if a seam regressed.
      return rungs.filter((h) => h.reviewed === true);
    } catch (err) {
      throw translate("list", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`hint repo ${op} failed: ${detail}`);
}
