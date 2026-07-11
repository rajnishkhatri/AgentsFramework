/**
 * weekly_sessions_vm — closed QuizSession[] + nowISO → WeeklySessionsVM (FR-8).
 *
 * Pure T1: count closed sessions whose `ended_at` falls in
 * `[Monday-00:00-local of week containing nowISO .. nowISO]`. ISO 8601 week
 * (Monday = start). Label display-caps at `target` (default 3); `count` is the
 * real unclamped number. No `Date.now()`, no React, no I/O.
 *
 * Imports `wire/` only.
 */

import type { QuizSession } from "../wire/engine_entities";

export interface WeeklySessionsVM {
  readonly count: number;
  readonly target: number;
  readonly label: string;
}

const DEFAULT_TARGET = 3;

/** Monday 00:00:00.000 local of the ISO week containing `nowISO`. */
function mondayStartLocal(nowISO: string): Date {
  const now = new Date(nowISO);
  const day = now.getDay(); // 0=Sun … 6=Sat
  const daysFromMonday = day === 0 ? 6 : day - 1;
  // Noon-of-day construction (mirrors streak_vm) avoids DST spring-forward /
  // fall-back shifting the Monday midnight when the wall-clock jumps.
  const noon = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() - daysFromMonday,
    12,
    0,
    0,
    0,
  );
  noon.setHours(0, 0, 0, 0);
  return noon;
}

export function toWeeklySessionsVM(
  closedSessions: readonly QuizSession[],
  nowISO: string,
  target: number = DEFAULT_TARGET,
): WeeklySessionsVM {
  const monday = mondayStartLocal(nowISO);
  const nowMs = new Date(nowISO).getTime();
  const mondayMs = monday.getTime();

  let count = 0;
  for (const s of closedSessions) {
    if (s.ended_at == null) continue;
    const endMs = new Date(s.ended_at).getTime();
    if (endMs >= mondayMs && endMs <= nowMs) count += 1;
  }

  const display = Math.min(count, target);
  return {
    count,
    target,
    label: `${display} / ${target} sessions`,
  };
}
