/**
 * EngineDb — the narrow row-level port the engine repos are written against.
 *
 * This is the engine analogue of `thread_store`'s `DrizzleLike`: the repos
 * (QuestionRepo, AttemptRepo, SessionRepo, SkillTaxonomy, ContentRepo, and the
 * Scheduler's `skill_state` writes) depend ONLY on this tiny interface, so the
 * Drizzle/SQLite query-builder never leaks into repo logic or tests. Two
 * implementations satisfy it:
 *   - `InMemoryEngineDb` (behavioral fake; L1 tests + dev) — `in_memory_engine_db.ts`
 *   - `drizzleEngineDb(...)` (the live pg/sqlite SDK seam) — `drizzle_engine_db.ts`
 *
 * Rows are the pure `wire/engine_entities` shapes (snake_case, ISO-string
 * timestamps) — the SDK seam is the only place that maps a Drizzle row to these
 * (Rule A4 / F-R8: no vendor type escapes the adapter).
 *
 * This module imports only the wire shapes + the typed error (no SDK), so it can
 * be imported by the repos without pulling Drizzle into their unit tests.
 */

import type {
  Attempt,
  Hint,
  ProgressPoint,
  Question,
  QuizSession,
  Skill,
  SkillState,
  TestBlueprint,
  TestItem,
  Tutorial,
} from "../../../wire/engine_entities";

/** The score+close patch SessionRepo applies (FR-D3). */
export type SessionClosePatch = {
  ended_at: string;
  score_correct: number;
  score_total: number;
};

/**
 * ReadableEngineDb — the read-only projection of the `skill_state` seam the
 * ADR-0011 `LearnerReadRepo` adapter depends on.
 *
 * The full `EngineDb` (below) exposes `upsertSkillState` (the Scheduler's write
 * path, FR-A2). `DrizzleLearnerReadRepo` must NOT be able to reach that write —
 * so it is typed against this narrow interface, which structurally omits every
 * mutation method. `EngineDb extends ReadableEngineDb`, so both the live
 * `pgEngineDb` and the `InMemoryEngineDb` fake satisfy it for free; the compiler
 * is the enforcement that read-only-by-construction holds (the deliberate
 * rejection of an assert-in-prose hedge — see ADR-0011 §Trade-off).
 */
export interface ReadableEngineDb {
  /** All `skill_state` rows for a learner (per-skill mastery, due, FSRS fields). */
  listSkillState(subject: string, learnerId: string): Promise<SkillState[]>;
}

/**
 * Row-level engine store. Behavioral (records + answers), not a mock of internal
 * calls — both the fake and the live seam implement the same observable
 * behavior, and the conformance suite runs against both.
 */
export interface EngineDb extends ReadableEngineDb {
  // --- skill (taxonomy; read-only via SkillTaxonomy) ---
  listSkills(subject: string): Promise<Skill[]>;
  getSkillByKey(subject: string, key: string): Promise<Skill | null>;
  /** Used by Scheduler seeding (FR-A7) to know which skills exist. */
  listSkillIds(subject: string): Promise<string[]>;

  // --- question (reviewed gate lives in the repo, but the filter is pushed down) ---
  /**
   * Next reviewed question for a skill (reviewed=true ONLY), or null.
   * `excludeIds` skips already-served ids (S3, FR-9); the reviewed gate is
   * unchanged and all-excluded → null (FR-11/FR-12). Omitted/empty → today's
   * behaviour.
   */
  nextReviewedQuestion(
    subject: string,
    skillId: string,
    excludeIds?: readonly string[],
  ): Promise<Question | null>;
  getQuestion(id: string): Promise<Question | null>;
  insertQuestion(q: Question): Promise<void>;

  // --- hint (ADR-0014; same pushed-down reviewed gate as question) ---
  /** The question's ladder, reviewed=true ONLY, ordered by rung ascending. */
  listReviewedHints(subject: string, questionId: string): Promise<Hint[]>;
  /** Rejects a duplicate (question_id, rung) — one rung per level (ADR-0014). */
  insertHint(h: Hint): Promise<void>;

  // --- test_item (ADR-0015; same pushed-down reviewed gate as question) ---
  /** Reviewed=true exam items for a subject ONLY (FR-27.1); [] when none. */
  listReviewedTestItems(subject: string): Promise<TestItem[]>;
  insertTestItem(item: TestItem): Promise<void>;

  // --- test_blueprint (ADR-0015) ---
  getTestBlueprint(id: string): Promise<TestBlueprint | null>;
  insertTestBlueprint(bp: TestBlueprint): Promise<void>;

  // --- quiz_session ---
  insertSession(s: QuizSession): Promise<void>;
  getSession(id: string): Promise<QuizSession | null>;
  patchSessionClose(id: string, patch: SessionClosePatch): Promise<QuizSession | null>;
  /**
   * Closed sessions for a learner, newest-first by ended_at; optional lower
   * bound. Excludes rows where ended_at IS NULL (ADR-0026 / C1 rail).
   */
  listClosedSessionsByLearner(
    subject: string,
    learnerId: string,
    options?: { sinceISO?: string },
  ): Promise<QuizSession[]>;

  // --- attempt ---
  insertAttempt(a: Attempt): Promise<void>;
  /** Incorrect attempts for a learner, newest-first (FR-D4). */
  listMisses(subject: string, learnerId: string): Promise<Attempt[]>;
  /**
   * The `question_id`s answered in one session (any correctness) — the S3
   * served-set projection (FR-13). A `question_id`-only read scoped by
   * `session_id`; order is not significant (the caller uses it as a set).
   */
  listSessionQuestionIds(sessionId: string): Promise<string[]>;
  /**
   * The distinct skills served in one session, **newest-first** (S3.1, FR-5) —
   * the round-robin rotation projection (ADR-0024). Joins the session's
   * append-only `attempt` rows to their questions (`attempt.question_id →
   * question.skill_id`), orders by attempt `created_at` descending, and de-dups
   * keeping each skill's newest occurrence. Like `listSessionQuestionIds` this
   * is derived from `attempt` only — NEVER `skill_state` (FR-13 purity). `[]`
   * when the session has no attempts.
   */
  listSessionSkillIds(sessionId: string): Promise<string[]>;

  // --- skill_state (Scheduler is the only writer; repos read for adaptivity) ---
  // `listSkillState` is inherited from ReadableEngineDb (the ADR-0011 read seam).
  getSkillState(
    subject: string,
    skillId: string,
    learnerId: string,
  ): Promise<SkillState | null>;
  /** Upsert one skill_state row — invoked ONLY by the Scheduler adapter (FR-A2). */
  upsertSkillState(state: SkillState): Promise<void>;

  // --- content_string ---
  getContentString(
    subject: string,
    key: string,
    locale: string,
  ): Promise<string | null>;
  listContentStrings(
    subject: string,
    locale: string,
  ): Promise<Array<{ key: string; value: string }>>;

  // --- tutorial / progress_point (read paths used by translators/UI) ---
  getTutorial(subject: string, skillId: string): Promise<Tutorial | null>;
  listProgressPoints(subject: string, learnerId: string): Promise<ProgressPoint[]>;
}
