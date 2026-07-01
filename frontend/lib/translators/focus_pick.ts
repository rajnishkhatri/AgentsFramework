/**
 * focus_pick — the weakest+due skill selection, shared by the Dashboard's
 * "today's focus" banner (FR-C2) and the Summary's recommended-next card
 * (FR-G1/G2).
 *
 * Pure T1 helper (imports `wire/` only; no I/O, no React). It mirrors
 * `FsrsScheduler.next`'s selection EXACTLY so the read-only views point at the
 * same skill the Scheduler would serve — WITHOUT the seeding write the Scheduler
 * performs (FR-A2: the Scheduler stays the sole skill_state writer). Living here
 * rather than inside one screen's hook keeps both consumers on one definition and
 * avoids a screen-to-screen import.
 */

import type { SkillState } from "../wire/engine_entities";

/**
 * The weakest+due focus skill id, or null when there are no rows. Selection:
 * prefer due (`due_at <= now`), then lowest mastery, then earliest due_at, then
 * `skill_id.localeCompare` as a deterministic tie-break.
 */
export function pickFocusSkillId(
  states: readonly SkillState[],
  nowISO: string,
): string | null {
  if (states.length === 0) return null;
  const nowMs = Date.parse(nowISO);
  const due = states.filter((s) => Date.parse(s.due_at) <= nowMs);
  const pool = [...(due.length > 0 ? due : states)];
  pool.sort(
    (a, b) =>
      a.mastery - b.mastery ||
      Date.parse(a.due_at) - Date.parse(b.due_at) ||
      a.skill_id.localeCompare(b.skill_id),
  );
  return pool[0]!.skill_id;
}
