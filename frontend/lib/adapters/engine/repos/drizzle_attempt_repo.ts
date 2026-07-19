/**
 * DrizzleAttemptRepo — the `AttemptRepo` adapter (ADR-0006 #3).
 *
 * Append-only. `record()` assigns `id` + `created_at` (the engine-owned fields)
 * and inserts; it never updates correctness, and `used_hint` is persisted as-is
 * without affecting `correct` (FR-D5). `misses()` returns outstanding misses
 * (latest attempt per question is incorrect), newest-first (FR-D4). Rejections
 * → `EngineRepoError` (A5).
 *
 * Id + clock: this adapter owns both (an attempt is a persisted event, so a
 * non-deterministic id/timestamp is correct here — unlike the pure Grader). They
 * are injected via the constructor so tests are deterministic.
 */

import type { AttemptRepo } from "../../../ports/engine/attempt_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type {
  AccuracyBySkill,
  Attempt,
  AttemptInput,
} from "../../../wire/engine_entities";
import { toAccuracyVM } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";
import { newUuid } from "../../../new_uuid";

export type AttemptRepoDeps = {
  db: EngineDb;
  /** Defaults to `newUuid` (LAN-HTTP-safe); injectable for deterministic tests. */
  newId?: () => string;
  /** Defaults to () => new Date(); injectable for deterministic tests. */
  now?: () => Date;
};

export class DrizzleAttemptRepo implements AttemptRepo {
  private readonly db: EngineDb;
  private readonly newId: () => string;
  private readonly now: () => Date;

  constructor(deps: AttemptRepoDeps) {
    this.db = deps.db;
    this.newId = deps.newId ?? newUuid;
    this.now = deps.now ?? (() => new Date());
  }

  async record(attempt: AttemptInput): Promise<Attempt> {
    const row: Attempt = {
      ...attempt,
      id: this.newId(),
      created_at: this.now().toISOString(),
    };
    try {
      await this.db.insertAttempt(row);
    } catch (err) {
      throw translate("record", err);
    }
    return row;
  }

  async misses(subject: string, learnerId: string): Promise<Attempt[]> {
    try {
      return await this.db.listMisses(subject, learnerId);
    } catch (err) {
      throw translate("misses", err);
    }
  }

  async servedQuestionIds(sessionId: string): Promise<readonly string[]> {
    try {
      return await this.db.listSessionQuestionIds(sessionId);
    } catch (err) {
      throw translate("servedQuestionIds", err);
    }
  }

  async listForSession(sessionId: string): Promise<readonly Attempt[]> {
    try {
      return await this.db.listSessionAttempts(sessionId);
    } catch (err) {
      throw translate("listForSession", err);
    }
  }

  async servedSkillIds(sessionId: string): Promise<readonly string[]> {
    try {
      return await this.db.listSessionSkillIds(sessionId);
    } catch (err) {
      throw translate("servedSkillIds", err);
    }
  }

  async accuracyBySkill(
    subject: string,
    learnerId: string,
    skillId: string,
    opts?: { sessions?: number },
  ): Promise<AccuracyBySkill> {
    const sessions = opts?.sessions ?? 6;
    try {
      return toAccuracyVM(
        await this.db.accuracyRowsBySkill(subject, learnerId, skillId, sessions),
      );
    } catch (err) {
      throw translate("accuracyBySkill", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`attempt repo ${op} failed: ${detail}`);
}
