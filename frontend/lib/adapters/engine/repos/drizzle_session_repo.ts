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
import type { ContentRepo } from "../../../ports/engine/content_repo";
import { EngineNotFoundError, EngineRepoError } from "../../../ports/engine/errors";
import type { QuizSession, SessionMode } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";
import { newUuid } from "../../../new_uuid";

/**
 * The flat per-mode default length (S3, spec FR-5): 30 for every mode. It is the
 * fallback when the `content_string` policy row is absent — the policy lives in
 * data (`session.target_count.<mode>`), this constant is the honest floor so a
 * missing row never persists a NaN or the echoed key-string as a length.
 */
const DEFAULT_TARGET_COUNT = 30;

/** `session.target_count.adaptive` | `.drill` | `.review` — the policy key. */
function targetCountKey(mode: SessionMode): string {
  return `session.target_count.${mode}`;
}

export type SessionRepoDeps = {
  db: EngineDb;
  /**
   * Resolves the per-mode default `target_count` from the `content_string`
   * policy plane (FR-5). Optional: without it, `open()` (called with no explicit
   * target) falls back to the flat `DEFAULT_TARGET_COUNT` constant.
   */
  contentRepo?: ContentRepo;
  newId?: () => string;
  now?: () => Date;
};

export class DrizzleSessionRepo implements SessionRepo {
  private readonly db: EngineDb;
  private readonly contentRepo: ContentRepo | undefined;
  private readonly newId: () => string;
  private readonly now: () => Date;

  constructor(deps: SessionRepoDeps) {
    this.db = deps.db;
    this.contentRepo = deps.contentRepo;
    this.newId = deps.newId ?? newUuid;
    this.now = deps.now ?? (() => new Date());
  }

  async open(
    subject: string,
    learnerId: string,
    mode: SessionMode,
    focus?: string | null,
    targetCount?: number | null,
  ): Promise<QuizSession> {
    // Three-way per FR-5/6: OMITTED (undefined) → resolve the policy default;
    // an explicit value or `null` (endless) → persist verbatim, never override.
    const resolvedTarget =
      targetCount === undefined
        ? await this.resolveDefaultTarget(subject, mode)
        : targetCount;
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
      target_count: resolvedTarget,
    };
    try {
      await this.db.insertSession(row);
    } catch (err) {
      throw translate("open", err);
    }
    return row;
  }

  /**
   * The per-mode default (FR-5): read `session.target_count.<mode>` from the
   * content plane and parse it as a positive int. On a miss the ContentRepo
   * echoes the key back (non-numeric) → fall back to `DEFAULT_TARGET_COUNT`.
   * With no ContentRepo injected, use the constant directly.
   */
  private async resolveDefaultTarget(
    subject: string,
    mode: SessionMode,
  ): Promise<number> {
    if (!this.contentRepo) return DEFAULT_TARGET_COUNT;
    let raw: string;
    try {
      raw = await this.contentRepo.text(subject, targetCountKey(mode));
    } catch {
      // A content-plane failure must not block opening a session; use the floor.
      return DEFAULT_TARGET_COUNT;
    }
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : DEFAULT_TARGET_COUNT;
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

  async listByLearner(
    subject: string,
    learnerId: string,
    options?: { sinceISO?: string },
  ): Promise<QuizSession[]> {
    try {
      return await this.db.listClosedSessionsByLearner(subject, learnerId, options);
    } catch (err) {
      throw translate("listByLearner", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`session repo ${op} failed: ${detail}`);
}
