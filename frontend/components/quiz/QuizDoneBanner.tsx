/**
 * QuizDoneBanner — the "you've reached your goal" milestone (S5).
 *
 * Presentational only (F-R1): a `targetCount` prop in, a milestone line out. The
 * "reached the target?" decision lives in the pure translator quiz_progress_vm
 * (`complete`), not here — this component only renders the message when the page
 * decides to show it. No engine call, no state, no logic (FR-9).
 *
 * FR-5: the milestone is REAL TEXT (WCAG 2.2 AA — not conveyed by colour/icon
 * alone), names the reached count via `{targetCount}` interpolation (never a
 * hardcoded 30), and sits above the item's feedback (the page composes it as a
 * sibling above FeedbackView). Uses `text-on-accent` on `bg-accent` so it meets
 * AA in BOTH light and dark (the on-* token family, per the a11y sweep).
 *
 * No `t()` — this codebase has no i18n helper yet (QuizProgress/QuizView/
 * FeedbackView use inline literals); matching the surrounding code is correct here.
 */

"use client";

import * as React from "react";

export interface QuizDoneBannerProps {
  /** The session's target_count — the number the learner set out to complete. */
  readonly targetCount: number;
}

export function QuizDoneBanner(props: QuizDoneBannerProps): React.JSX.Element {
  const { targetCount } = props;
  return (
    <section
      aria-label="Session complete"
      data-testid="quiz-done-banner"
      role="status"
      className="mx-auto flex max-w-[760px] items-center gap-3 rounded-2xl bg-accent px-5 py-4 font-semibold text-on-accent"
    >
      <span aria-hidden="true" className="text-xl">
        🎉
      </span>
      <p>You&apos;ve completed your {targetCount}-question session!</p>
    </section>
  );
}
