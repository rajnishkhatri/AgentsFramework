/**
 * quiz_frame_timer — Q-9 session-elapsed display helper (D1).
 *
 * Pure: `session.started_at` (ISO) + wall-clock `nowMs` → `"m:ss"`. Clamps
 * future clocks and unparseable / null inputs to `"0:00"` (FR-Q9-4). No React,
 * no I/O — the presentational leaf ticks via setInterval and calls this.
 */

export function formatElapsedFromStartedAt(
  startedAtIso: string | null,
  nowMs: number,
): string {
  if (startedAtIso == null) return "0:00";
  const parsed = Date.parse(startedAtIso);
  if (!Number.isFinite(parsed)) return "0:00";
  const elapsedMs = Math.max(0, nowMs - parsed);
  const totalSec = Math.floor(elapsedMs / 1000);
  const mm = Math.floor(totalSec / 60);
  const ss = String(totalSec % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}
