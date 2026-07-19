/**
 * Drizzle schema (SQLite dialect) for the Subject-Coach engine — the on-device
 * twin of `schema.pg.ts`.
 *
 * ADR-0005 substrate: the learner-facing engine runs local-first on-device
 * (Frontend-Ring, under Capacitor). Postgres/Neon is the canonical/online
 * store; this SQLite schema is the working store for the single learner offline
 * (engine spec FR-G1). One Drizzle schema authored twice — same columns, same
 * names, same nullability and default intent — only the dialect-specific column
 * types differ. The parity is the whole point: FR-G3 compiles both and a parity
 * test guards drift.
 *
 * Dialect mapping (the only differences from schema.pg.ts):
 *   - uuid("id").primaryKey().defaultRandom()  ->  text("id").primaryKey()  (+ app-supplied uuid)
 *   - jsonb(col)                               ->  text(col, { mode: "json" })
 *   - boolean(col)                             ->  integer(col, { mode: "boolean" })
 *   - timestamp(col, { withTimezone: true })   ->  integer(col, { mode: "timestamp" })
 *   - real / integer / text                    ->  unchanged
 * Everything else (notNull, defaults, references, composite PKs, the `subject`
 * discriminator default) is identical to the Postgres file.
 *
 * SDK confinement (F-R2): drizzle-orm/sqlite-core is imported only here, under
 * `lib/adapters/**`. IR-NEON-5 analogue applies on the Postgres side; the local
 * SQLite store never holds LangGraph checkpoint tables either.
 */

import { sql } from "drizzle-orm";
import {
  integer,
  primaryKey,
  real,
  sqliteTable,
  text,
  uniqueIndex,
} from "drizzle-orm/sqlite-core";

const DEFAULT_SUBJECT = "act-english";

/** skill — see schema.pg.ts for column intent. */
export const skill = sqliteTable("skill", {
  // SQLite has no native UUID; ids are app-supplied uuid strings.
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  key: text("key").notNull(),
  name: text("name").notNull(),
  share_of_test_pct: real("share_of_test_pct").notNull().default(0),
  accent_var: text("accent_var").notNull().default(""),
  description: text("description").notNull().default(""),
  order: integer("order").notNull().default(0),
});

/** question — reviewed-gated; see schema.pg.ts. */
export const question = sqliteTable("question", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  skill_id: text("skill_id")
    .notNull()
    .references(() => skill.id, { onDelete: "cascade" }),
  difficulty: integer("difficulty").notNull().default(3), // 1..5
  context_html: text("context_html").notNull().default(""),
  stem: text("stem").notNull().default(""),
  choices: text("choices", { mode: "json" }).notNull().default([]),
  answer_letter: text("answer_letter").notNull(),
  per_choice_rationale: text("per_choice_rationale", { mode: "json" })
    .notNull()
    .default({}),
  why_correct_md: text("why_correct_md").notNull().default(""),
  why_tempted_md: text("why_tempted_md").notNull().default(""),
  rule_md: text("rule_md").notNull().default(""),
  item_type: text("item_type").notNull().default("underlined-span-mc"),
  reviewed: integer("reviewed", { mode: "boolean" }).notNull().default(false),
  generated_by: text("generated_by").notNull().default(""),
});

/** hint — reviewed-gated hint-ladder rungs (ADR-0014/ADR-0035); see schema.pg.ts. */
export const hint = sqliteTable(
  "hint",
  {
    id: text("id").primaryKey(),
    subject: text("subject").notNull().default(DEFAULT_SUBJECT),
    question_id: text("question_id")
      .notNull()
      .references(() => question.id, { onDelete: "cascade" }),
    choice_letter: text("choice_letter"), // null | A–D (ADR-0035)
    rung: integer("rung").notNull(), // 1..3; assertion rung unrepresentable at the wire
    body_md: text("body_md").notNull(),
    reviewed: integer("reviewed", { mode: "boolean" }).notNull().default(false),
    generated_by: text("generated_by").notNull().default(""),
  },
  (t) => [
    uniqueIndex("hint_item_level_uq")
      .on(t.question_id, t.rung)
      .where(sql`${t.choice_letter} is null`),
    uniqueIndex("hint_choice_level_uq")
      .on(t.question_id, t.choice_letter, t.rung)
      .where(sql`${t.choice_letter} is not null`),
  ],
);

