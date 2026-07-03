-- 0001_coach_session_marker.sql — coach-session marker table (ADR-0012 Amendment).
--
-- Hand-authored, same convention as 0000_init_threads.sql (drizzle-kit is
-- intentionally NOT a dependency; apply with psql or the drizzle-orm
-- migrator). Mirrors lib/adapters/coach_marker/db/schema.ts exactly.
--
-- Without this migration the PgCoachMarkerRepo path is silently dead:
-- isSubmitted fails → false (fail-closed to pre_submit forever) and
-- markSubmitted throws into the fire-and-forget swallow.
--
-- Monotonic by construction: the repo only ever INSERTs (ON CONFLICT DO
-- NOTHING). No UPDATE or DELETE statement exists against this table.
--
-- IR-NEON-5: application table only — drizzle.config.ts whitelists it in
-- APPLICATION_TABLES; the LangGraph checkpoint tables stay untouched.

CREATE TABLE IF NOT EXISTS "coach_session_marker" (
    "user_id"      text NOT NULL,
    "question_id"  text NOT NULL,
    "submitted_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "coach_session_marker_user_id_question_id_pk"
        PRIMARY KEY ("user_id", "question_id")
);
