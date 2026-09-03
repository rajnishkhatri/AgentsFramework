/**
 * C-4 — ExamReviewView unscored badge + post-grade correct reveal
 * (FR-P2-18, FR-P2-9).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ExamReviewView } from "./ExamReviewView";
import type { ExamReviewItemVM } from "./exam_review";

const noop = (): void => undefined;

function reviewItem(
  over: Partial<ExamReviewItemVM> = {},
): ExamReviewItemVM {
  return {
    questionId: "q-1",
    ordinal: 0,
    stem: "stem",
    contextHtml: "ctx",
    choices: [
      { letter: "A", label: "a" },
      { letter: "B", label: "b" },
    ],
    chosenLetter: "B",
    correctLetter: "A",
    correct: false,
    rationale: null,
    dwellMs: 1000,
    visits: 1,
    answerChanges: 0,
    flagged: false,
    bookmarked: false,
    scored: true,
    ...over,
  };
}

function renderDoc(items: readonly ExamReviewItemVM[]): Document {
  const html = renderToStaticMarkup(
    React.createElement(ExamReviewView, {
      title: "English",
      items,
      filter: "all",
      onFilter: noop,
      onToggleBookmark: noop,
    }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("ExamReviewView (C-4 / FR-P2-18, FR-P2-9)", () => {
  it("shows an unscored (field-test) badge on unscored items", () => {
    const doc = renderDoc([
      reviewItem({ questionId: "q-ft", scored: false }),
      reviewItem({ questionId: "q-s", scored: true }),
    ]);
    const badge = doc.querySelector('[data-testid="exam-review-unscored-q-ft"]');
    expect(badge?.textContent).toMatch(/unscored \(field-test\)/i);
    expect(
      doc.querySelector('[data-testid="exam-review-unscored-q-s"]'),
    ).toBeNull();
  });

  it("excludes unscored items from the score summary", () => {
    const doc = renderDoc([
      reviewItem({
        questionId: "q-s",
        scored: true,
        chosenLetter: "A",
        correctLetter: "A",
        correct: true,
      }),
      reviewItem({
        questionId: "q-ft",
        scored: false,
        chosenLetter: "A",
        correctLetter: "A",
        correct: true,
      }),
    ]);
    const summary = doc.querySelector('[data-testid="exam-review-score-summary"]');
    expect(summary?.textContent).toMatch(/1\/1/);
    expect(summary?.textContent).not.toMatch(/2\/2/);
  });

  it("shows the correct letter only when present (post-grade)", () => {
    const graded = renderDoc([
      reviewItem({ questionId: "q-g", correctLetter: "C" }),
    ]);
    expect(
      graded.querySelector('[data-testid="exam-review-answer-q-g"]')
        ?.textContent,
    ).toContain("Correct: C");

    const preGrade = renderDoc([
      reviewItem({
        questionId: "q-p",
        correctLetter: null,
        correct: null,
      }),
    ]);
    const line = preGrade.querySelector(
      '[data-testid="exam-review-answer-q-p"]',
    )?.textContent;
    expect(line).not.toMatch(/Correct:/);
    expect(line).toContain("Your answer:");
  });
});
