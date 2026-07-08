/**
 * DrizzleQuestionRepo — the `QuestionRepo` adapter (ADR-0006 #2).
 *
 * Carries the engine's hard invariant: `nextReviewed()` returns `reviewed=true`
 * ONLY (engine spec FR-B*). The reviewed filter is pushed into
 * `EngineDb.nextReviewedQuestion` so BOTH the in-memory fake and the live seam
 * enforce it identically, and the conformance suite asserts it against both.
 * `get(id)` is the non-learner path and may return an unreviewed row. This repo
 * never grades (that is the `Grader`). Rejections → `EngineRepoError` (A5).
 */

import type { QuestionRepo } from "../../../ports/engine/question_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { Question } from "../../../wire/engine_entities";
import type { EngineDb } from "../db/engine_db";

export class DrizzleQuestionRepo implements QuestionRepo {
  constructor(private readonly db: EngineDb) {}

  async nextReviewed(
    subject: string,
    skillId: string,
    excludeIds?: readonly string[],
  ): Promise<Question | null> {
    try {
      const q = await this.db.nextReviewedQuestion(subject, skillId, excludeIds);
      // Defense in depth: the gate is enforced in the store, but a repo must
      // never hand a learner an unreviewed item even if a seam regressed.
      if (q && q.reviewed !== true) return null;
      return q;
    } catch (err) {
      throw translate("nextReviewed", err);
    }
  }

  async get(id: string): Promise<Question | null> {
    try {
      return await this.db.getQuestion(id);
    } catch (err) {
      throw translate("get", err);
    }
  }

  async save(question: Question): Promise<void> {
    try {
      await this.db.insertQuestion(question);
    } catch (err) {
      throw translate("save", err);
    }
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`question repo ${op} failed: ${detail}`);
}
