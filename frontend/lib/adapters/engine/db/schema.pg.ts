/**
 * Drizzle schema (Postgres dialect) for the Subject-Coach engine.
 *
 * This is the **canonical / online** table definition for the eight engine
 * entities (ADR-0005 substrate decision: Postgres/Neon is canonical, SQLite is
 * the on-device twin in `schema.sqlite.ts`). It is co-located under
 * `frontend/lib/adapters/engine/db/` so the drizzle/pg vendor imports stay
 * inside `lib/adapters/**` (F-R2 SDK confinement), exactly like
 * `adapters/thread_store/db/schema.ts`. The engine core depends only on the
 * ADR-0006 port interfaces; this file is consumed by drizzle-kit at
 * migrate/generate time and by the Drizzle repo adapters at runtime, never by
 * anything upstream of the adapter.
 *
 * WHAT this backs: design doc §2.1 (entity model). WHY it is shaped this way:
 *   - ADR-0005 — engine home (Frontend-Ring local-first) + substrate.
 *   - ADR-0006 — the seven component protocols the repos implement.
 *   - preact-english-coach-engine.spec.md — the FRs these tables satisfy.
 *
 * Dual-dialect rule (ADR-0005 consequence, see README.md): NO Postgres-only
 * column types on tables that also live in the on-device SQLite store. JSON ->
 * `jsonb` here / `text({ mode: "json" })` in SQLite; timestamps ->
 * `timestamp` here / `integer({ mode: "timestamp" })` in SQLite. The two files
 * MUST stay column-for-column identical in name, nullability, and default
 * intent — `schema.spec` (FR-G3) compiles both and a parity test guards drift.
 *
 * IR-NEON-5 analogue: these engine tables are added to the drizzle.config
 * `tablesFilter` whitelist; the LangGraph checkpoint tables (`checkpoints`,
 * `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) remain
 * intentionally ABSENT so drizzle-kit never regenerates them.
 *
 * `subject` defaults to 'act-english' on every table — the single discriminator
 * column that keeps the schema open for Math/Science without making it abstract
 * (engine spec FR-H1). A new subject is new rows + a new Grader adapter + a new
 * renderer-registry entry; this schema does not change.
 */

