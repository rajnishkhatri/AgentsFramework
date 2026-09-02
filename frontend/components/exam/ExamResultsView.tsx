/**
 * ExamResultsView — run scores + composite + links (S-D2 / FR-27–28, FR-34).
 */

"use client";

import * as React from "react";
import Link from "next/link";
import type { ExamAnalytics, ExamSectionAttempt } from "@/lib/wire/exam_entities";
import { ExamAnalyticsPanel } from "./ExamAnalyticsPanel";

export type ExamResultsSectionVM = {
  readonly code: string;
  readonly title: string;
  readonly attempt: ExamSectionAttempt | null;
  readonly href: string;
};

export interface ExamResultsViewProps {
  readonly formTitle: string;
  readonly sections: readonly ExamResultsSectionVM[];
  readonly composite: number | null;
  readonly analytics: ExamAnalytics | null;
  readonly homeHref: string;
}

export function ExamResultsView(props: ExamResultsViewProps): React.JSX.Element {
  return (
    <section
      data-testid="exam-results"
      aria-label="Exam results"
      className="mx-auto flex max-w-[760px] flex-col gap-6"
    >
      <header>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          {props.formTitle}
        </p>
        <h1 className="text-xl font-semibold text-fg">Results</h1>
      </header>
      <div className="grid gap-3 sm:grid-cols-2">
        {props.sections.map((section) => {
          const attempt = section.attempt;
          const raw =
            attempt?.raw_correct != null && attempt.raw_scored_total != null
              ? `${attempt.raw_correct}/${attempt.raw_scored_total}`
              : "—";
          return (
            <Link
              key={section.code}
              href={section.href}
              data-testid={`exam-results-section-${section.code}`}
              className="rounded-[16px] border border-border p-4 hover:bg-selected"
            >
              <p className="text-xs uppercase tracking-wide text-muted">
                {section.title}
              </p>
              <p className="text-2xl font-semibold">{raw}</p>
              <p className="text-sm text-muted">
                {attempt?.scale_score == null
                  ? "Scale unavailable"
                  : `Scale ${attempt.scale_score}`}
              </p>
            </Link>
          );
        })}
        <div
          data-testid="exam-composite"
          className="rounded-[16px] border border-border p-4"
        >
          <p className="text-xs uppercase tracking-wide text-muted">Composite</p>
          <p className="text-2xl font-semibold">
            {props.composite == null ? "—" : props.composite}
          </p>
        </div>
      </div>
      {props.analytics ? <ExamAnalyticsPanel analytics={props.analytics} /> : null}
      <Link
        href={props.homeHref}
        data-testid="exam-back-home"
        className="inline-flex w-fit rounded-full border border-border px-6 py-3 font-medium"
      >
        Back to exam home
      </Link>
    </section>
  );
}
