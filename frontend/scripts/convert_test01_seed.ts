/**
 * Test-01 → governed-bank seed demotion (Phase 6 — ADR-0015 clause 6, FR-25).
 *
 * The converter's parser (`parseTest01English`) and its frozen serving corpus
 * (`_test01_english_corpus.ts`) are UNCHANGED — this is a separate, additive
 * seed-emission that feeds the governed bank, not the client bundle (FR-25.3).
 *
 * A parsed `Question` self-stamps `reviewed:true` / `generated_by:"test01-
 * convert"`; the seed row RETROACTIVELY UNEARNS that: it enters at
 * `reviewed=false` with `generated_by="test01-import"` (FR-25.1/25.2). `reviewed`
 * is then earned only by the Python cascade (`scripts/promote_test_item_seed.py`),
 * which re-stamps `generated_by="<model>@<run_id>"` on promotion — so
 * "test01-import" never rides a reviewed=true row.
 *
 * TEACHING FIELDS CARRIED THROUGH (ADR-0021 — reverses the original "dead
 * weight" drop). The bank now also serves the PRACTICE quiz via the
 * `TestItemQuestionRepo` adapter, and the Feedback screen renders
 * `per_choice_rationale` + `rule_md` — so the parsed `Question`'s teaching
 * payload maps into the seed row losslessly. Without this the seed would
 * quarantine at the cascade's schema stage (fail-closed).
 *
 * Pure: `(Question[]) -> TestItem[]`, no I/O.
 */

import type { Question, TestItem } from "../lib/wire/engine_entities";

export const TEST01_IMPORT_PROVENANCE = "test01-import";

export function toTestItemSeed(questions: readonly Question[]): TestItem[] {
  return questions.map((q) => ({
    id: q.id,
    subject: q.subject,
    skill_id: q.skill_id,
    difficulty: q.difficulty,
    context_html: q.context_html,
    stem_md: q.stem,
    choices: q.choices,
    answer_letter: q.answer_letter,
    // Teaching payload (ADR-0021): lossless into the bank — the practice
    // Feedback screen renders these on bank-served items.
    per_choice_rationale: q.per_choice_rationale,
    why_correct_md: q.why_correct_md,
    why_tempted_md: q.why_tempted_md,
    rule_md: q.rule_md,
    item_type: q.item_type,
    misconception: q.misconception ?? null,
    // Demotion (FR-25.1): the converter's self-stamp is unearned; the cascade
    // is the sole reviewer for imported items just as for generated ones.
    reviewed: false,
    generated_by: TEST01_IMPORT_PROVENANCE,
  }));
}
