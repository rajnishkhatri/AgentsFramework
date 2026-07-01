/**
 * DrizzleSessionRepo — the `SessionRepo` adapter (ADR-0006 #4).
 *
 * Session lifecycle + scoring tally only. `open()` creates the row with
 * `started_at = now`, `ended_at = null`, `score_* = 0` (FR-D1). `close()` sets
 * `ended_at` + the stored tally (FR-D3) and is idempotent — re-closing applies
 * the same patch without error. The UI Summary reads the STORED tally, never a
 * recompute. Rejections → `EngineRepoError` (A5).
 *
 * Id + clock are injected (constructor) so tests are deterministic; a session is
 * a persisted event so a non-deterministic id/timestamp is correct here.
 */

import type { SessionRepo, SessionScore } from "../../../ports/engine/session_repo";
import { EngineNotFoundError, EngineRepoError } from "../../../ports/engine/errors";
import type { QuizSession, SessionMode } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export type SessionRepoDeps = {
  db: EngineDb;
  newId?: () => string;
  now?: () => Date;
};

export class DrizzleSessionRepo implements SessionRepo {
  private readonly db: EngineDb;
  private readonly newId: () => string;
  private readonly now: () => Date;

  constructor(deps: SessionRepoDeps) {
    this.db = deps.db;
    this.newId = deps.newId ?? (() => crypto.randomUUID());
    this.now = deps.now ?? (() => new Date());
  }

  async open(
    subject: string,
    learnerId: string,
    mode: SessionMode,
    focus?: string | null,
  ): Promise<QuizSession> {
    const row: QuizSession = {
      id: this.newId(),
      subject,
      learner_id: learnerId,
      mode,
      skill_focus: focus ?? null,
      started_at: this.now().toISOString(),
      ended_at: null,
      score_correct: 0,
      score_total: 0,
    };
    try {
      await this.db.insertSession(row);
    } catch (err) {
      throw translate("open", err);
    }
    return row;
  }

  async close(id: string, score: SessionScore): Promise<QuizSession> {
    let updated: QuizSession | null;
    try {
      updated = await this.db.patchSessionClose(id, {
        ended_at: this.now().toISOString(),
        score_correct: score.score_correct,
        score_total: score.score_total,
      });
    } catch (err) {
      throw translate("close", err);
    }
    if (!updated) {
      throw new EngineNotFoundError(`no session '${id}' to close`);
    }
    return updated;
  }

  async get(id: string): Promise<QuizSession | null> {
    try {
      return await this.db.getSession(id);
    } catch (err) {
      throw translate("get", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`session repo ${op} failed: ${detail}`);
}
