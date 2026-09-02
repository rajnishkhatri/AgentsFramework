/**
 * ExamAnalyticsPanel — facets / pacing / recommendations (FR-30–34).
 * Sourced only from ExamAnalytics — never FSRS mastery.
 */

"use client";

import * as React from "react";
import type { ExamAnalytics } from "@/lib/wire/exam_entities";

export interface ExamAnalyticsPanelProps {
  readonly analytics: ExamAnalytics;
  readonly heading?: string;
}

export function ExamAnalyticsPanel(
  props: ExamAnalyticsPanelProps,
): React.JSX.Element {
  const { analytics, heading = "Exam performance" } = props;
  return (
    <section
      data-testid="exam-analytics"
      aria-labelledby="exam-analytics-title"
      className="rounded-[13px] bg-surface-sunken p-4"
    >
      <h2 id="exam-analytics-title" className="text-sm font-semibold text-fg">
        {heading}
      </h2>
      {analytics.recommendations.length === 0 ? (
        <p data-testid="exam-analytics-none" className="mt-2 text-sm text-muted">
          No recommendations yet.
        </p>
      ) : (
        <ul data-testid="exam-analytics-recs" className="mt-2 flex flex-col gap-2">
          {analytics.recommendations.map((rec) => (
            <li
              key={`${rec.rule}-${rec.facet_ref}`}
              data-testid={`exam-rec-${rec.rule}`}
              className="text-sm"
            >
              <span className="font-medium">{rec.rule}</span>
              {": "}
              {rec.evidence}
            </li>
          ))}
        </ul>
      )}
      <ul className="mt-3 flex flex-col gap-1 text-sm">
        {analytics.facets.map((facet) => (
          <li
            key={`${facet.kind}:${facet.key}`}
            data-testid={`exam-facet-${facet.kind}-${facet.key}`}
            data-label={facet.label}
          >
            {facet.kind} {facet.key}: {facet.correct}/{facet.items}{" "}
            {facet.label.replace("_", " ")}
          </li>
        ))}
      </ul>
    </section>
  );
}
