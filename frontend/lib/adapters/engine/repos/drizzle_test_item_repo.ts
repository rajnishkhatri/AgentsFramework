/**
 * DrizzleTestItemRepo — the `TestItemRepo` adapter (ADR-0015).
 *
 * Carries the reviewed gate: `listReviewed()` returns `reviewed=true` rows ONLY
 * (spec FR-27.1). The filter is pushed into `EngineDb.listReviewedTestItems` so
 * BOTH the in-memory fake and the live seam enforce it identically (the
 * `nextReviewedQuestion` posture), and the repo re-checks it as defense in
 * depth. Read-only: writes happen at the composition boundary (the seed/
 * generator path), never through this port. Rejections → `EngineRepoError`.
 */

import type { TestItemRepo } from "../../../ports/engine/test_item_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { TestItem } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleTestItemRepo implements TestItemRepo {
  constructor(private readonly db: EngineDb) {}

  async listReviewed(subject: string): Promise<TestItem[]> {
    try {
      const items = await this.db.listReviewedTestItems(subject);
      // Defense in depth: the gate is in the store, but the repo must never
      // hand a caller an unreviewed exam item even if a seam regressed.
      return items.filter((i) => i.reviewed === true);
    } catch (err) {
      throw translate("listReviewed", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`test_item repo ${op} failed: ${detail}`);
}
