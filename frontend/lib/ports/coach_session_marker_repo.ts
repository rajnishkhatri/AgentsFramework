/**
 * CoachSessionMarkerRepo — the ADR-0012 Amendment marker store port.
 *
 * The mode-derivation source of truth for the coach's context contract
 * (agent spec FR-19/FR-21): a `{user_id, question_id, submitted_at}` marker
 * written fire-and-forget from the quiz submit path and read by the coach
 * BFF stream route to derive the AUTHORITATIVE mode (client-supplied mode
 * is advisory, never trusted).
 *
 * Behavioral contract:
 *   1. MONOTONIC — once submitted, always submitted for that item within
 *      the store's lifetime. There is deliberately NO unmark/delete method:
 *      the absence is a type-level fact, not a convention.
 *   2. `isSubmitted` for an unknown pair returns `false` — the caller then
 *      derives `pre_submit`, which FAILS CLOSED (fields stripped).
 *   3. `markSubmitted` is idempotent (a double-tap submit is harmless).
 *   4. Per-user isolation: markers never leak across `user_id`.
 *
 * `user_id` is the server-derived session subject (S3) — never a
 * client-supplied value.
 */
export interface CoachSessionMarkerRepo {
  markSubmitted(userId: string, questionId: string): Promise<void>;
  isSubmitted(userId: string, questionId: string): Promise<boolean>;
}
