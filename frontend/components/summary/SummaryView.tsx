/**
 * SummaryView — the Session-Summary screen (Screen 5, FR-G1..G3).
 *
 * Presentational only (F-R1): renders a `SummaryVM` (composed by `loadSummary`).
 * No engine port, no I/O, no SDK. Three stat tiles — score (STORED, FR-G1),
 * mastery delta (signed, or "—" when the session-start snapshot was absent,
 * ADR-0011 §4), and time — plus a recommended-next card whose CTA re-opens Quiz
 * (FR-G2). The mastery-delta tile shows a number, never color-only (FR-A8).
 */

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import type { SummaryVM } from "./use_summary";
import { screen } from "@/components/shell/nav_model";

function StatTile(props: { label: string; value: string; testId: string }): React.JSX.Element {
  return (
    <div
      data-testid={props.testId}
      className="flex flex-col gap-1 rounded-[13px] border border-border p-4"
    >
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
        {props.label}
      </dt>
      <dd className="text-2xl font-semibold tabular-nums">{props.value}</dd>
    </div>
  );
}

export function SummaryView(props: { vm: SummaryVM }): React.JSX.Element {
  const { summary, masteryDeltaKnown } = props.vm;
  const quizRoute = screen("quiz").route; // /learn/quiz
  const deltaValue = masteryDeltaKnown ? summary.masteryDeltaTile : "—";

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Session summary</h1>
        <p className="text-sm text-muted">Here&rsquo;s how this session went.</p>
      </header>

      <dl className="grid grid-cols-3 gap-3">
        <StatTile label="Score" value={summary.scoreTile} testId="summary-score" />
        <StatTile label="Mastery" value={deltaValue} testId="summary-delta" />
        <StatTile label="Time" value={summary.timeTile} testId="summary-time" />
      </dl>

      <section
        aria-label="Recommended next"
        data-testid="summary-recommended"
        style={{ ["--accent" as string]: `var(${summary.recommended.accentVar})` }}
        className={cn(
          "flex flex-col gap-3 rounded-[13px] border p-5 sm:flex-row sm:items-center sm:justify-between",
          "border-[color-mix(in_oklab,var(--accent)_35%,var(--color-border))]",
          "bg-[color-mix(in_oklab,var(--accent)_8%,transparent)]",
        )}
      >
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Recommended next
          </p>
          <p className="text-lg font-semibold">{summary.recommended.skillName}</p>
        </div>
        <Link
          href={quizRoute}
          data-testid="summary-start-next"
          className="inline-flex items-center justify-center rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white"
        >
          Practice this next
        </Link>
      </section>
    </div>
  );
}