import { sql } from "drizzle-orm";
import {
  boolean,
  integer,
  jsonb,
  pgTable,
  primaryKey,
  real,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

const DEFAULT_SUBJECT = "act-english";

/**
 * skill — the subject taxonomy + share-of-test weighting.
 * Backs BucketCardVM, the mastery grid, and the Skill-detail header.
 * Read-only mastery lives in `skillState`, never here (ADR-0006 SkillTaxonomy
 * is read-only; mastery is the Scheduler's concern).
 */
export const skill = pgTable("skill", {
  id: uuid("id").primaryKey().defaultRandom(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  // Stable key used by content + code: 'punctuation', 'rhetoric', ...
  key: text("key").notNull(),
  name: text("name").notNull(),
  // Share of the ACT English test this bucket represents (e.g. 13.0).
  share_of_test_pct: real("share_of_test_pct").notNull().default(0),
  // The bucket's accent custom-property value (design system, UI spec FR-A3).
  accent_var: text("accent_var").notNull().default(""),
  description: text("description").notNull().default(""),
  // Display ordering in the mastery grid.
  order: integer("order").notNull().default(0),
});

/**
 * question — one item (English: an underlined-span multiple-choice item).
 * Body is LLM-generated offline and verifier-gated; `reviewed = false` rows
 * MUST NOT reach a learner (engine spec FR-B*). `item_type` drives the
 * client-side renderer registry, not a `switch(subject)` (FR-H2).
 */
export const question = pgTable("question", {
  id: uuid("id").primaryKey().defaultRandom(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  skill_id: uuid("skill_id")
    .notNull()
    .references(() => skill.id, { onDelete: "cascade" }),
  difficulty: integer("difficulty").notNull().default(3), // 1..5
  // The context sentence carrying the underlined-span markup (UI spec FR-A6).
  context_html: text("context_html").notNull().default(""),
  stem: text("stem").notNull().default(""),
  // [{ letter, label, isNoChange }] — choice A is "NO CHANGE" for English.
  choices: jsonb("choices").notNull().default([]),
  answer_letter: text("answer_letter").notNull(),
  // { A: "...", B: "...", ... } per-choice rationale, keyed by letter.
  per_choice_rationale: jsonb("per_choice_rationale").notNull().default({}),
  why_correct_md: text("why_correct_md").notNull().default(""),
  why_tempted_md: text("why_tempted_md").notNull().default(""),
  rule_md: text("rule_md").notNull().default(""),
  // Renderer-registry key (English: 'underlined-span-mc').
  item_type: text("item_type").notNull().default("underlined-span-mc"),
  // The hard gate: only reviewed=true reaches a learner (FR-B1/B2).
  reviewed: boolean("reviewed").notNull().default(false),
  // Provenance for audit (FR-B4 / FR-E3): which model/run produced this.
  generated_by: text("generated_by").notNull().default(""),
});

/**
 * hint — reviewed-gated hint-ladder rungs (ADR-0012/ADR-0014, spec FR-12/20).
 * One rung per level per question (unique index); `reviewed = true` is EARNED
 * by the generator's verifier cascade (deterministic per-rung leakage check
 * first) — `reviewed = false` rows MUST NOT reach a learner. `generated_by`
 * is "authored" or "<model>@<run_id>" (provenance, FR-B4-analog).
 */
export const hint = pgTable(
  "hint",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    subject: text("subject").notNull().default(DEFAULT_SUBJECT),
    question_id: uuid("question_id")
      .notNull()
      .references(() => question.id, { onDelete: "cascade" }),
    rung: integer("rung").notNull(), // 1..3; assertion rung unrepresentable at the wire
    body_md: text("body_md").notNull(),
    reviewed: boolean("reviewed").notNull().default(false),
    generated_by: text("generated_by").notNull().default(""),
  },
  (t) => [uniqueIndex("hint_question_rung_uq").on(t.question_id, t.rung)],
);

/**
 * quiz_session — one drill/adaptive/review session.
 * Score tally is stored (set on close) so the UI Summary derives from stored
 * values, not re-computation (engine spec FR-D3).
 */
export const quizSession = pgTable("quiz_session", {
  id: uuid("id").primaryKey().defaultRandom(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  learner_id: text("learner_id").notNull(),
  // 'adaptive' | 'drill' | 'review'.
  mode: text("mode").notNull(),
  // Present for drill sessions scoped to one skill (FR-A5); null otherwise.
  skill_focus: uuid("skill_focus").references(() => skill.id, {
    onDelete: "set null",
  }),
  started_at: timestamp("started_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  ended_at: timestamp("ended_at", { withTimezone: true }),
  score_correct: integer("score_correct").notNull().default(0),
  score_total: integer("score_total").notNull().default(0),
});

/**
 * attempt — append-only history of one answered item.
 * `correct` comes from the Grader Verdict; `used_hint` is auditable but never
 * changes recorded correctness (engine spec FR-D5).
 */
export const attempt = pgTable("attempt", {
  id: uuid("id").primaryKey().defaultRandom(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  session_id: uuid("session_id")
    .notNull()
    .references(() => quizSession.id, { onDelete: "cascade" }),
  question_id: uuid("question_id")
    .notNull()
    .references(() => question.id, { onDelete: "cascade" }),
  chosen_letter: text("chosen_letter").notNull(),
  correct: boolean("correct").notNull(),
  elapsed_ms: integer("elapsed_ms").notNull().default(0),
  used_hint: boolean("used_hint").notNull().default(false),
  created_at: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

/**
 * skill_state — the adaptivity source of truth (engine spec FR-A2).
 * The Scheduler (FSRS) port is the ONLY writer. Composite PK keeps one row per
 * (subject, skill, learner). `due_at` + `mastery` drive next-item selection.
 */
export const skillState = pgTable(
  "skill_state",
  {
    subject: text("subject").notNull().default(DEFAULT_SUBJECT),
    skill_id: uuid("skill_id")
      .notNull()
      .references(() => skill.id, { onDelete: "cascade" }),
    learner_id: text("learner_id").notNull(),
    mastery: real("mastery").notNull().default(0), // 0..1
    last_seen: timestamp("last_seen", { withTimezone: true }),
    fsrs_stability: real("fsrs_stability").notNull().default(0),
    fsrs_difficulty: real("fsrs_difficulty").notNull().default(0),
    due_at: timestamp("due_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
    // Opaque full FSRS card snapshot (the Scheduler's vendor boundary). The
    // named columns above are the durable projection; this preserves the card's
    // state machine across reviews so intervals grow. Null until first review.
    fsrs_card: jsonb("fsrs_card"),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.subject, t.skill_id, t.learner_id] }),
  }),
);

/**
 * tutorial — the "rule in one line" + examples for a skill.
 * Same reviewed-gate as `question` (FR-B*). Generated offline, gated before
 * a learner sees it.
 */
export const tutorial = pgTable("tutorial", {
  id: uuid("id").primaryKey().defaultRandom(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  skill_id: uuid("skill_id")
    .notNull()
    .references(() => skill.id, { onDelete: "cascade" }),
  body_md: text("body_md").notNull().default(""),
  examples: jsonb("examples").notNull().default([]),
  // 'rule' | 'misses' — what the tutorial was generated from.
  generated_from: text("generated_from").notNull().default("rule"),
  reviewed: boolean("reviewed").notNull().default(false),
});

/**
 * content_string — the objective plane: every UI label, keyed by
 * (subject, key, locale). Behind the ContentRepo port; an in-repo bundle now,
 * a CMS later (engine spec FR-F3). Subject is a dimension alongside locale.
 */
export const contentString = pgTable(
  "content_string",
  {
    subject: text("subject").notNull().default(DEFAULT_SUBJECT),
    // e.g. 'screen.dashboard.greeting'.
    key: text("key").notNull(),
    locale: text("locale").notNull().default("en"),
    value: text("value").notNull().default(""),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.subject, t.key, t.locale] }),
  }),
);

/**
 * progress_point — sampled progress for the trend line (UI spec FR-I1).
 * Can be derived from attempts; stored here for a stable, cheap read.
 */
export const progressPoint = pgTable("progress_point", {
  id: uuid("id").primaryKey().defaultRandom(),
  subject: text("subject").notNull().default(DEFAULT_SUBJECT),
  learner_id: text("learner_id").notNull(),
  at: timestamp("at", { withTimezone: true }).notNull().defaultNow(),
  projected_score: real("projected_score").notNull().default(0),
  items_reviewed: integer("items_reviewed").notNull().default(0),
});

// Row types — the adapters convert these to wire/view-model shapes; the UI
// never imports these directly (engine spec §4 / F-R1).
export type SkillRowPg = typeof skill.$inferSelect;
export type SkillInsertPg = typeof skill.$inferInsert;
export type QuestionRowPg = typeof question.$inferSelect;
export type QuestionInsertPg = typeof question.$inferInsert;
export type QuizSessionRowPg = typeof quizSession.$inferSelect;
export type QuizSessionInsertPg = typeof quizSession.$inferInsert;
export type AttemptRowPg = typeof attempt.$inferSelect;
export type AttemptInsertPg = typeof attempt.$inferInsert;
export type SkillStateRowPg = typeof skillState.$inferSelect;
export type SkillStateInsertPg = typeof skillState.$inferInsert;
export type TutorialRowPg = typeof tutorial.$inferSelect;
export type TutorialInsertPg = typeof tutorial.$inferInsert;
export type ContentStringRowPg = typeof contentString.$inferSelect;
export type ContentStringInsertPg = typeof contentString.$inferInsert;
export type ProgressPointRowPg = typeof progressPoint.$inferSelect;
export type ProgressPointInsertPg = typeof progressPoint.$inferInsert;

// The engine-table whitelist for the IR-NEON-5 `tablesFilter` (see README.md).
// Exported so drizzle.config can reference one source of truth.
export const ENGINE_TABLE_NAMES = [
  "skill",
  "question",
  "hint",
  "quiz_session",
  "attempt",
  "skill_state",
  "tutorial",
  "content_string",
  "progress_point",
] as const;

// Suppress unused-import lint until a CHECK constraint or default uses `sql`.
// (Kept imported so the SQLite twin and this file share an identical import
// surface for the parity check.)
export const __schema_sql_marker = sql;
