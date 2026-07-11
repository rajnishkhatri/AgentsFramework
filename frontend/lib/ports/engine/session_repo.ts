/** SessionRepo port (ADR-0006 #4) — quiz-session lifecycle + scoring tally. */

import type {
  QuizSession,
  SessionMode,
} from "../../wire/engine_entities";

/** The score tally applied at close (FR-D3). A `type`, not an `interface`, so
 * the one-interface-per-file rule (P1) counts only `SessionRepo`. */
export type SessionScore = {
  score_correct: number;
  score_total: number;
};

/**
 * SessionRepo — quiz-session lifecycle + scoring tally (ADR-0006 #4).
 *
 * Behavioral contract:
 *   1. LIFECYCLE + SCORING ONLY. This port opens, closes, and reads sessions.
 *      It does not grade, schedule, or record attempts — those are other ports.
 *   2. `open()` creates a `quiz_session` row (FR-D1) with `started_at` set and
 *      `ended_at = null`, `score_* = 0`. `focus` is the skill id for a drill
 *      session (FR-A5) or null for adaptive/review.
 *   2a. `targetCount` sets the bounded-session length (S3, FR-5/6). It
 *      distinguishes three cases: OMITTED (arg not passed) → resolve the
 *      per-mode default from the `content_string` policy (flat 30) and persist
 *      it; an explicit positive int → persist that value, no override (FR-6);
 *      an explicit `null` → an endless session. The value is stored, never
 *      recomputed on close (FR-7).
 *   3. `close()` sets `ended_at` and the score tally (`score_correct` /
 *      `score_total`) from the supplied tally — the UI Summary derives from
 *      these STORED values, never a recompute (FR-D3). Idempotent: closing an
 *      already-closed session re-applies the same tally without error.
 *   4. `get()` returns `null` (not throw) for an unknown session id.
 *   5. All returned values are `wire/engine_entities` shapes (Rule A4).
 *   6. `listByLearner()` returns closed sessions only (newest-first) for
 *      derived trust signals (streak / weekly) — ADR-0026.
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface SessionRepo {
  /**
   * Open a session; `focus` = skill id for a drill, null otherwise.
   * `targetCount`: omit → per-mode default (30) from `content_string`; a
   * positive int → that length; `null` → endless (FR-5/6).
   */
  open(
    subject: string,
    learnerId: string,
    mode: SessionMode,
    focus?: string | null,
    targetCount?: number | null,
  ): Promise<QuizSession>;

  /** Close a session: set `ended_at` + the stored score tally. Idempotent. */
  close(id: string, score: SessionScore): Promise<QuizSession>;

  /** Read a session by id, or null if unknown. */
  get(id: string): Promise<QuizSession | null>;

  /**
   * Closed sessions for a learner, newest-first (by `ended_at DESC`), for
   * derived signals like streak and weekly-session counts (FR-C1 rail).
   *
   * Behavioral contract:
   *   1. RETURNS CLOSED SESSIONS ONLY (`ended_at != null`). In-flight sessions
   *      are excluded — the caller reasons over completed work, not intent.
   *   2. `sinceISO` (optional) — inclusive lower bound on `ended_at`. Omitted
   *      → no lower bound (all closed sessions). Callers pass the earliest
   *      timestamp they need so the read stays bounded (e.g. 8 days back for
   *      "this week + a 1-day streak-continuity check").
   *   3. Ordering is deterministic (`ended_at DESC`, then `id ASC` as a
   *      tiebreaker for same-instant ends).
   *   4. Empty result → `[]`, never `null`, never throw.
   *   5. Returned rows are `wire/engine_entities.QuizSession` shapes (Rule A4
   *      / F-R8: no vendor type escapes the adapter).
   *
   * @throws EngineRepoError on persistence failure.
   */
  listByLearner(
    subject: string,
    learnerId: string,
    options?: { sinceISO?: string },
  ): Promise<QuizSession[]>;
}
