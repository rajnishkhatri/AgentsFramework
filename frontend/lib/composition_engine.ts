/**
 * Subject-Coach engine composition root (ADR-0006).
 *
 * The ONLY file that names the concrete engine adapter classes (Rule C2). It is
 * a separate composition root from `composition.ts` because the engine is a
 * Frontend-Ring-local bounded context (ADR-0005: learner-facing engine runs
 * on-device, local-first) — it selects its persistence (`EngineDb`) by
 * `DATABASE_URL` independently of the chat `ARCHITECTURE_PROFILE` switch, exactly
 * as `selectThreadRepo` does for threads.
 *
 * `buildEngineAdapters({ env })` returns the typed `EnginePortBag`. Consumers
 * (engine policy, translators, eventually a React provider) receive port
 * instances only — they never import a concrete adapter (Rule C1/C2).
 *
 * Substrate: no `DATABASE_URL` → `InMemoryEngineDb` (dev / tests / CI / the
 * on-device-before-DB path). With `DATABASE_URL` → the live Postgres seam
 * (`pgEngineDb`). The on-device SQLite seam is wired here too once the Capacitor
 * SQLite driver lands (it is the same `EngineDb` contract).
 */

import type { SkillTaxonomy } from "./ports/engine/skill_taxonomy";
import type { QuestionRepo } from "./ports/engine/question_repo";
import type { AttemptRepo } from "./ports/engine/attempt_repo";
import type { SessionRepo } from "./ports/engine/session_repo";
import type { Scheduler } from "./ports/engine/scheduler";
import type { Grader } from "./ports/engine/grader";
import type { ContentRepo } from "./ports/engine/content_repo";
import type { LearnerReadRepo } from "./ports/engine/learner_read_repo";

import type { EngineDb } from "./adapters/engine/db/engine_db";
import { InMemoryEngineDb } from "./adapters/engine/db/in_memory_engine_db";
import { pgEngineDb } from "./adapters/engine/db/drizzle_engine_db";
import { DrizzleSkillTaxonomy } from "./adapters/engine/repos/drizzle_skill_taxonomy";
import { DrizzleQuestionRepo } from "./adapters/engine/repos/drizzle_question_repo";
import { DrizzleAttemptRepo } from "./adapters/engine/repos/drizzle_attempt_repo";
import { DrizzleSessionRepo } from "./adapters/engine/repos/drizzle_session_repo";
import { DrizzleContentRepo } from "./adapters/engine/repos/drizzle_content_repo";
import { FsrsScheduler } from "./adapters/engine/scheduler/fsrs_scheduler";
import { ExactLetterGrader } from "./adapters/engine/grader/exact_letter_grader";
import { DrizzleLearnerReadRepo } from "./adapters/engine/repos/drizzle_learner_read_repo";

export interface BuildEngineAdaptersOptions {
  readonly env: Readonly<Record<string, string | undefined>>;
  /** Test seam: inject an EngineDb (e.g. a seeded InMemoryEngineDb) directly. */
  readonly engineDb?: EngineDb;
}

export interface EnginePortBag {
  readonly skillTaxonomy: SkillTaxonomy;
  readonly questionRepo: QuestionRepo;
  readonly attemptRepo: AttemptRepo;
  readonly sessionRepo: SessionRepo;
  readonly scheduler: Scheduler;
  readonly grader: Grader;
  readonly contentRepo: ContentRepo;
  /** Read-only skill_state view for Dashboard mastery + Summary delta (ADR-0011). */
  readonly learnerRead: LearnerReadRepo;
}

/**
 * Select the EngineDb seam. Pure given its env argument (the pg seam constructs
 * lazily — no connection until a query runs), so the choice is unit-testable
 * without `server-only`. Mirrors `selectThreadRepo`.
 */
export function selectEngineDb(
  env: Readonly<Record<string, string | undefined>>,
): EngineDb {
  const url = env.DATABASE_URL;
  if (url && url.trim()) {
    return pgEngineDb(url);
  }
  return new InMemoryEngineDb();
}

export function buildEngineAdapters(
  options: BuildEngineAdaptersOptions,
): EnginePortBag {
  const db = options.engineDb ?? selectEngineDb(options.env);

  const questionRepo = new DrizzleQuestionRepo(db);

  return {
    skillTaxonomy: new DrizzleSkillTaxonomy(db),
    questionRepo,
    attemptRepo: new DrizzleAttemptRepo({ db }),
    sessionRepo: new DrizzleSessionRepo({ db }),
    // The Scheduler needs QuestionRepo to resolve a chosen skill → a reviewed
    // question (FR-A1); it is the sole writer of skill_state (FR-A2).
    scheduler: new FsrsScheduler({ db, questions: questionRepo }),
    grader: new ExactLetterGrader(),
    contentRepo: new DrizzleContentRepo(db),
    // Read-only skill_state view (ADR-0011): depends on the ReadableEngineDb
    // projection, so it cannot reach upsertSkillState (FR-A2, Scheduler-only).
    learnerRead: new DrizzleLearnerReadRepo(db),
  };
}
