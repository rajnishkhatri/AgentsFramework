/**
 * Pure time-bucketing for the chat-history sidebar (Phase 3).
 *
 * Framework-clean (no React, no SDK, no I/O): takes thread states + a
 * reference "now" and returns ordered groups (Today / Yesterday / Previous 7
 * days / Older), newest-first within each group. Kept pure and injectable-now
 * so it is deterministic in tests (no hidden `Date.now()`).
 *
 * The component renders these groups verbatim — all bucketing logic lives
 * here, not in the leaf component (F-R1).
 */

import type { ThreadState } from "./wire/agent_protocol";

export type ThreadGroupLabel =
  | "Today"
  | "Yesterday"
  | "Previous 7 days"
  | "Older";

export interface ThreadGroup {
  readonly label: ThreadGroupLabel;
  readonly threads: ReadonlyArray<ThreadState>;
}

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function sortKey(t: ThreadState): number {
  // Prefer updated_at (most-recent activity); fall back to created_at.
  const v = Date.parse(t.updated_at || t.created_at || "");
  return Number.isNaN(v) ? 0 : v;
}

function bucket(threadMs: number, todayStart: number): ThreadGroupLabel {
  if (threadMs >= todayStart) return "Today";
  if (threadMs >= todayStart - DAY_MS) return "Yesterday";
  if (threadMs >= todayStart - 7 * DAY_MS) return "Previous 7 days";
  return "Older";
}

const ORDER: ReadonlyArray<ThreadGroupLabel> = [
  "Today",
  "Yesterday",
  "Previous 7 days",
  "Older",
];

/**
 * Group threads into ordered time buckets, newest-first within each. Empty
 * buckets are omitted. `now` is injected so callers/tests control the clock.
 */
export function groupThreadsByTime(
  threads: ReadonlyArray<ThreadState>,
  now: number = Date.now(),
): ReadonlyArray<ThreadGroup> {
  const todayStart = startOfDay(now);
  const byLabel = new Map<ThreadGroupLabel, ThreadState[]>();
  for (const t of threads) {
    const label = bucket(sortKey(t), todayStart);
    const list = byLabel.get(label) ?? [];
    list.push(t);
    byLabel.set(label, list);
  }
  const groups: ThreadGroup[] = [];
  for (const label of ORDER) {
    const list = byLabel.get(label);
    if (!list || list.length === 0) continue;
    list.sort((a, b) => sortKey(b) - sortKey(a));
    groups.push({ label, threads: list });
  }
  return groups;
}
