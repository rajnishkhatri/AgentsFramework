-- 0000_frontend_baseline.sql — CREATE TABLE baseline for the durable engine.
--
-- coach-v3 durable FR-F2/F3. Hand-authored from schema.pg.ts + the threads/
-- coach-marker schemas. Applied by frontend/scripts/migrate_engine.mjs BEFORE
-- 0001–0004 and the seed reconciliation.
--
-- Inventory (this file):
--   * 11 engine tables (skill, question, hint, test_item, test_blueprint,
--     quiz_session, attempt, skill_state, tutorial, content_string,
--     progress_point) — pre-0001 shape (misconception / tutorial teaching
--     fields / attempt.resolution land in 0001–0003 ALTER files).
--   * threads + thread_messages + coach_session_marker (FR-F3: binding
--     DATABASE_URL auto-flips those repos to Pg).
--
-- Deliberate deviations from a literal uuid()-typed drizzle dump (required for
-- the live opaque-id bank — skill ids like `s-punc`, test_item ids like
-- `ti-gen-*` are NOT UUID-shaped):
--   * Primary keys and FK id columns are TEXT (matches the sqlite twin + wire).
--   * hint.question_id and attempt.question_id are TEXT WITHOUT a REFERENCES
--     clause: the practice path stores test_item ids there via
--     TestItemQuestionRepo; a FK to question.id would reject the seed.
-- Soft-retire (not hard-DELETE) remains the content-removal policy (FR-G2).
--
-- IR-NEON-5 / drizzle.config.ts invariant: LangGraph checkpoint tables
-- (checkpoints / checkpoint_writes / checkpoint_blobs / checkpoint_migrations)
-- are ABSENT.

CREATE TABLE IF NOT EXISTS "skill" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "key" text NOT NULL,
    "name" text NOT NULL,
    "share_of_test_pct" real NOT NULL DEFAULT 0,
    "accent_var" text NOT NULL DEFAULT '',
    "description" text NOT NULL DEFAULT '',
    "order" integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS "question" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "skill_id" text NOT NULL REFERENCES "skill" ("id") ON DELETE CASCADE,
    "difficulty" integer NOT NULL DEFAULT 3,
    "context_html" text NOT NULL DEFAULT '',
    "stem" text NOT NULL DEFAULT '',
    "choices" jsonb NOT NULL DEFAULT '[]'::jsonb,
    "answer_letter" text NOT NULL,
    "per_choice_rationale" jsonb NOT NULL DEFAULT '{}'::jsonb,
    "why_correct_md" text NOT NULL DEFAULT '',
    "why_tempted_md" text NOT NULL DEFAULT '',
    "rule_md" text NOT NULL DEFAULT '',
    "item_type" text NOT NULL DEFAULT 'underlined-span-mc',
    "reviewed" boolean NOT NULL DEFAULT false,
    "generated_by" text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS "hint" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "question_id" text NOT NULL,
    "choice_letter" text,
    "rung" integer NOT NULL,
    "body_md" text NOT NULL,
    "reviewed" boolean NOT NULL DEFAULT false,
    "generated_by" text NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS "hint_item_level_uq"
    ON "hint" ("question_id", "rung")
    WHERE "choice_letter" IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS "hint_choice_level_uq"
    ON "hint" ("question_id", "choice_letter", "rung")
    WHERE "choice_letter" IS NOT NULL;

CREATE TABLE IF NOT EXISTS "test_item" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "skill_id" text NOT NULL REFERENCES "skill" ("id") ON DELETE CASCADE,
    "difficulty" integer NOT NULL DEFAULT 3,
    "context_html" text NOT NULL DEFAULT '',
    "stem_md" text NOT NULL,
    "choices" jsonb NOT NULL DEFAULT '[]'::jsonb,
    "answer_letter" text NOT NULL,
    "per_choice_rationale" jsonb NOT NULL DEFAULT '{}'::jsonb,
    "why_correct_md" text NOT NULL DEFAULT '',
    "why_tempted_md" text NOT NULL DEFAULT '',
    "rule_md" text NOT NULL DEFAULT '',
    "item_type" text NOT NULL DEFAULT '',
    "reviewed" boolean NOT NULL DEFAULT false,
    "generated_by" text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS "test_blueprint" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "skill_mix" jsonb NOT NULL DEFAULT '{}'::jsonb,
    "difficulty_dist" jsonb NOT NULL DEFAULT '{}'::jsonb,
    "count" integer NOT NULL,
    "minutes" integer NOT NULL,
    "scale_band_table" jsonb NOT NULL DEFAULT '[]'::jsonb,
    "pass_criteria" jsonb,
    "seed" integer NOT NULL
);

