/**
 * AccuracyBars — ≤6-bar session-accuracy trend (E1b-D1 / FR-BLK-19).
 *
 * Hand-built from the single-fill progressbar idiom. No external chart lib.
 * Newest-first bars; no padding. Each bar is a11y-labeled with its %.
 */

"use client";

import * as React from "react";

export interface AccuracyBarsProps {
  readonly bars: readonly number[];
  /** Accessible name for the group (e.g. "Accuracy trend"). */
  readonly label?: string;
}

export function AccuracyBars(props: AccuracyBarsProps): React.JSX.Element {
  const { bars, label = "Accuracy trend" } = props;
  const capped = bars.slice(0, 6);
  return (
    <div
      data-testid="accuracy-bars"
      role="group"
      aria-label={label}
      className="flex h-10 items-end gap-1.5"
    >
      {capped.map((pct, i) => {
        const height = Math.max(0, Math.min(100, pct));
        return (
          <div
            key={i}
            role="img"
            aria-label={`${pct}%`}
            data-testid={`accuracy-bar-${i}`}
            className="flex-1 rounded-sm"
            style={{
              height: `${height}%`,
              minHeight: height === 0 ? 2 : undefined,
              background: "var(--accent, var(--color-accent))",
              opacity: 0.55 + (i / Math.max(capped.length, 1)) * 0.45,
            }}
          />
        );
      })}
    </div>
  );
}
