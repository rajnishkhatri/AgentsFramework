/**
 * Drizzle schema for the V3 ThreadStore (live-infra Piece C).
 *
 * This is the production table definition behind `NeonFreeThreadStore` /
 * `NeonThreadRepo`. It is co-located under `lib/adapters/thread_store/db/` so
 * the drizzle/neon vendor imports stay inside `lib/adapters/**` (F-R2 SDK
 * confinement). The in-repo runtime adapter depends only on the narrow
 * `ThreadRepo` interface (A4 / F-R8); this file is consumed by drizzle-kit at
 * migrate/generate time and by `NeonThreadRepo` at runtime, never by anything
 * upstream of the adapter.
 *
 * IR-NEON-5: the LangGraph checkpoint tables (`checkpoints`,
 * `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) are owned by
 * LangGraph's runtime and are intentionally ABSENT here so drizzle-kit cannot
 * regenerate them. `drizzle.config.ts` whitelists exactly `threads` +
 * `thread_messages`.
 *
 * v1 stores the thread's message list as an inline JSONB column on `threads`
 * (the chat history the resume path replays). The `thread_messages` table is
 * defined to satisfy the IR-NEON-5 whitelist and reserve the normalized shape
 * for a future per-message migration; the v1 repo does not write to it.
 */

import {
  jsonb,
  pgTable,
  text,
  timestamp,
  uuid,
} from "drizzle-orm/pg-core";

export const threads = pgTable("threads", {
  thread_id: text("thread_id").primaryKey(),
  user_id: text("user_id").notNull(),
  title: text("title").notNull().default("New chat"),
  // Inline chat history (array of {role, content, ...}); the resume path
  // replays this. JSONB keeps it queryable and avoids a join for v1.
  messages: jsonb("messages").notNull().default([]),
  metadata: jsonb("metadata").notNull().default({}),
  created_at: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  // Soft-delete tombstone: list()/get() filter on `archived_at IS NULL`.
  archived_at: timestamp("archived_at", { withTimezone: true }),
});

/**
 * Reserved normalized message table (IR-NEON-5 whitelist member). Not written
 * by the v1 repo — the inline `threads.messages` JSONB is the source of truth
 * for now. Defining it here keeps the migration set explicit and lets a future
 * story migrate to per-row messages without a config change.
 */
export const threadMessages = pgTable("thread_messages", {
  id: uuid("id").primaryKey().defaultRandom(),
  thread_id: text("thread_id")
    .notNull()
    .references(() => threads.thread_id, { onDelete: "cascade" }),
  role: text("role").notNull(),
  content: text("content").notNull().default(""),
  created_at: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export type ThreadRowDb = typeof threads.$inferSelect;
export type ThreadRowInsert = typeof threads.$inferInsert;
