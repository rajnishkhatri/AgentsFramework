-- 0004_durable_progress.sql — served pointer + attempt idempotency (coach-v3 §4).
--
-- (a) quiz_session.current_question_id — durable served-pointer (FR-B3a).
--     TEXT to match opaque bank ids (`ti-gen-*`), not uuid.
-- (b) attempt.idempotency_key + partial unique index (FR-A9.1).
--     Client stamps a real UUID; column type is uuid (matches schema.pg.ts).
--     Baseline 0000 uses TEXT PKs for content/session rows; this key is not an
--     opaque bank id, so uuid is intentional.
--
-- The WHERE clause on the unique index lets legacy NULL-key rows coexist.

ALTER TABLE "quiz_session" ADD COLUMN "current_question_id" text;

ALTER TABLE "attempt" ADD COLUMN "idempotency_key" uuid;

CREATE UNIQUE INDEX "attempt_idempotency_uq"
  ON "attempt" ("session_id", "question_id", "idempotency_key")
  WHERE "idempotency_key" IS NOT NULL;
