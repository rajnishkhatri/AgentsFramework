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
}
