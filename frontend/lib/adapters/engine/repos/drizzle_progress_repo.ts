/**
 * DrizzleProgressRepo — the `ProgressRepo` adapter (ADR-0028).
 *
 * Read-only delegate to `EngineDb.listProgressPoints`. Returns [] (not throw)
 * when empty. Rejections → `EngineRepoError` (A5).
 */

import type { ProgressRepo } from "../../../ports/engine/progress_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { ProgressPoint } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleProgressRepo implements ProgressRepo {
  constructor(private readonly db: EngineDb) {}

  async list(subject: string, learnerId: string): Promise<ProgressPoint[]> {
    try {
      return await this.db.listProgressPoints(subject, learnerId);
    } catch (err) {
      throw translate("list", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`progress repo ${op} failed: ${detail}`);
}
