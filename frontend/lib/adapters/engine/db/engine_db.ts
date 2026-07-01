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
  ProgressPoint,
  Question,
  QuizSession,
  Skill,
  SkillState,
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
  /** Next reviewed question for a skill (reviewed=true ONLY), or null. */
  nextReviewedQuestion(subject: string, skillId: string): Promise<Question | null>;
  getQuestion(id: string): Promise<Question | null>;
  insertQuestion(q: Question): Promise<void>;

  // --- quiz_session ---
  insertSession(s: QuizSession): Promise<void>;
  getSession(id: string): Promise<QuizSession | null>;
  patchSessionClose(id: string, patch: SessionClosePatch): Promise<QuizSession | null>;

  // --- attempt ---
  insertAttempt(a: Attempt): Promise<void>;
  /** Incorrect attempts for a learner, newest-first (FR-D4). */
  listMisses(subject: string, learnerId: string): Promise<Attempt[]>;

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
