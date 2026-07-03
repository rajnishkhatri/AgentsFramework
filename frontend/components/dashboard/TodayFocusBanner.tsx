/**
 * TodayFocusBanner — the dashboard "Today's focus" banner (FR-C2).
 *
 * Presentational only (F-R1): renders a present `TodayFocusVM` — the weakest+due
 * skill with a primary CTA ("Start adaptive session") that routes to Quiz
 * (FR-B4). The parent omits this component entirely when `todayFocus.present` is
 * false (cold start), so this component always receives a present focus.
 */

import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { screen } from "@/components/shell/nav_model";

/** The present branch of TodayFocusVM (the parent guards `present`). */
export interface TodayFocusBannerProps {
  skillName: string;
  accentVar: string;
  ctaLabel: string;
}

export function TodayFocusBanner(props: TodayFocusBannerProps): React.JSX.Element {
  const { skillName, accentVar, ctaLabel } = props;
  const quizRoute = screen("quiz").route; // /learn/quiz
  return (
    <section
      data-testid="today-focus"
      style={{ ["--accent" as string]: `var(${accentVar})` }}
      className={cn(
        "flex flex-col gap-3 rounded-[13px] border p-5 sm:flex-row sm:items-center sm:justify-between",
        "border-[color-mix(in_oklab,var(--accent)_35%,var(--color-border))]",
        "bg-[color-mix(in_oklab,var(--accent)_8%,transparent)]",
      )}
    >
      <div className="flex flex-col gap-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Today&rsquo;s focus
        </p>
        <p className="text-lg font-semibold">{skillName}</p>
      </div>
      <Link
        href={quizRoute}
        className="inline-flex items-center justify-center rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-on-accent"
      >
        {ctaLabel}
      </Link>
    </section>
  );
}
