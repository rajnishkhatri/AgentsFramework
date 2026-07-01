/**
 * TestResultsView — the Test-Mode section result screen (F-R1, presentational).
 *
 * Renders the raw score tile ("39/48") and the official scale-score BAND from
 * `test_scoring.ts` (never one fabricated number — Test-01 publishes ranges). It
 * holds no logic beyond reading its props; the tally comes from the reducer's
 * `results` phase and the band from the pure `englishScaleBand`.
 *
 * Self-contained (Test Mode is decoupled): it does NOT reach into the Summary
 * surface's private tiles. A "Back to dashboard" link keeps the control live
 * (FR-B5, no dead end).
 */

import * as React from "react";
import Link from "next/link";
import { englishScaleBand } from "./test_scoring";

export interface TestResultsViewProps {
  readonly correct: number;
  readonly total: number;
  readonly sectionLabel?: string | undefined;
  readonly dashboardHref: string;
}

function ResultTile(props: {
  label: string;
  value: string;
  testId: string;
}): React.JSX.Element {
  return (
    <div className="flex flex-col gap-1 rounded-[16px] border border-border p-5">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted">
        {props.label}
      </span>
      <span data-testid={props.testId} className="text-2xl font-semibold">
        {props.value}
      </span>
    </div>
  );
}

export function TestResultsView(props: TestResultsViewProps): React.JSX.Element {
  const { correct, total, sectionLabel, dashboardHref } = props;
  const band = englishScaleBand(correct, total);

  return (
    <section
      data-testid="test-results"
      aria-label="Test results"
      className="mx-auto flex max-w-[640px] flex-col gap-6"
    >
      <div className="flex flex-col gap-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          {sectionLabel ? `${sectionLabel} section` : "Section"} — complete
        </p>
        <h1 className="text-xl font-semibold">Your result</h1>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <ResultTile label="Raw score" value={`${correct}/${total}`} testId="test-score" />
        <ResultTile
          label="Scale band"
          value={band ?? "—"}
          testId="test-scale-band"
        />
      </div>

      <p className="text-sm text-muted">
        Scale scores are reported as a band, not a single number (official PreACT
        conversion). Review your misses by reporting category to find your growth
        edge.
      </p>

      <Link
        href={dashboardHref}
        data-testid="test-back-dashboard"
        className="inline-flex w-fit items-center justify-center rounded-full border border-border px-6 py-3 font-medium hover:bg-selected"
      >
        Back to dashboard
      </Link>
    </section>
  );
}
