/**
 * SummaryView — the Session-Summary screen (Screen 5, FR-G1..G3 + C2 payoff).
 *
 * Presentational only (F-R1): renders a `SummaryVM` (composed by `loadSummary`).
 * No engine port, no I/O, no SDK. Three stat tiles — score (STORED, FR-G1),
 * mastery delta (signed, or "—" when the session-start snapshot was absent,
 * ADR-0011 §4), and time — plus a recommended-next card and the C2 three-actions
 * row (FR-16). Misconception accent card when authored (FR-15). Framed title
 * from the VM (FR-13). The mastery-delta tile shows a number, never color-only
 * (FR-A8).
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
  const skillScreen = screen("skill");
  const dashboardRoute = screen("dashboard").route;
  const deltaValue = masteryDeltaKnown ? summary.masteryDeltaTile : "—";
  // S2 (FR-4): the recommended-skill name deep-links into a FOCUSED drill on
  // that skill (`?focus=<skillId>`), honored by the Quiz page (FR-6). The
  // prototype opens Skill detail on a skill click; that screen is comingSoon
  // (nav_model), so the interim target is the quiz-focus route — never the
  // dead /learn/skill route (FR-2). Re-points to Skill detail when S9 lands.
  const focusHref = `${quizRoute}?focus=${summary.recommended.skillId}`;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{summary.title}</h1>
        <p className="text-sm text-muted">{summary.body}</p>
      </header>

      {summary.misconception != null ? (
        <section
          aria-label="The misconception I spotted"
          data-testid="summary-misconception"
          className={cn(
            "rounded-[13px] border p-4",
            "border-[color-mix(in_oklab,var(--color-accent)_35%,var(--color-border))]",
            "bg-[color-mix(in_oklab,var(--color-accent)_8%,transparent)]",
          )}
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            The misconception I spotted
          </p>
          <p className="mt-1 text-sm leading-relaxed">{summary.misconception}</p>
          {summary.selfCorrected ? (
            <p
              data-testid="summary-misconception-recap"
              className="mt-2 text-sm text-muted"
            >
              Once the coach flagged it, you carried the fix — that pattern is
              yours to keep.
            </p>
          ) : null}
        </section>
      ) : null}

      <dl className="grid grid-cols-3 gap-3">
        <StatTile
          label="Solved first-try"
          value={summary.scoreTile}
          testId="summary-score"
        />
        <StatTile label="Mastery change" value={deltaValue} testId="summary-delta" />
        <StatTile label="Time" value={summary.timeTile} testId="summary-time" />
      </dl>

      {summary.outcomeCounts != null ? (
        <div data-testid="summary-outcomes" className="flex flex-col gap-2">
          {/* R6 / VOICE-5: counts are session-global — the heading must not
              claim a per-skill run-until-cleared breakdown we don't render. */}
          <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-muted">
            How items resolved this session
          </p>
          <ul
            aria-label="How items resolved"
            className="flex flex-col gap-1.5 text-sm text-fg"
          >
            <li data-testid="summary-outcome-first-try">
              ✓ Solved on first try: {summary.outcomeCounts.firstTry}
            </li>
            <li data-testid="summary-outcome-coached">
              ↺ Worked through with the coach: {summary.outcomeCounts.coached}
            </li>
            {summary.outcomeCounts.walkedThrough > 0 ? (
              <li data-testid="summary-outcome-walked-through">
                → Walked through (not counted as solved):{" "}
                {summary.outcomeCounts.walkedThrough}
              </li>
            ) : null}
          </ul>
          <p
            data-testid="summary-outcome-legend"
            className="text-xs text-muted"
          >
            ✓ first-try · ↺ coached · → walked through (not scored)
          </p>
        </div>
      ) : null}

      <section
        aria-labelledby="summary-misses-heading"
        data-testid="summary-misses"
        className="flex flex-col gap-3 rounded-[13px] border border-border p-5"
      >
        <h2 id="summary-misses-heading" className="text-base font-semibold">
          Questions to revisit
        </h2>
        {summary.misses.length === 0 ? (
          <p className="text-sm text-muted">
            Clean sweep — no missed or walked-through questions this session.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {summary.misses.map((miss) => (
              <li key={miss.questionId} className="flex flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {miss.skillName}
                </span>
                <span className="text-sm">{miss.stem}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {summary.skillPerformance.length > 0 ? (
        <section
          aria-labelledby="summary-skills-heading"
          data-testid="summary-skill-performance"
          className="flex flex-col gap-3 rounded-[13px] border border-border p-5"
        >
          <h2 id="summary-skills-heading" className="text-base font-semibold">
            Strong and weak areas
          </h2>
          <ul className="flex flex-col gap-2">
            {summary.skillPerformance.map((row) => (
              <li
                key={row.skillId}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="font-medium">{row.skillName}</span>
                <span className="text-muted">
                  {row.accuracyPct}% ·{" "}
                  {row.strength === "strong" ? "Strong" : "Needs practice"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section
        aria-label="Recommended next"
        data-testid="summary-recommended"
        style={{ ["--accent" as string]: `var(${summary.recommended.accentVar})` }}
        className={cn(
          "flex flex-col gap-3 rounded-[13px] border p-5",
          "border-[color-mix(in_oklab,var(--accent)_35%,var(--color-border))]",
          "bg-[color-mix(in_oklab,var(--accent)_8%,transparent)]",
        )}
      >
        <div className="flex flex-col gap-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Recommended next
          </p>
          <Link
            href={focusHref}
            data-testid="summary-skill-link"
            className="text-lg font-semibold underline-offset-2 hover:underline"
          >
            {summary.recommended.skillName}
          </Link>
          <p className="text-sm text-muted">{summary.recommended.drillTitle}</p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <Link
            href={focusHref}
            data-testid="summary-start-next"
            // FR-1/FR-3: fill with the BRAND accent (`--color-accent`), not the
            // card-scoped per-bucket `--accent` above. The per-bucket fill + white
            // text drops below WCAG-AA on the pale/mid buckets (~3.6:1, measured);
            // the bucket-independent brand pair (`bg-accent`/`text-on-accent`)
            // clears AA (~6.5:1). The card keeps `--accent` for its border/tint.
            className="inline-flex items-center justify-center rounded-md bg-accent px-4 py-2 text-sm font-semibold text-on-accent"
          >
            Start recommended drill
          </Link>

          {skillScreen.comingSoon ? (
            <button
              type="button"
              disabled
              aria-disabled="true"
              data-disabled="true"
              title="Coming soon"
              data-testid="summary-see-lesson"
              className={cn(
                "inline-flex items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-semibold",
                "cursor-not-allowed opacity-50",
              )}
            >
              See full lesson
            </button>
          ) : (
            <Link
              href={`${skillScreen.route}?skillId=${summary.recommended.skillId}`}
              data-testid="summary-see-lesson"
              className="inline-flex items-center justify-center rounded-md border border-border px-4 py-2 text-sm font-semibold"
            >
              See full lesson
            </Link>
          )}

          <Link
            href={dashboardRoute}
            data-testid="summary-done"
            className="inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-semibold text-muted underline-offset-2 hover:underline"
          >
            Done for today
          </Link>
        </div>
      </section>
    </div>
  );
}
