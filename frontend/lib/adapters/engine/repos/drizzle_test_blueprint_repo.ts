/**
 * DrizzleTestBlueprintRepo — the `TestBlueprintRepo` adapter (ADR-0015).
 *
 * `get()` returns the blueprint or `null` for an unknown id (config error, not
 * an exception). Read-only: blueprints are authored/seeded at the composition
 * boundary, never mutated through this port. Rejections → `EngineRepoError`.
 */

import type { TestBlueprintRepo } from "../../../ports/engine/test_blueprint_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { TestBlueprint } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleTestBlueprintRepo implements TestBlueprintRepo {
  constructor(private readonly db: EngineDb) {}

  async get(id: string): Promise<TestBlueprint | null> {
    try {
      return await this.db.getTestBlueprint(id);
    } catch (err) {
      throw translate("get", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`test_blueprint repo ${op} failed: ${detail}`);
}
