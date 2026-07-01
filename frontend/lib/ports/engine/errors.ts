/**
 * Typed errors for the Subject-Coach engine ports (Rule P4).
 *
 * Every engine repo/port method that can fail surfaces an `EngineError`
 * subclass — never a raw Drizzle/SQLite vendor error (mirrors `ThreadStoreError`
 * in the thread_store adapter, Rule A5). Consumers `catch` on type, not on
 * string matching.
 *
 * This is `ports/`-local shared infrastructure (not a port interface), so it is
 * a `.ts` module under `ports/engine/` that the conformance suite skips (it is
 * not one of the seven interface files).
 */

/** Base for every engine persistence/contract failure. */
export class EngineError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EngineError";
  }
}

/** A repository (QuestionRepo, AttemptRepo, SessionRepo, ContentRepo, SkillTaxonomy) operation failed. */
export class EngineRepoError extends EngineError {
  constructor(message: string) {
    super(message);
    this.name = "EngineRepoError";
  }
}

/** The Scheduler (FSRS) failed to pick or to apply a review. */
export class SchedulerError extends EngineError {
  constructor(message: string) {
    super(message);
    this.name = "SchedulerError";
  }
}

/** A requested entity was not found (kept distinct so callers can 404 vs 500). */
export class EngineNotFoundError extends EngineError {
  constructor(message: string) {
    super(message);
    this.name = "EngineNotFoundError";
  }
}
