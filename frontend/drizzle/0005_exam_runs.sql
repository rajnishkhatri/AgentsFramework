-- 0005_exam_runs.sql — official-rules exam persistence (ADR-0040 / spec §4.2).
--
-- Three additive tables on the ADR-0038 seam. Analytics is computed, not stored.
-- sqlite parity is schema.sqlite.ts + schema.parity.test (no sqlite runner).
-- Rollback = leave tables in place; the nav entry is the reachability gate.

CREATE TABLE IF NOT EXISTS "exam_run" (
    "id" text PRIMARY KEY NOT NULL,
    "learner_id" text NOT NULL,
    "form_id" text NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "composite" real
);

CREATE INDEX IF NOT EXISTS "exam_run_learner_form_idx"
    ON "exam_run" ("learner_id", "form_id");

CREATE TABLE IF NOT EXISTS "exam_section_attempt" (
    "run_id" text NOT NULL REFERENCES "exam_run" ("id") ON DELETE CASCADE,
    "section_code" text NOT NULL,
    "status" text NOT NULL,
    "started_at" timestamptz,
    "finished_at" timestamptz,
    "deadline_at" timestamptz,
    "raw_correct" integer,
    "raw_scored_total" integer,
    "scale_score" real,
    "time_remaining_ms_at_submit" integer,
    PRIMARY KEY ("run_id", "section_code")
);

CREATE TABLE IF NOT EXISTS "exam_run_item" (
    "run_id" text NOT NULL REFERENCES "exam_run" ("id") ON DELETE CASCADE,
    "section_code" text NOT NULL,
    "question_id" text NOT NULL,
    "ordinal" integer NOT NULL,
    "chosen_letter" text,
    "correct" boolean,
    "dwell_ms" integer NOT NULL DEFAULT 0,
    "visits" integer NOT NULL DEFAULT 0,
    "answer_changes" integer NOT NULL DEFAULT 0,
    "first_answered_at" timestamptz,
    "dwell_at_first_answer_ms" integer,
    "flagged_in_section" boolean NOT NULL DEFAULT false,
    "bookmarked" boolean NOT NULL DEFAULT false,
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("run_id", "section_code", "question_id")
);

CREATE INDEX IF NOT EXISTS "exam_run_item_run_section_idx"
    ON "exam_run_item" ("run_id", "section_code");
