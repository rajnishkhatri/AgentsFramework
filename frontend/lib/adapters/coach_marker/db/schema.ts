/**
 * Drizzle schema for the coach_session_marker table (ADR-0012 Amendment).
 *
 * BFF-side minimal state — never queried by the Python backend. Co-located
 * under `lib/adapters/coach_marker/db/` so the drizzle vendor import stays
 * inside `lib/adapters/**` (F-R2). Consumed by drizzle-kit at generate time
 * and by `PgCoachMarkerRepo` at runtime, never by anything upstream of the
 * adapter.
 *
 * Monotonic by construction: the repo only ever INSERTs (ON CONFLICT DO
 * NOTHING) — no update or delete statement exists against this table.
 *
 * IR-NEON-5: this table must be added to `drizzle.config.ts`
 * APPLICATION_TABLES (inclusive whitelist) in the same commit.
 */

import { pgTable, primaryKey, text, timestamp } from "drizzle-orm/pg-core";

export const coach_session_marker = pgTable(
  "coach_session_marker",
  {
    user_id: text("user_id").notNull(),
    question_id: text("question_id").notNull(),
    submitted_at: timestamp("submitted_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
  },
  (table) => [primaryKey({ columns: [table.user_id, table.question_id] })],
);
