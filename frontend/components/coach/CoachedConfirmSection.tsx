/**
 * FR-15 — in-place coached-solve confirmation (V20).
 * Affirmation turn + inline label + learner-initiated "See the breakdown →".
 */

"use client";

import * as React from "react";
import type { CoachedConfirmState } from "@/components/quiz/quiz_screen_reducer";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";

export function CoachedConfirmSection(props: {
  readonly confirm: CoachedConfirmState;
  readonly onSeeBreakdown?: () => void;
}): React.JSX.Element {
  const { confirm, onSeeBreakdown } = props;
  // V30: the confirm serves BOTH solves. The affirmation turn + result label
  // mirror the v3 prototype's `resultLabel` — a first-try solve is not "worked
  // through the trap", so both strings switch on `confirm.resolution`.
  const firstTry = confirm.resolution === "first_try";
  return (
    <div
      data-testid="quiz-coached-confirm"
      role="region"
      aria-label={
        firstTry ? "Solve confirmation" : "Coached solve confirmation"
      }
      className="flex flex-col gap-3"
    >
      <div className="flex justify-start">
        <div className="max-w-[92%] rounded-2xl rounded-bl-md border border-border bg-surface px-3 py-2 text-sm leading-relaxed">
          <p data-testid="quiz-coached-confirm-turn" className="text-fg">
            {firstTry
              ? "Yes — that’s it. Clean solve"
              : "Yes — that’s it. You worked through the trap"}
            {confirm.whySummary.length > 0 ? ":" : "."}
          </p>
          {confirm.whySummary.length > 0 ? (
            <div className="mt-1.5 text-muted">
              <StreamingMarkdown text={confirm.whySummary} tone="plain" />
            </div>
          ) : null}
        </div>
      </div>
      <p
        data-testid="quiz-coached-confirm-label"
        className={
          firstTry
            ? "text-sm font-medium text-success"
            : "text-sm font-medium text-accent"
        }
      >
        {firstTry ? "Solved on first try" : "Worked through it with the coach"}
      </p>
      <button
        type="button"
        data-testid="quiz-see-breakdown"
        onClick={onSeeBreakdown}
        className="min-h-11 w-fit rounded-full border border-dashed border-accent px-4 py-2 text-sm font-semibold text-accent"
      >
        See the breakdown →
      </button>
    </div>
  );
}
