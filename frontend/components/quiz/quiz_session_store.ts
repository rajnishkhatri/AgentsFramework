/**
 * quiz_session_store — the in-session Quiz→Summary handoff (Phase 1.4′,
 * ADR-0011 §4) plus the active-quiz resume pointer (Epic A/B continuity,
 * FLAG-4 / FR-1–FR-2).
 *
 * FR-G1's mastery delta is measured against `skillStateAtStart`, an in-memory
 * `ReadonlyMap` captured once by `openQuizSession` (after `sessionRepo.open`,
 * before the first `review()`). The Quiz page and the Summary page are separate
 * route segments, so the map has to survive the client-side navigation between
 * them without being persisted. This module-level singleton is that carrier —
 * the same "shared client-side substrate" role the plan assigns to
 * `coach_thread_store` (§Architecture / OD-3), scoped by session id.
 *
 * The **active quiz pointer** is a second in-tab heap field on the same module:
 * written while Quiz is live so Coach ← Back can remount `/learn/quiz` and
 * resume the left item instead of calling `openSession` again (FR-3). Cleared
 * on Finish close (FR-2). Retained across unmount (Coach nav). Not persisted —
 * same two-tab / reload limitation as the mastery snapshot.
 * Feedback-phase pointers also stash verdict + answeredLetter so remount
 * restores reviewing (same Question N; learner taps Next) — not answering with
 * a post-grade tally (which would display N+1).
 *
 * Forward notes (not this sprint):
 *   - Epic C0 Wrap-up `?session=` should prefer `readActiveQuiz()?.sessionId`
 *     over putting quiz session id on `coach_thread_store`.
 *   - Epic D `Q-8` End-session MUST also `clearActiveQuiz()`.
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

import type { SkillState, Verdict } from "@/lib/wire/engine_entities";

/** The captured "before" mastery, keyed by `skill_id` (see `openQuizSession`). */
export type SkillStateSnapshot = ReadonlyMap<string, SkillState>;

/**
 * In-tab pointer to the live Quiz item so a remount can resume (FLAG-4).
 * Spec minimum is `{ sessionId, questionId, position }`; `correct`/`total` are
 * also stashed so resume does not fabricate a `0/0` score (plan §1).
 *
 * When `phase === "feedback"`, `verdict` + `answeredLetter` MUST be present so
 * remount restores reviewing (same item, Next still available) — not answering
 * with a post-grade tally (that would show Question N+1 and risk re-submit).
 */
export type ActiveQuizPointer = {
  sessionId: string;
  questionId: string;
  /** 1-based progress position shown in QuizProgress. */
  position: number;
  correct: number;
  total: number;
  /** Optional; resume defaults to answering if omitted. */
  phase?: "answering" | "feedback";
  /** Present when `phase === "feedback"` — restores reviewing on remount. */
  verdict?: Verdict;
  answeredLetter?: string;
  usedHint?: boolean;
};

const snapshots = new Map<string, SkillStateSnapshot>();
let activeQuiz: ActiveQuizPointer | null = null;

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

/** Write / overwrite the live Quiz resume pointer (FR-1). */
export function setActiveQuiz(pointer: ActiveQuizPointer): void {
  activeQuiz = pointer;
}

/** Read the live Quiz resume pointer, or `null` if none (FR-2 / FR-3). */
export function readActiveQuiz(): ActiveQuizPointer | null {
  return activeQuiz;
}

/**
 * Clear the live Quiz resume pointer (FR-2). Call on Finish close; also on
 * Epic D End-session when that lands. Idempotent.
 */
export function clearActiveQuiz(): void {
  activeQuiz = null;
}
