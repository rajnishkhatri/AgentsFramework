/**
 * FeedbackView — the post-answer teaching screen (FR-E1..E5).
 *
 * Presentational only (F-R1): it renders a `FeedbackVM` (composed by
 * `feedback_vm` from a graded Verdict) as props. No engine port, no grading, no
 * SDK — wire/VM types only.
 *
 * FR-A8 (color is never the sole signal): each reviewed choice pairs its
 * per-state color (via `data-state` + tokens) with an ICON and a TEXT LABEL
 * ("CORRECT ANSWER" / "YOUR CHOICE"), so the state is legible without color.
 * State-driven styling rides `data-state` (§13 convention), not className
 * ternaries, so it survives style merges and is DevTools-inspectable.
 */

import * as React from "react";
import { Check, X, Circle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  FeedbackVM,
  ReviewedChoiceState,
} from "@/lib/translators/feedback_vm";

const STATE_ICON: Record<ReviewedChoiceState, LucideIcon> = {
  correct: Check,
  "chosen-wrong": X,
  other: Circle,
};

/** The text label paired with color for every state (FR-A8). */
const STATE_LABEL: Record<ReviewedChoiceState, string> = {
  correct: "CORRECT ANSWER",
  "chosen-wrong": "YOUR CHOICE",
  other: "",
};

const BANNER_TEXT = {
  celebrate: "Exactly right.",
  soft: "Not quite — and that's useful.",
} as const;

function ReviewedChoiceRow(props: {
  letter: string;
  label: string;
  state: ReviewedChoiceState;
}): React.JSX.Element {
  const { letter, label, state } = props;
  const Icon = STATE_ICON[state];
  const stateLabel = STATE_LABEL[state];
  return (
    <li
      data-testid={`choice-${letter}`}
      data-state={state}
      className={cn(
        "flex items-center gap-3 rounded-[13px] border px-4 py-3",
        "data-[state=correct]:border-[color-mix(in_oklab,var(--color-success)_45%,transparent)]",
        "data-[state=correct]:bg-[color-mix(in_oklab,var(--color-success)_10%,transparent)]",
        "data-[state=chosen-wrong]:border-[color-mix(in_oklab,var(--color-danger)_45%,transparent)]",
        "data-[state=chosen-wrong]:bg-[color-mix(in_oklab,var(--color-danger)_9%,transparent)]",
        "data-[state=other]:border-border data-[state=other]:bg-surface",
      )}
    >
      <span
        aria-hidden="true"
        data-state={state}
        className={cn(
          "grid size-7 place-items-center rounded-full font-semibold",
          "data-[state=correct]:bg-success data-[state=correct]:text-white",
          "data-[state=chosen-wrong]:bg-danger data-[state=chosen-wrong]:text-white",
          "data-[state=other]:bg-selected data-[state=other]:text-muted",
        )}
      >
        {letter}
      </span>
      <span className="flex-1">{label}</span>
      {stateLabel ? (
        <span className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide">
          <Icon aria-hidden="true" className="size-3.5" />
          {stateLabel}
        </span>
      ) : null}
    </li>
  );
}

export function FeedbackView(props: { vm: FeedbackVM }): React.JSX.Element {
  const { vm } = props;
  return (
    <section aria-label="Answer feedback" className="flex flex-col gap-5">
      <div
        data-testid="feedback-banner"
        data-banner={vm.banner}
        role="status"
        className={cn(
          "flex items-center gap-2 rounded-md px-4 py-3 text-lg font-semibold",
          "data-[banner=celebrate]:bg-[color-mix(in_oklab,var(--color-success)_12%,transparent)]",
          "data-[banner=celebrate]:text-success",
          "data-[banner=soft]:bg-accent-light data-[banner=soft]:text-accent",
        )}
      >
        {vm.banner === "celebrate" ? (
          <Check aria-hidden="true" className="size-5" />
        ) : (
          <Circle aria-hidden="true" className="size-5" />
        )}
        {BANNER_TEXT[vm.banner]}
      </div>

      <ul className="flex flex-col gap-2">
        {vm.reviewedChoices.map((c) => (
          <ReviewedChoiceRow
            key={c.letter}
            letter={c.letter}
            label={c.label}
            state={c.state}
          />
        ))}
      </ul>

      <div className="flex flex-col gap-3 text-base">
        <p>
          <span className="font-semibold">
            Why {vm.correctLetter} is correct:{" "}
          </span>
          {vm.correctRationale}
        </p>
        {!vm.correct && vm.chosenLetter ? (
          <p>
            <span className="font-semibold">
              Why {vm.chosenLetter} tempted you:{" "}
            </span>
            {vm.chosenRationale}
          </p>
        ) : null}
        <p className="rounded-[13px] bg-surface px-4 py-3 text-muted">
          <span className="font-semibold text-fg">The rule: </span>
          {vm.ruleMd}
        </p>
      </div>
    </section>
  );
}
