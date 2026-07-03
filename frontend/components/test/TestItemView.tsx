/**
 * TestItemView — one timed-test item (F-R1, presentational).
 *
 * The Test-Mode analogue of QuizView, but for a FIXED timed section: it renders
 * the item's context + choices and a navigation footer (Previous / Next /
 * Submit section) plus an "answered N/total" progress readout and the countdown.
 * Unlike QuizView it has NO hint/reveal and does NOT submit a single answer —
 * selection only records into the reducer's answers map; grading happens once, at
 * Submit section. It reuses the `choice-<L>` testid pattern so selectors stay
 * consistent with practice.
 *
 * Reviewed engine content note (same as QuizView): `contextHtml` is REVIEWED,
 * engine-authored content, so dangerouslySetInnerHTML is the sanctioned delivery
 * of the underlined span — distinct from FE-AP-12 (agent-emitted HTML).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { QuizItemVM } from "@/lib/translators/quiz_item_vm";
import { CountdownTimer } from "./CountdownTimer";

export interface TestItemViewProps {
  readonly vm: QuizItemVM;
  readonly selectedLetter: string | null;
  readonly onSelect: (letter: string) => void;
  readonly index: number;
  readonly count: number;
  readonly answeredCount: number;
  readonly remainingMs: number;
  readonly sectionLabel?: string | undefined;
  readonly onPrev: () => void;
  readonly onNext: () => void;
  readonly onSubmitSection: () => void;
}

export function TestItemView(props: TestItemViewProps): React.JSX.Element {
  const {
    vm,
    selectedLetter,
    onSelect,
    index,
    count,
    answeredCount,
    remainingMs,
    sectionLabel,
    onPrev,
    onNext,
    onSubmitSection,
  } = props;

  const atFirst = index <= 0;
  const atLast = index >= count - 1;

  return (
    <section aria-label="Timed test question" className="mx-auto flex max-w-[760px] flex-col gap-5">
      <header className="flex items-center justify-between gap-3">
        <p data-testid="test-progress" className="text-sm text-muted">
          Question {index + 1} of {count} · {answeredCount}/{count} answered
        </p>
        <CountdownTimer remainingMs={remainingMs} sectionLabel={sectionLabel} />
      </header>

      {/* Reviewed engine-authored context carrying the underlined span. */}
      <p
        data-testid="quiz-context"
        className="text-[1.25rem] leading-[1.8]"
        dangerouslySetInnerHTML={{ __html: vm.contextHtml }}
      />

      <p className="text-base font-medium">{vm.stem}</p>

      <ul className="flex flex-col gap-2">
        {vm.choices.map((c) => {
          const selected = c.letter === selectedLetter;
          return (
            <li key={c.letter}>
              <button
                type="button"
                data-testid={`choice-${c.letter}`}
                data-selected={selected ? "true" : "false"}
                onClick={() => onSelect(c.letter)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-[16px] border px-4 py-3 text-left",
                  "data-[selected=false]:border-border data-[selected=false]:bg-surface",
                  "data-[selected=true]:border-accent data-[selected=true]:bg-accent-light",
                )}
              >
                <span
                  data-selected={selected ? "true" : "false"}
                  className={cn(
                    "grid size-7 place-items-center rounded-full font-semibold",
                    "data-[selected=false]:bg-selected data-[selected=false]:text-muted",
                    "data-[selected=true]:bg-accent data-[selected=true]:text-on-accent",
                  )}
                >
                  {c.letter}
                </span>
                <span className="flex-1">{c.label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          data-testid="test-prev"
          onClick={onPrev}
          disabled={atFirst}
          data-enabled={atFirst ? "false" : "true"}
          className={cn(
            "rounded-full border border-border px-5 py-2.5 font-medium hover:bg-selected",
            "data-[enabled=false]:opacity-50 data-[enabled=false]:pointer-events-none",
          )}
        >
          ← Previous
        </button>

        {atLast ? (
          <button
            type="button"
            data-testid="test-submit-section"
            onClick={onSubmitSection}
            className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
          >
            Submit section
          </button>
        ) : (
          <button
            type="button"
            data-testid="test-next"
            onClick={onNext}
            className="rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
          >
            Next →
          </button>
        )}
      </div>

      {/* Submit is always reachable, not only on the last item (a learner may
          finish early). Kept low-emphasis so Next stays the primary path. */}
      {!atLast ? (
        <button
          type="button"
          data-testid="test-submit-early"
          onClick={onSubmitSection}
          className="mx-auto rounded-full px-4 py-2 text-sm text-muted hover:text-fg"
        >
          Submit section now
        </button>
      ) : null}
    </section>
  );
}
