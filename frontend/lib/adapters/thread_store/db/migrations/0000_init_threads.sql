-- 0000_init_threads.sql — initial schema for the V3 ThreadStore (Piece C).
--
-- Hand-authored (drizzle-kit is intentionally NOT a dependency yet, per
-- drizzle.config.ts; the runtime uses drizzle-orm only). Apply with psql or the
-- drizzle-orm/neon-http migrator. Mirrors lib/db/schema.ts exactly.
--
-- IR-NEON-5: this migration touches ONLY the application tables. The LangGraph
-- checkpoint tables (checkpoints / checkpoint_writes / checkpoint_blobs /
-- checkpoint_migrations) are owned by LangGraph's runtime and MUST NOT appear
-- here — drizzle.config.ts whitelists exactly `threads` + `thread_messages`.

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

-- list() is owner-scoped, newest-first, archived hidden — index the predicate.
CREATE INDEX IF NOT EXISTS "threads_user_created_idx"
    ON "threads" ("user_id", "created_at" DESC)
    WHERE "archived_at" IS NULL;

-- Reserved normalized message table (not written by the v1 repo; inline
-- threads.messages JSONB is the source of truth). Defined to keep the
-- IR-NEON-5 whitelist explicit for a future per-message migration.
CREATE TABLE IF NOT EXISTS "thread_messages" (
    "id"         uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
    "thread_id"  text NOT NULL REFERENCES "threads" ("thread_id") ON DELETE CASCADE,
    "role"       text NOT NULL,
    "content"    text NOT NULL DEFAULT '',
    "created_at" timestamptz NOT NULL DEFAULT now()
);
