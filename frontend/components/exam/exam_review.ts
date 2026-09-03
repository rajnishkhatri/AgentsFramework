/**
 * Pure FR-25 / FR-29 review VM. Filterable to-revise = flagged ∪ bookmarked ∪ wrong.
 */

import type { ExamQuestion, ExamRunItem } from "@/lib/wire/exam_entities";

export type ExamReviewFilter = "all" | "flagged" | "bookmarked" | "wrong";

export type ExamReviewItemVM = {
  readonly questionId: string;
  readonly ordinal: number;
  readonly stem: string;
  readonly contextHtml: string;
  readonly choices: readonly { letter: string; label: string }[];
  readonly chosenLetter: string | null;
  /** Present only post-grade (or client-bundled Test-01). Null pre-grade. */
  readonly correctLetter: string | null;
  readonly correct: boolean | null;
  readonly rationale: string | null;
  readonly dwellMs: number;
  readonly visits: number;
  readonly answerChanges: number;
  readonly flagged: boolean;
  readonly bookmarked: boolean;
  readonly scored: boolean;
};

export type ExamReviewScoreSummary = {
  readonly scoredCorrect: number;
  readonly scoredTotal: number;
  readonly unscoredCount: number;
};

export type ExamReviewVM = {
  readonly items: readonly ExamReviewItemVM[];
  readonly filter: ExamReviewFilter;
};

export function toExamReviewItem(
  question: ExamQuestion,
  item: ExamRunItem,
): ExamReviewItemVM {
  const chosen = item.chosen_letter;
  const rationale =
    chosen == null ? null : (question.per_choice_rationale[chosen] ?? null);
  // Empty/absent key = asset-served pre-grade (FR-P2-9). Do not fabricate.
  const answerLetter =
    question.answer_letter === "" ? null : question.answer_letter;
  // FR-29: the live client review builds from ungraded reducer items (correct=null),
  // so derive correctness from the answer key when a stored verdict is absent. An
  // authoritative graded verdict, when present, still wins (`??` keeps a stored
  // `false`). Unanswered ⇒ null (never "wrong"), matching the grader (no selection
  // ⇒ no verdict) — otherwise the Wrong filter is empty even for wrong answers.
  // Pre-grade asset-served (no key) also stays null — do not derive.
  const correct =
    item.correct ??
    (chosen == null || answerLetter == null ? null : chosen === answerLetter);
  return {
    questionId: question.id,
    ordinal: item.ordinal,
    stem: question.stem,
    contextHtml: question.context_html,
    choices: question.choices.map((c) => ({ letter: c.letter, label: c.label })),
    chosenLetter: chosen,
    correctLetter: answerLetter,
    correct,
    rationale,
    dwellMs: item.dwell_ms,
    visits: item.visits,
    answerChanges: item.answer_changes,
    flagged: item.flagged_in_section,
    bookmarked: item.bookmarked,
    scored: question.scored,
  };
}

/** Scored items only — field-test rows stay in review, not in the tally (FR-P2-18). */
export function reviewScoreSummary(
  items: readonly ExamReviewItemVM[],
): ExamReviewScoreSummary {
  let scoredCorrect = 0;
  let scoredTotal = 0;
  let unscoredCount = 0;
  for (const row of items) {
    if (!row.scored) {
      unscoredCount += 1;
      continue;
    }
    scoredTotal += 1;
    if (row.correct === true) scoredCorrect += 1;
  }
  return { scoredCorrect, scoredTotal, unscoredCount };
}

export function isToRevise(item: ExamReviewItemVM): boolean {
  return item.flagged || item.bookmarked || item.correct === false;
}

export function filterExamReview(
  items: readonly ExamReviewItemVM[],
  filter: ExamReviewFilter,
): readonly ExamReviewItemVM[] {
  if (filter === "all") return items;
  if (filter === "flagged") return items.filter((i) => i.flagged);
  if (filter === "bookmarked") return items.filter((i) => i.bookmarked);
  return items.filter((i) => i.correct === false);
}

export function buildExamReview(
  questions: readonly ExamQuestion[],
  items: readonly ExamRunItem[],
  filter: ExamReviewFilter,
): ExamReviewVM {
  const byId = new Map(items.map((i) => [i.question_id, i]));
  const rows = questions
    .map((q, index) => {
      const stored = byId.get(q.id);
      if (stored == null) return null;
      return toExamReviewItem(q, { ...stored, ordinal: stored.ordinal || index });
    })
    .filter((row): row is ExamReviewItemVM => row != null);
  return { items: filterExamReview(rows, filter), filter };
}
