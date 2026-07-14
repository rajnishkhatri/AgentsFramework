/**
 * ProgressView — presentational `/learn/progress` surface (Epic F).
 *
 * Renders ProgressScreenVM. Local ephemeral state: none — range is owned by
 * the page (controlled via props). Honest empty trend (FR-1); no projected
 * score (FR-3). Horizontal mastery bar-rows (Q-D3). Range tabs hidden on
 * narrow @container (DT-6 / iPhone — not a dead control).
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type {
  ProgressRange,
  ProgressScreenVM,
} from "@/lib/translators/progress_screen_vm";
import type { BucketCardVM } from "@/lib/translators/bucket_card_vm";
import { TrendChart } from "./TrendChart";

export interface ProgressViewProps {
  readonly vm: ProgressScreenVM;
  readonly range: ProgressRange;
  readonly onRangeChange: (range: ProgressRange) => void;
}

function streakLabel(days: number): string {
  return days === 1 ? "1-day streak" : `${days}-day streak`;
}

function MasteryBarRow(props: { vm: BucketCardVM }): React.JSX.Element {
  const { vm } = props;
  return (
    <div
      data-testid={`mastery-row-${vm.skillId}`}
      data-due={vm.due ? "true" : "false"}
      style={{ ["--accent" as string]: `var(${vm.accentVar})` }}
      className="flex items-center gap-3 py-2"
    >
      <div className="flex min-w-[7.5rem] items-center gap-2">
        <span
          aria-hidden="true"
          className="h-[11px] w-[11px] shrink-0 rounded bg-[var(--accent)]"
        />
        <span className="text-sm font-medium text-fg">{vm.name}</span>
      </div>
      {/*
        Honest-null (Epic F FR-4 / P-4): UNKNOWN mastery renders an inert track,
        never a role=progressbar aria-valuenow=0 (indistinguishable from a real
        0%). The KNOWN flag — not the number — gates the bar and the percent.
      */}
      {vm.masteryKnown ? (
        <div
          className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-selected"
          role="progressbar"
          aria-valuenow={vm.masteryPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${vm.name} mastery`}
        >
          <div
            className="h-full rounded-full bg-[var(--accent)]"
            style={{ width: `${vm.masteryPct}%` }}
          />
        </div>
      ) : (
        <div
          data-testid={`mastery-nodata-${vm.skillId}`}
          className="h-2 min-w-0 flex-1 rounded-full bg-selected opacity-40"
          aria-hidden="true"
        />
      )}
      <div className="flex min-w-[4.5rem] items-center justify-end gap-2">
        {vm.masteryKnown ? (
          <span
            data-testid={`mastery-pct-${vm.skillId}`}
            className="text-sm font-semibold tabular-nums"
            style={{ color: "var(--accent)" }}
          >
            {vm.masteryPct}%
          </span>
        ) : (
          <span
            data-testid={`mastery-nodata-label-${vm.skillId}`}
            className="text-xs italic text-muted"
          >
            No data yet
          </span>
        )}
        {vm.due ? (
          <span
            data-testid={`mastery-due-${vm.skillId}`}
            className="rounded-full bg-[color-mix(in_oklab,var(--color-warning,var(--accent))_18%,transparent)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-fg"
          >
            Due
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function ProgressView(props: ProgressViewProps): React.JSX.Element {
  const { vm, range, onRangeChange } = props;
  const points = vm.trend?.points ?? [];
  const emptyTrend = points.length === 0;

  return (
    <div data-testid="progress-root" className="@container w-full">
      <div className="flex flex-col gap-6 p-4 @md:p-6">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-fg">Your progress</h1>
            <p
              data-testid="progress-header-stats"
              className="mt-1 text-sm text-muted"
            >
              {vm.header.itemsReviewed} items reviewed ·{" "}
              {streakLabel(vm.header.streak.days)}
            </p>
          </div>

          {/*
            DT-6: tabs removed by layout on narrow (iPhone) — hidden until @md,
            not a disabled dead control. Series defaults to all-time on phone
            via the page's initial range.
          */}
          <div
            data-testid="progress-range-tabs"
            role="tablist"
            aria-label="Progress range"
            className="hidden @md:inline-flex rounded-full bg-selected p-1"
          >
            {(
              [
                { id: "30d", label: "30 days" },
                { id: "all", label: "All time" },
              ] as const
            ).map((tab) => {
              const selected = range === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  data-testid={`progress-range-${tab.id}`}
                  onClick={() => onRangeChange(tab.id)}
                  className={cn(
                    "min-h-11 min-w-[5.5rem] rounded-full px-4 text-sm font-medium",
                    selected
                      ? "bg-surface text-fg shadow-sm"
                      : "text-muted hover:text-fg",
                  )}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </header>

        <section
          data-testid="progress-trend-card"
          aria-labelledby="progress-trend-title"
          className="rounded-[13px] bg-surface-sunken p-4 @md:p-5"
        >
          <h2
            id="progress-trend-title"
            className="mb-3 text-sm font-semibold text-fg"
          >
            Accuracy trend
          </h2>
          {emptyTrend ? (
            <p
              data-testid="progress-trend-empty"
              className="py-8 text-center text-sm text-muted"
            >
              Not enough history yet — complete a few sessions to see your
              accuracy trend
            </p>
          ) : (
            <TrendChart points={points} label="Accuracy trend" />
          )}
        </section>

        <section
          data-testid="progress-mastery"
          aria-labelledby="progress-mastery-title"
        >
          <h2
            id="progress-mastery-title"
            className="mb-2 text-sm font-semibold text-fg"
          >
            Mastery by bucket
          </h2>
          <div className="flex flex-col divide-y divide-border">
            {vm.buckets.map((b) => (
              <MasteryBarRow key={b.skillId} vm={b} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