/**
 * test_item — governed exam-item bank (ADR-0015); see schema.pg.ts. SEPARATE
 * from `question` so practice scheduling can never serve an exam item.
 * `reviewed = true` is EARNED by the Python cascade — no FK to `question`.
 */
export const testItem = sqliteTable("test_item", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  skill_id: text("skill_id")
    .notNull()
    .references(() => skill.id, { onDelete: "cascade" }),
  difficulty: integer("difficulty").notNull().default(3), // 1..5
  context_html: text("context_html").notNull().default(""),
  stem_md: text("stem_md").notNull(),
  choices: text("choices", { mode: "json" }).notNull().default([]),
  answer_letter: text("answer_letter").notNull(),
  // Teaching fields (ADR-0021 — amends the ADR-0015 minimal exam shape): the
  // bank also serves the practice quiz, whose Feedback renders these.
  per_choice_rationale: text("per_choice_rationale", { mode: "json" })
    .notNull()
    .default({}),
  why_correct_md: text("why_correct_md").notNull().default(""),
  why_tempted_md: text("why_tempted_md").notNull().default(""),
  rule_md: text("rule_md").notNull().default(""),
  item_type: text("item_type").notNull().default(""),
  // Author-captured one-line misconception (C2 / ADR-0027). Null = honest-absent.
  misconception: text("misconception"),
  reviewed: integer("reviewed", { mode: "boolean" }).notNull().default(false),
  generated_by: text("generated_by").notNull().default(""),
});

/** test_blueprint — deterministic test-form recipe (ADR-0015); see schema.pg.ts. */
export const testBlueprint = sqliteTable("test_blueprint", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  skill_mix: text("skill_mix", { mode: "json" }).notNull().default({}),
  difficulty_dist: text("difficulty_dist", { mode: "json" }).notNull().default({}),
  count: integer("count").notNull(),
  minutes: integer("minutes").notNull(),
  scale_band_table: text("scale_band_table", { mode: "json" }).notNull().default([]),
  pass_criteria: text("pass_criteria", { mode: "json" }),
  seed: integer("seed").notNull(),
});

/** quiz_session — score tally stored on close; see schema.pg.ts. */
export const quizSession = sqliteTable("quiz_session", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  learner_id: text("learner_id").notNull(),
  mode: text("mode").notNull(), // 'adaptive' | 'drill' | 'review'
  skill_focus: text("skill_focus").references(() => skill.id, {
    onDelete: "set null",
  }),
  started_at: integer("started_at", { mode: "timestamp" })
    .notNull()
    .default(sql`(unixepoch())`),
  ended_at: integer("ended_at", { mode: "timestamp" }),
  score_correct: integer("score_correct").notNull().default(0),
  score_total: integer("score_total").notNull().default(0),
  // Bounded-session length (S3) — parity twin of schema.pg.ts. Nullable, no
  // default: NULL = endless; a pre-S3 row reads NULL → `target_count: null`.
  target_count: integer("target_count"),
});

/** attempt — append-only; `used_hint` never changes correctness. */
export const attempt = sqliteTable("attempt", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  session_id: text("session_id")
    .notNull()
    .references(() => quizSession.id, { onDelete: "cascade" }),
  question_id: text("question_id")
    .notNull()
    .references(() => question.id, { onDelete: "cascade" }),
  chosen_letter: text("chosen_letter").notNull(),
  correct: integer("correct", { mode: "boolean" }).notNull(),
  elapsed_ms: integer("elapsed_ms").notNull().default(0),
  used_hint: integer("used_hint", { mode: "boolean" }).notNull().default(false),
  created_at: integer("created_at", { mode: "timestamp" })
    .notNull()
    .default(sql`(unixepoch())`),
  // Commit-first FR-10: set only on the resolving attempt. Null = legacy /
  // non-resolving row (no backfill). Values: first_try | coached | walked_through.
  resolution: text("resolution"),
});