CREATE TABLE IF NOT EXISTS "quiz_session" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "learner_id" text NOT NULL,
    "mode" text NOT NULL,
    "skill_focus" text REFERENCES "skill" ("id") ON DELETE SET NULL,
    "started_at" timestamptz NOT NULL DEFAULT now(),
    "ended_at" timestamptz,
    "score_correct" integer NOT NULL DEFAULT 0,
    "score_total" integer NOT NULL DEFAULT 0,
    "target_count" integer
);

CREATE TABLE IF NOT EXISTS "attempt" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "session_id" text NOT NULL REFERENCES "quiz_session" ("id") ON DELETE CASCADE,
    "question_id" text NOT NULL,
    "chosen_letter" text NOT NULL,
    "correct" boolean NOT NULL,
    "elapsed_ms" integer NOT NULL DEFAULT 0,
    "used_hint" boolean NOT NULL DEFAULT false,
    "created_at" timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "skill_state" (
    "subject" text NOT NULL DEFAULT 'act-english',
    "skill_id" text NOT NULL REFERENCES "skill" ("id") ON DELETE CASCADE,
    "learner_id" text NOT NULL,
    "mastery" real NOT NULL DEFAULT 0,
    "last_seen" timestamptz,
    "fsrs_stability" real NOT NULL DEFAULT 0,
    "fsrs_difficulty" real NOT NULL DEFAULT 0,
    "due_at" timestamptz NOT NULL DEFAULT now(),
    "fsrs_card" jsonb,
    PRIMARY KEY ("subject", "skill_id", "learner_id")
);

CREATE TABLE IF NOT EXISTS "tutorial" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "skill_id" text NOT NULL REFERENCES "skill" ("id") ON DELETE CASCADE,
    "body_md" text NOT NULL DEFAULT '',
    "examples" jsonb NOT NULL DEFAULT '[]'::jsonb,
    "generated_from" text NOT NULL DEFAULT 'rule',
    "reviewed" boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS "content_string" (
    "subject" text NOT NULL DEFAULT 'act-english',
    "key" text NOT NULL,
    "locale" text NOT NULL DEFAULT 'en',
    "value" text NOT NULL DEFAULT '',
    PRIMARY KEY ("subject", "key", "locale")
);

CREATE TABLE IF NOT EXISTS "progress_point" (
    "id" text PRIMARY KEY NOT NULL,
    "subject" text NOT NULL DEFAULT 'act-english',
    "learner_id" text NOT NULL,
    "at" timestamptz NOT NULL DEFAULT now(),
    "projected_score" real NOT NULL DEFAULT 0,
    "items_reviewed" integer NOT NULL DEFAULT 0
);

-- Threads + coach-marker (FR-F3) — copied from
-- lib/adapters/thread_store/db/migrations/{0000_init_threads,0001_coach_session_marker}.sql

CREATE TABLE IF NOT EXISTS "threads" (
    "thread_id"   text PRIMARY KEY NOT NULL,
    "user_id"     text NOT NULL,
    "title"       text NOT NULL DEFAULT 'New chat',
    "messages"    jsonb NOT NULL DEFAULT '[]'::jsonb,
    "metadata"    jsonb NOT NULL DEFAULT '{}'::jsonb,
    "created_at"  timestamptz NOT NULL DEFAULT now(),
    "updated_at"  timestamptz NOT NULL DEFAULT now(),
    "archived_at" timestamptz
);

CREATE INDEX IF NOT EXISTS "threads_user_created_idx"
    ON "threads" ("user_id", "created_at" DESC)
    WHERE "archived_at" IS NULL;

CREATE TABLE IF NOT EXISTS "thread_messages" (
    "id"         uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "thread_id"  text NOT NULL REFERENCES "threads" ("thread_id") ON DELETE CASCADE,
    "role"       text NOT NULL,
    "content"    text NOT NULL DEFAULT '',
    "created_at" timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "coach_session_marker" (
    "user_id"      text NOT NULL,
    "question_id"  text NOT NULL,
    "submitted_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "coach_session_marker_user_id_question_id_pk"
        PRIMARY KEY ("user_id", "question_id")
);
