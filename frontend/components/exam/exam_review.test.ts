/**
 * S-D2 — exam review VM (FR-25 / FR-29).
 * Bookmark + to-revise filter (flagged ∪ bookmarked ∪ wrong).
 */

import { describe, expect, it } from "vitest";
import type { ExamQuestion, ExamRunItem } from "@/lib/wire/exam_entities";
import {
  buildExamReview,
  filterExamReview,
  isToRevise,
  toExamReviewItem,
} from "./exam_review";

function question(over: Partial<ExamQuestion> = {}): ExamQuestion {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-punct",
    difficulty: 2,
    context_html: "ctx",
    stem: "stem",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "b", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: { B: "tempted by B" },
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    reporting_category: null,
    scored: true,
    passage: null,
    ...over,
  };
}

function item(over: Partial<ExamRunItem> = {}): ExamRunItem {
  return {
    run_id: "run-1",
    section_code: "english",
    question_id: "q-1",
    ordinal: 0,
    chosen_letter: "B",
    correct: false,
    dwell_ms: 1200,
    visits: 2,
    answer_changes: 1,
    first_answered_at: "2026-09-02T12:00:01.000Z",
    dwell_at_first_answer_ms: 400,
    flagged_in_section: false,
    bookmarked: false,
    updated_at: "2026-09-02T12:00:02.000Z",
    ...over,
  };
}

describe("exam_review (FR-25 / FR-29)", () => {
  it("exposes answer, correct letter, rationale, dwell, visits, changes, flag, bookmark", () => {
    const vm = toExamReviewItem(
      question(),
      item({ flagged_in_section: true, bookmarked: true }),
    );
    expect(vm.chosenLetter).toBe("B");
    expect(vm.correctLetter).toBe("A");
    expect(vm.correct).toBe(false);
    expect(vm.rationale).toBe("tempted by B");
    expect(vm.dwellMs).toBe(1200);
    expect(vm.visits).toBe(2);
    expect(vm.answerChanges).toBe(1);
    expect(vm.flagged).toBe(true);
    expect(vm.bookmarked).toBe(true);
  });

  it("to-revise is flagged ∪ bookmarked ∪ wrong; filters by each", () => {
    const flagged = toExamReviewItem(
      question({ id: "q-flag" }),
      item({
        question_id: "q-flag",
        chosen_letter: "A",
        correct: true,
        flagged_in_section: true,
      }),
    );
    const bookmarked = toExamReviewItem(
      question({ id: "q-book" }),
      item({
        question_id: "q-book",
        chosen_letter: "A",
        correct: true,
        bookmarked: true,
      }),
    );
    const wrong = toExamReviewItem(question({ id: "q-wrong" }), item({ question_id: "q-wrong" }));
    const clean = toExamReviewItem(
      question({ id: "q-ok" }),
      item({
        question_id: "q-ok",
        chosen_letter: "A",
        correct: true,
      }),
    );
    expect(isToRevise(flagged)).toBe(true);
    expect(isToRevise(bookmarked)).toBe(true);
    expect(isToRevise(wrong)).toBe(true);
    expect(isToRevise(clean)).toBe(false);
    const all = [flagged, bookmarked, wrong, clean];
    expect(filterExamReview(all, "flagged").map((i) => i.questionId)).toEqual([
      "q-flag",
    ]);
    expect(filterExamReview(all, "bookmarked").map((i) => i.questionId)).toEqual([
      "q-book",
    ]);
    expect(filterExamReview(all, "wrong").map((i) => i.questionId)).toEqual([
      "q-wrong",
    ]);
    expect(buildExamReview(
      [question({ id: "q-flag" }), question({ id: "q-ok" })],
      [
        item({ question_id: "q-flag", flagged_in_section: true, chosen_letter: "A", correct: true }),
        item({ question_id: "q-ok", chosen_letter: "A", correct: true }),
      ],
      "flagged",
    ).items).toHaveLength(1);
  });
});
