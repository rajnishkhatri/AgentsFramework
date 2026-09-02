/**
 * ExamDirectionsView — official directions + time allowed (S-D2 / FR-13).
 * Clock starts only on explicit Begin.
 */

"use client";

import * as React from "react";

export interface ExamDirectionsViewProps {
  readonly title: string;
  readonly directions: string;
  readonly minutes: number;
  readonly onBegin: () => void;
}

export function ExamDirectionsView(
  props: ExamDirectionsViewProps,
): React.JSX.Element {
  return (
    <section
      data-testid="exam-directions"
      aria-label="Section directions"
      className="mx-auto flex max-w-[640px] flex-col gap-5"
    >
      <header>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Official directions
        </p>
        <h1 className="text-xl font-semibold text-fg">{props.title}</h1>
      </header>
      <p data-testid="exam-directions-time" className="text-sm text-muted">
        Time allowed: {props.minutes} minutes. The clock starts when you tap
        Begin.
      </p>
      <p data-testid="exam-directions-body" className="text-base leading-7">
        {props.directions}
      </p>
      <button
        type="button"
        data-testid="exam-begin"
        onClick={props.onBegin}
        className="w-fit rounded-full bg-accent px-6 py-3 font-semibold text-on-accent"
      >
        Begin
      </button>
    </section>
  );
}