/** skill_state — adaptivity source of truth; FSRS is the only writer. */
export const skillState = sqliteTable(
  "skill_state",
  {
    subject: text("subject").notNull().default(DEFAULT_SUBJECT),
    skill_id: text("skill_id")
      .notNull()
      .references(() => skill.id, { onDelete: "cascade" }),
    learner_id: text("learner_id").notNull(),
    mastery: real("mastery").notNull().default(0), // 0..1
    last_seen: integer("last_seen", { mode: "timestamp" }),
    fsrs_stability: real("fsrs_stability").notNull().default(0),
    fsrs_difficulty: real("fsrs_difficulty").notNull().default(0),
    due_at: integer("due_at", { mode: "timestamp" })
      .notNull()
      .default(sql`(unixepoch())`),
    // Opaque full FSRS card snapshot — see schema.pg.ts. Null until first review.
    fsrs_card: text("fsrs_card", { mode: "json" }),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.subject, t.skill_id, t.learner_id] }),
  }),
);

/** tutorial — reviewed-gated; see schema.pg.ts. Optional teaching fields ADR-0028. */
export const tutorial = sqliteTable("tutorial", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  skill_id: text("skill_id")
    .notNull()
    .references(() => skill.id, { onDelete: "cascade" }),
  body_md: text("body_md").notNull().default(""),
  examples: text("examples", { mode: "json" }).notNull().default([]),
  generated_from: text("generated_from").notNull().default("rule"),
  reviewed: integer("reviewed", { mode: "boolean" }).notNull().default(false),
  // Optional teaching fields (ADR-0028). Null = content without that asset.
  ground_md: text("ground_md"),
  pitfall_md: text("pitfall_md"),
  question_md: text("question_md"),
  self_explain_prompt: text("self_explain_prompt"),
  worked_example: text("worked_example", { mode: "json" }),
  completion_try: text("completion_try", { mode: "json" }),
  annotated_examples: text("annotated_examples", { mode: "json" }),
});

/** content_string — objective plane; PK (subject, key, locale). */
export const contentString = sqliteTable(
  "content_string",
  {
    subject: text("subject").notNull().default(DEFAULT_SUBJECT),
    key: text("key").notNull(),
    locale: text("locale").notNull().default("en"),
    value: text("value").notNull().default(""),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.subject, t.key, t.locale] }),
  }),
);

/** progress_point — sampled trend points. */
export const progressPoint = sqliteTable("progress_point", {
  id: text("id").primaryKey(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  learner_id: text("learner_id").notNull(),
  at: integer("at", { mode: "timestamp" })
    .notNull()
    .default(sql`(unixepoch())`),
  projected_score: real("projected_score").notNull().default(0),
  items_reviewed: integer("items_reviewed").notNull().default(0),
});

// Row types (SQLite dialect). Structurally these match the Postgres row types
// except `Date` vs `Date` (both modes decode to Date) and boolean columns
// decode to `boolean` in both — so the adapter's wire conversion is identical.
export type SkillRowSqlite = typeof skill.$inferSelect;
export type SkillInsertSqlite = typeof skill.$inferInsert;
export type QuestionRowSqlite = typeof question.$inferSelect;
export type QuestionInsertSqlite = typeof question.$inferInsert;
export type QuizSessionRowSqlite = typeof quizSession.$inferSelect;
export type QuizSessionInsertSqlite = typeof quizSession.$inferInsert;
export type AttemptRowSqlite = typeof attempt.$inferSelect;
export type AttemptInsertSqlite = typeof attempt.$inferInsert;
export type SkillStateRowSqlite = typeof skillState.$inferSelect;
export type SkillStateInsertSqlite = typeof skillState.$inferInsert;
export type TutorialRowSqlite = typeof tutorial.$inferSelect;
export type TutorialInsertSqlite = typeof tutorial.$inferInsert;
export type ContentStringRowSqlite = typeof contentString.$inferSelect;
export type ContentStringInsertSqlite = typeof contentString.$inferInsert;
export type ProgressPointRowSqlite = typeof progressPoint.$inferSelect;
export type ProgressPointInsertSqlite = typeof progressPoint.$inferInsert;
