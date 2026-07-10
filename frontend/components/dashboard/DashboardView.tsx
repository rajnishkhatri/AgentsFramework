/**
 * DashboardView — the Dashboard / Home screen (Screen 1, FR-C2/C3/C5 + C1 rail).
 *
 * Presentational only (F-R1): renders a `DashboardVM` (composed by
 * `loadDashboard`). No engine port, no I/O, no SDK — VM + wire/translator types
 * only. Greeting header + trust rail (streak/weekly) are additive C1 surfaces;
 * score-goal and coach-note tiles are intentionally absent (FR-14).
 */

import * as React from "react";
import Link from "next/link";
import { BucketCard } from "./BucketCard";
import { TodayFocusBanner } from "./TodayFocusBanner";
import { StreakTile } from "./StreakTile";
import { WeeklyTile } from "./WeeklyTile";
import type { DashboardVM } from "./use_dashboard";
import { screen } from "@/components/shell/nav_model";

export function DashboardView(props: {
  vm: DashboardVM;
  /** Re-fires the dashboard load after a rail-scoped failure (FR-1). */
  onRetryRail?: () => void;
}): React.JSX.Element {
  const { vm, onRetryRail } = props;
  const quizRoute = screen("quiz").route;
  const testRoute = screen("test").route;

  return (
    <div
      data-testid="dashboard-root"
      className="@container flex flex-col gap-6 @lg:grid @lg:grid-cols-[1fr_320px] @lg:items-start"
    >
      <header className="@lg:col-span-2">
        <h1 className="text-2xl font-semibold text-fg">{vm.greeting.headline}</h1>
        <p className="text-sm text-muted">{vm.greeting.subline}</p>
      </header>

      <aside
        aria-label="Trust rail"
        data-testid="trust-rail"
        className="order-2 flex gap-3 overflow-x-auto @lg:order-none @lg:col-start-2 @lg:row-span-3 @lg:flex-col"
      >
        <div aria-live="polite" className="flex gap-3 @lg:flex-col">
          {vm.rail.status === "unavailable" ? (
            <>
              <span className="text-sm text-muted">Trust rail unavailable</span>
              <button
                type="button"
                data-testid="rail-retry"
                className="text-sm font-medium text-fg underline"
                onClick={onRetryRail}
              >
                Retry
              </button>
            </>
          ) : (
            <>
              <StreakTile vm={vm.rail.streak} />
              <WeeklyTile vm={vm.rail.weekly} />
            </>
          )}
        </div>
      </aside>

      <div className="order-3 flex flex-col gap-6 @lg:order-none @lg:col-start-1">
        {vm.todayFocus.present ? (
          <TodayFocusBanner
            skillName={vm.todayFocus.skillName}
            accentVar={vm.todayFocus.accentVar}
            ctaLabel={vm.todayFocus.ctaLabel}
          />
        ) : null}

        <section aria-label="Skill mastery" className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold text-muted">Skill mastery</h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            {vm.buckets.map((b) => (
              <BucketCard key={b.skillId} vm={b} />
            ))}
          </div>
        </section>

        <section aria-label="Secondary actions" className="flex flex-wrap gap-3">
          <Link
            href={quizRoute}
            className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-selected"
          >
            Drill a skill
          </Link>
          <Link
            href={`${quizRoute}?mode=review`}
            data-testid="review-misses"
            className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-selected"
          >
            Review my misses ({vm.reviewMissesCount})
          </Link>
          <Link
            href={testRoute}
            data-testid="take-timed-test"
            className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-selected"
          >
            Take a timed test
          </Link>
        </section>
      </div>
    </div>
  );
}
