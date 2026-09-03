-- 0006_exam_run_item_reconcile.sql — reconcile prod `exam_run_item` to the 0005 shape.
--
-- WHY: the 2026-09-03 exam deploy hit HTTP 500 on every
-- `/api/engine/db/upsertExamRunItems` in prod, while `insertExamRun` (204) and
-- `beginExamSection` (200) succeeded. The 0005 migration, `schema.pg.ts`, and the
-- generated INSERT all agree, and the real-Postgres adapter test passes against a
-- FRESH 0005 — so the code is correct and the prod `exam_run_item` table shape
-- differs from 0005 (a pre-existing table that 0005's `CREATE TABLE IF NOT EXISTS`
-- silently skipped, so 0005 was ledgered "applied" without recreating it).
--
-- SAFE TO DROP: `upsertExamRunItems` never succeeded in prod, so zero item rows
-- were ever persisted — the table is empty of real data. Dropping and recreating
-- to the exact 0005 shape is therefore lossless and fixes any drift (missing
-- column, wrong type, or wrong PK) uniformly. Parent `exam_run` /
-- `exam_section_attempt` rows are untouched; nothing references `exam_run_item`.
--
-- Idempotent: DROP ... IF EXISTS + a shape identical to 0005. On a fresh DB
-- (0005 already ran) this drops an empty table and recreates it — a no-op.

DROP TABLE IF EXISTS "exam_run_item" CASCADE;

CREATE TABLE "exam_run_item" (
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
