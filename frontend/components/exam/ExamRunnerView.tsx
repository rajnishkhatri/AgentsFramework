/**
 * ExamRunnerView — in-section item + countdown + nav + flag (S-D2 / FR-13–18, 23).
 * Reuses Test Mode's CountdownTimer (decisions.md sibling import).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { QuizItemVM } from "@/lib/translators/quiz_item_vm";
import { CountdownTimer } from "@/components/test/CountdownTimer";
import { ExamNavigator } from "./ExamNavigator";
import type { NavigatorCell } from "./exam_section_reducer";

export interface ExamRunnerViewProps {
  readonly vm: QuizItemVM;
  readonly selectedLetter: string | null;
  readonly flagged: boolean;
  readonly index: number;
  readonly count: number;
  readonly answeredCount: number;
  readonly remainingMs: number;
  readonly fiveMinWarning: boolean;
  readonly sectionLabel: string;
  readonly cells: readonly NavigatorCell[];
  readonly pendingBlankConfirm: number | null;
  readonly notSaved: boolean;
  readonly onSelect: (letter: string) => void;
  readonly onClear: () => void;
  readonly onFlag: () => void;
  readonly onPrev: () => void;
  readonly onNext: () => void;
  readonly onJump: (questionId: string) => void;
  readonly onSubmit: () => void;
  readonly onConfirmSubmit: () => void;
  readonly onCancelSubmit: () => void;
}

export function ExamRunnerView(props: ExamRunnerViewProps): React.JSX.Element {
  const atFirst = props.index <= 0;
  const atLast = props.index >= props.count - 1;

  return (
    <section
      data-testid="exam-runner"
      aria-label="Exam question"
      className="mx-auto flex max-w-[760px] flex-col gap-5"
    >
      <header className="flex items-center justify-between gap-3">
        <p data-testid="exam-progress" className="text-sm text-muted">
          Question {props.index + 1} of {props.count} · {props.answeredCount}/
          {props.count} answered
        </p>
        <CountdownTimer
          remainingMs={props.remainingMs}
          sectionLabel={props.sectionLabel}
        />
      </header>

      {props.fiveMinWarning ? (
        <p
          data-testid="exam-five-min-warning"
          role="status"
          className="rounded-md border border-warning px-3 py-2 text-sm text-warning"
        >
          5 minutes remaining.
        </p>
      ) : null}

      {props.notSaved ? (
        <p data-testid="exam-not-saved" role="status" className="text-sm text-danger">
          not saved
        </p>
      ) : null}

      <p
        data-testid="quiz-context"
        className="text-[1.25rem] leading-[1.8]"
        dangerouslySetInnerHTML={{ __html: props.vm.contextHtml }}
      />
      <p className="text-base font-medium">{props.vm.stem}</p>

      <ul className="flex flex-col gap-2">
        {props.vm.choices.map((c) => {
          const selected = c.letter === props.selectedLetter;
          return (
            <li key={c.letter}>
              <button
                type="button"
                data-testid={`choice-${c.letter}`}
                data-selected={selected ? "true" : "false"}
                onClick={() => props.onSelect(c.letter)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-[16px] border px-4 py-3 text-left",
                  "data-[selected=false]:border-border data-[selected=false]:bg-surface",
                  "data-[selected=true]:border-accent data-[selected=true]:bg-accent-light",
                )}
              >
                <span className="grid size-7 place-items-center rounded-full bg-selected font-semibold">
                  {c.letter}
                </span>
                <span className="flex-1">{c.label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="exam-clear"
          onClick={props.onClear}
          disabled={props.selectedLetter == null}
          className="rounded-full border border-border px-4 py-2 text-sm disabled:opacity-50"
        >
          Clear answer
        </button>
        <button
          type="button"
          data-testid="exam-flag"
          data-flagged={props.flagged ? "true" : "false"}
          onClick={props.onFlag}
          className="rounded-full border border-border px-4 py-2 text-sm data-[flagged=true]:border-warning data-[flagged=true]:text-warning"
        >
          {props.flagged ? "Flagged for review" : "Mark for review"}
        </button>
      </div>

      <ExamNavigator cells={props.cells} onJump={props.onJump} />

      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          data-testid="exam-prev"
          onClick={props.onPrev}
          disabled={atFirst}
          className="rounded-full border border-border px-5 py-2.5 font-medium disabled:opacity-50"
        >
          ← Previous
        </button>
        {atLast ? (
          <button
            type="button"
            data-testid="exam-submit"
            onClick={props.onSubmit}
            className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
          >
            Submit section
          </button>
        ) : (
          <button
            type="button"
            data-testid="exam-next"
            onClick={props.onNext}
            className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
          >
            Next →
          </button>
        )}
      </div>
      {!atLast ? (
        <button
          type="button"
          data-testid="exam-submit-early"
          onClick={props.onSubmit}
          className="mx-auto rounded-full px-4 py-2 text-sm text-muted hover:text-fg"
        >
          Submit section now
        </button>
      ) : null}

      {props.pendingBlankConfirm != null ? (
        <div
          data-testid="exam-blank-confirm"
          role="alertdialog"
          aria-label="Unanswered items"
          className="rounded-[13px] border border-warning bg-surface p-4"
        >
          <p className="text-sm">
            {props.pendingBlankConfirm} unanswered{" "}
            {props.pendingBlankConfirm === 1 ? "item" : "items"}. Unanswered
            items score 0. Submit anyway?
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              data-testid="exam-confirm-submit"
              onClick={props.onConfirmSubmit}
              className="rounded-full bg-accent px-5 py-2 text-sm font-semibold text-on-accent"
            >
              Submit
            </button>
            <button
              type="button"
              data-testid="exam-cancel-submit"
              onClick={props.onCancelSubmit}
              className="rounded-full border border-border px-5 py-2 text-sm"
            >
              Keep working
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
