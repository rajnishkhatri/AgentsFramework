/**
 * quiz_session_store — the in-session Quiz→Summary handoff (Phase 1.4′,
 * ADR-0011 §4).
 *
 * FR-G1's mastery delta is measured against `skillStateAtStart`, an in-memory
 * `ReadonlyMap` captured once by `openQuizSession` (after `sessionRepo.open`,
 * before the first `review()`). The Quiz page and the Summary page are separate
 * route segments, so the map has to survive the client-side navigation between
 * them without being persisted. This module-level singleton is that carrier —
 * the same "shared client-side substrate" role the plan assigns to
 * `coach_thread_store` (§Architecture / OD-3), scoped by session id.
 *
 * It is deliberately NOT an engine port and NOT persisted: on a fresh page load
 * or deep-link straight to `/learn/summary`, the map is gone → Summary reads an
 * empty snapshot → the delta renders "—" (the documented resume limitation,
 * ADR-0011 §4). Persisting the snapshot is a later decision (its trigger =
 * real session-resume UX).
 *
 * Not React state on purpose: it lives above the component tree so it is stable
 * across the Quiz→Summary route change (React state in either page would unmount
 * with it).
 */

import type { SkillState } from "@/lib/wire/engine_entities";

/** The captured "before" mastery, keyed by `skill_id` (see `openQuizSession`). */
export type SkillStateSnapshot = ReadonlyMap<string, SkillState>;

const snapshots = new Map<string, SkillStateSnapshot>();

/** Stash the session-open snapshot so the Summary page can read it back. */
export function stashQuizSession(
  sessionId: string,
  skillStateAtStart: SkillStateSnapshot,
): void {
  snapshots.set(sessionId, skillStateAtStart);
}

/**
 * Read the snapshot captured for `sessionId`, or `null` if none is held (a
 * fresh/deep-link Summary load, or after `clearQuizSession`). Never returns
 * another session's snapshot.
 */
export function readQuizSessionSnapshot(
  sessionId: string,
): SkillStateSnapshot | null {
  return snapshots.get(sessionId) ?? null;
}

/** Drop the snapshot for `sessionId` (idempotent). */
export function clearQuizSession(sessionId: string): void {
  snapshots.delete(sessionId);
}
