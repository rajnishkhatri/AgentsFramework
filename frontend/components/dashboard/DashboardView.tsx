/**
 * DashboardView — the Dashboard / Home screen (Screen 1, FR-C2/C3/C5).
 *
 * Presentational only (F-R1): renders a `DashboardVM` (composed by
 * `loadDashboard`). No engine port, no I/O, no SDK — VM + wire/translator types
 * only. The banner is shown only when `todayFocus.present` (cold start hides it),
 * the grid is one BucketCard per bucket (FR-C3), and the misses control shows its
 * count with a real destination (FR-C5/B5).
 */

import * as React from "react";
import Link from "next/link";
import { BucketCard } from "./BucketCard";
import { TodayFocusBanner } from "./TodayFocusBanner";
import type { DashboardVM } from "./use_dashboard";
import { screen } from "@/components/shell/nav_model";

export function DashboardView(props: { vm: DashboardVM }): React.JSX.Element {
  const { vm } = props;
  const quizRoute = screen("quiz").route; // /learn/quiz
  const testRoute = screen("test").route; // /learn/test (timed section)

  return (
    <div className="flex flex-col gap-6">
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
          href={quizRoute}
          data-testid="review-misses"
          className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-selected"
        >
          Review my misses ({vm.reviewMissesCount})
        </Link>
        {/* Test Mode entry — a timed, fixed section, distinct from adaptive practice. */}
        <Link
          href={testRoute}
          data-testid="take-timed-test"
          className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-selected"
        >
          Take a timed test
        </Link>
      </section>
    </div>
  );
}
