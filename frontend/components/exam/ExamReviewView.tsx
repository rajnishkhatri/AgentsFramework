/**
 * ExamReviewView — finished-section review + bookmark + to-revise filters (FR-25/29).
 */

"use client";

import * as React from "react";
import {
  reviewScoreSummary,
  type ExamReviewFilter,
  type ExamReviewItemVM,
} from "./exam_review";

export interface ExamReviewViewProps {
  readonly title: string;
  readonly items: readonly ExamReviewItemVM[];
  readonly filter: ExamReviewFilter;
  readonly onFilter: (filter: ExamReviewFilter) => void;
  readonly onToggleBookmark: (questionId: string, bookmarked: boolean) => void;
}

const FILTERS: readonly { id: ExamReviewFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "flagged", label: "Flagged" },
  { id: "bookmarked", label: "Bookmarked" },
  { id: "wrong", label: "Wrong" },
];

export function ExamReviewView(props: ExamReviewViewProps): React.JSX.Element {
  const summary = reviewScoreSummary(props.items);
  return (
    <section
      data-testid="exam-review"
      aria-label="Section review"
      className="mx-auto flex max-w-[760px] flex-col gap-5"
    >
      <header>
        <h1 className="text-xl font-semibold text-fg">{props.title} review</h1>
        <p
          data-testid="exam-review-score-summary"
          className="mt-1 text-sm text-muted"
        >
          {summary.scoredCorrect}/{summary.scoredTotal} scored
          {summary.unscoredCount > 0
            ? ` · ${summary.unscoredCount} field-test`
            : ""}
        </p>
      </header>
      <div
        data-testid="exam-review-filters"
        role="tablist"
        aria-label="To revise"
        className="inline-flex flex-wrap gap-1 rounded-full bg-selected p-1"
      >
        {FILTERS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={props.filter === tab.id}
            data-testid={`exam-review-filter-${tab.id}`}
            onClick={() => props.onFilter(tab.id)}
            className="rounded-full px-4 py-1.5 text-sm font-medium aria-selected:bg-surface aria-selected:shadow-sm"
          >
            {tab.label}
          </button>
        ))}
      </div>
      <ol className="flex flex-col gap-4">
        {props.items.map((item) => (
          <li
            key={item.questionId}
            data-testid={`exam-review-item-${item.questionId}`}
            className="rounded-[13px] border border-border p-4"
          >
            <p
              className="text-[1.1rem] leading-7"
              dangerouslySetInnerHTML={{ __html: item.contextHtml }}
            />
            <p className="mt-2 font-medium">{item.stem}</p>
            {!item.scored ? (
              <p
                data-testid={`exam-review-unscored-${item.questionId}`}
                className="mt-2 text-xs font-medium uppercase tracking-wide text-muted"
              >
                unscored (field-test)
              </p>
            ) : null}
            <p data-testid={`exam-review-answer-${item.questionId}`} className="mt-2 text-sm">
              Your answer: {item.chosenLetter ?? "unanswered"}
              {item.correctLetter != null ? ` · Correct: ${item.correctLetter}` : ""}
            </p>
            {item.rationale ? (
              <p className="mt-1 text-sm text-muted">{item.rationale}</p>
            ) : null}
            <p className="mt-2 text-xs text-muted">
              dwell {Math.round(item.dwellMs / 1000)}s · visits {item.visits} ·
              changes {item.answerChanges}
              {item.flagged ? " · flagged" : ""}
            </p>
            <button
              type="button"
              data-testid={`exam-bookmark-${item.questionId}`}
              data-bookmarked={item.bookmarked ? "true" : "false"}
              onClick={() =>
                props.onToggleBookmark(item.questionId, !item.bookmarked)
              }
              className="mt-3 rounded-full border border-border px-4 py-1.5 text-sm"
            >
              {item.bookmarked ? "Bookmarked" : "Bookmark"}
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
