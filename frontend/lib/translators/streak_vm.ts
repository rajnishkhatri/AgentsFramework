/**
 * streak_vm — closed QuizSession[] + nowISO → StreakVM (FR-2/3/4/6/7).
 *
 * Pure T1: consecutive local-date buckets with ≥1 closed session, walking
 * backwards from the `nowISO` local date. Day-1 (one session today) counts as
 * `{present: true, days: 1}` (Q4). In-flight rows (`ended_at == null`) are
 * skipped. No `Date.now()`, no React, no I/O.
 *
 * Imports `wire/` only.
 */

import type { QuizSession } from "../wire/engine_entities";

export interface StreakVM {
  readonly present: boolean;
  readonly days: number;
}

/** Local YYYY-MM-DD via en-CA (ISO date format, locale-stable). */
function localDateKey(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}

/** Subtract one calendar day from a YYYY-MM-DD key (local-date arithmetic). */
function prevDateKey(key: string): string {
  const [y, m, d] = key.split("-").map(Number) as [number, number, number];
  // Noon UTC avoids DST edge when constructing from Y-M-D parts in local TZ.
  const dt = new Date(y, m - 1, d, 12, 0, 0, 0);
  dt.setDate(dt.getDate() - 1);
  return localDateKey(dt.toISOString());
}

export function toStreakVM(
  closedSessions: readonly QuizSession[],
  nowISO: string,
): StreakVM {
  const buckets = new Set<string>();
  for (const s of closedSessions) {
    if (s.ended_at == null) continue;
    buckets.add(localDateKey(s.ended_at));
  }

  let cursor = localDateKey(nowISO);
  let days = 0;
  while (buckets.has(cursor)) {
    days += 1;
    cursor = prevDateKey(cursor);
  }

  return days > 0 ? { present: true, days } : { present: false, days: 0 };
}
