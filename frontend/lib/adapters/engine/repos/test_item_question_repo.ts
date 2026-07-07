/**
 * TestItemQuestionRepo — the bank-backed `QuestionRepo` adapter (ADR-0021).
 *
 * Bridges the governed exam-item bank (ADR-0015's read-only `TestItemRepo`,
 * port 11) to the `QuestionRepo` shape the `FsrsScheduler` is bound to, so the
 * SAME scheduler (the sole `skill_state` writer) serves practice items from
 * the bank without touching the practice `question` table — the two repos
 * never cross, keeping ADR-0015 clause 1's exam-item leak structurally
 * unrepresentable.
 *
 * Behavioral contract (on top of the QuestionRepo port docs):
 *   1. REVIEWED, TWICE. `TestItemRepo.listReviewed` already gates; this
 *      adapter filters `reviewed === true` AGAIN (defense in depth — a
 *      regressed upstream seam must not reach a learner). BOTH `nextReviewed`
 *      and `get` are gated: unlike the practice repo (whose `get` serves
 *      admin/generation paths), the bank adapter serves learners only.
 *   2. READ-ONLY. `save()` throws `EngineRepoError` — serving code never
 *      writes the bank (the ADR-0014 posture); rows enter via the cascade
 *      seed path at the composition boundary.
 *   3. LOSSLESS MAP (spec FR-C4). Every `Question` field is populated from a
 *      real bank column (`stem_md` ↔ `Question.stem` is the one documented
 *      rename); nothing synthesized — bank feedback renders exactly like
 *      authored feedback.
 *   4. DETERMINISTIC PICK. Lowest difficulty, then id — mirrors
 *      `InMemoryEngineDb.nextReviewedQuestion` so the bank quiz is as
 *      reproducible as the dev-seed quiz was.
 *
 * Depends on the `TestItemRepo` PORT (injected — never a concrete sibling
 * adapter, Rule A2); constructed only at the composition roots (Rule C1/C2).
 */

import type { QuestionRepo } from "../../../ports/engine/question_repo";
import type { TestItemRepo } from "../../../ports/engine/test_item_repo";
import { EngineRepoError } from "../../../ports/engine/errors";
import type { Question, TestItem } from "../../../wire/engine_entities";

export class TestItemQuestionRepo implements QuestionRepo {
  constructor(
    private readonly bank: TestItemRepo,
    /** The one subject this bank serves (the bank read is subject-scoped). */
    private readonly subject: string,
  ) {}

  async nextReviewed(subject: string, skillId: string): Promise<Question | null> {
    const rows = await this.reviewedRows(subject);
    const candidates = rows.filter((r) => r.skill_id === skillId);
    candidates.sort(
      (a, b) => a.difficulty - b.difficulty || a.id.localeCompare(b.id),
    );
    const first = candidates[0];
    return first ? toQuestion(first) : null;
  }

  async get(id: string): Promise<Question | null> {
    // SUBJECT ASYMMETRY (deliberate, port-shaped): `nextReviewed` scopes by its
    // METHOD `subject` arg (the QuestionRepo signature), but the port's `get`
    // has no subject param, so it scopes by the CONSTRUCTOR subject. The two
    // agree only when callers pass the constructor's subject to `nextReviewed`
    // — true for the one composition-root wiring today (single-subject bank).
    // A second subject would want a per-subject adapter instance, not a wider
    // signature.
    const rows = await this.reviewedRows(this.subject);
    const row = rows.find((r) => r.id === id);
    return row ? toQuestion(row) : null;
  }

  async save(_question: Question): Promise<void> {
    // Read-only by contract: the bank is written only by the Python cascade's
    // seed path at the composition boundary, never by serving code.
    throw new EngineRepoError(
      "TestItemQuestionRepo is read-only: the bank is cascade-written (ADR-0021)",
    );
  }

  private async reviewedRows(subject: string): Promise<TestItem[]> {
    try {
      const rows = await this.bank.listReviewed(subject);
      // Defense in depth: re-assert the gate even though the port contracts it.
      return rows.filter((r) => r.reviewed === true);
    } catch (err) {
      if (err instanceof EngineRepoError) throw err;
      const detail = err instanceof Error ? err.message : String(err);
      throw new EngineRepoError(`bank question read failed: ${detail}`);
    }
  }
}

/** Lossless TestItem → Question map (FR-C4); `stem_md` ↔ `stem` documented. */
function toQuestion(item: TestItem): Question {
  return {
    id: item.id,
    subject: item.subject,
    skill_id: item.skill_id,
    difficulty: item.difficulty,
    context_html: item.context_html,
    stem: item.stem_md,
    choices: item.choices,
    answer_letter: item.answer_letter,
    per_choice_rationale: item.per_choice_rationale,
    why_correct_md: item.why_correct_md,
    why_tempted_md: item.why_tempted_md,
    rule_md: item.rule_md,
    item_type: item.item_type,
    reviewed: item.reviewed,
    generated_by: item.generated_by,
  };
}
