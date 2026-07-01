/**
 * format_clock — the pure, testable timer logic for Test Mode (no React, no clock).
 *
 * The live tick lives in `use_countdown.ts` (a §14-sanctioned effect around the
 * browser clock). Everything DERIVABLE from a remaining-ms value — the `mm:ss`
 * label and the visual band — is pure and lives here, so it is node-testable with
 * no fake timers and reused by both the hook and the `CountdownTimer` view.
 *
 * Import rule: stdlib only.
 */

/** The visual urgency band of the countdown (drives styling + a `data-state`). */
export type ClockBand = "normal" | "warning" | "expired";

/** Under this many ms remaining, the clock is in the "warning" band. */
export const WARNING_THRESHOLD_MS = 5 * 60_000; // 5 minutes

/** Format remaining ms as `mm:ss` (clamped at 0; minutes may exceed 59 → e.g. 75:00). */
export function formatClock(remainingMs: number): string {
  const ms = Math.max(0, remainingMs);
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const mm = String(minutes).padStart(2, "0");
  const ss = String(seconds).padStart(2, "0");
  return `${mm}:${ss}`;
}

/** The band for a remaining-ms value: expired at ≤0, warning under the threshold. */
export function clockBand(remainingMs: number): ClockBand {
  if (remainingMs <= 0) return "expired";
  if (remainingMs <= WARNING_THRESHOLD_MS) return "warning";
  return "normal";
}
