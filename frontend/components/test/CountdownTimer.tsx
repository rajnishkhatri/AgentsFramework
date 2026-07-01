/**
 * CountdownTimer — presentational section countdown for Test Mode (F-R1, U-rules).
 *
 * Renders a remaining-ms value as `mm:ss` with an urgency band. It holds NO clock
 * and NO logic beyond formatting (both live in `format_clock.ts`); the live tick
 * is the parent's `use_countdown` hook. That keeps this a pure, node-renderable
 * view.
 *
 * A11y: `role="timer"` with `aria-live="off"` — a countdown must NOT announce
 * every second (that would flood a screen reader, the timer analogue of the
 * streaming-token `aria-live="polite"` rule). The remaining time is conveyed by
 * text (`mm:ss`) + an `aria-label`, never color alone; the band rides a
 * `data-state` attribute for CSS, not a className ternary (§13).
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import { formatClock, clockBand } from "./format_clock";

export interface CountdownTimerProps {
  readonly remainingMs: number;
  /** Section label for the accessible name, e.g. "English". */
  readonly sectionLabel?: string | undefined;
}

export function CountdownTimer(props: CountdownTimerProps): React.JSX.Element {
  const { remainingMs, sectionLabel } = props;
  const label = formatClock(remainingMs);
  const band = clockBand(remainingMs);
  const aria = sectionLabel
    ? `${sectionLabel} section time remaining: ${label}`
    : `Time remaining: ${label}`;

  return (
    <div
      data-testid="test-timer"
      data-state={band}
      role="timer"
      aria-live="off"
      aria-label={aria}
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-sm tabular-nums",
        "border-border",
        // Band styling via data-state (not a className ternary): warning turns
        // amber, expired turns danger. Text is always present, so never color-only.
        "data-[state=warning]:border-warning data-[state=warning]:text-warning",
        "data-[state=expired]:border-danger data-[state=expired]:text-danger",
      )}
    >
      <span aria-hidden="true">⏱</span>
      <span>{label}</span>
    </div>
  );
}
