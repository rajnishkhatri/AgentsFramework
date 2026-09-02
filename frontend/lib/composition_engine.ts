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
 * Substrate (coach-v3 FR-A3): `DATABASE_URL` → live Postgres (`pgEngineDb`);
 * unset URL → typed `EngineRepoError` (no silent in-memory fallback). Tests
 * inject `engineDb: new InMemoryEngineDb()` explicitly. The on-device SQLite
 * seam is wired here too once the Capacitor SQLite driver lands (same
 * `EngineDb` contract).
 */

import type { SkillTaxonomy } from "./ports/engine/skill_taxonomy";
import type { QuestionRepo } from "./ports/engine/question_repo";
import type { AttemptRepo } from "./ports/engine/attempt_repo";
import type { SessionRepo } from "./ports/engine/session_repo";
import type { Scheduler } from "./ports/engine/scheduler";
import type { Grader } from "./ports/engine/grader";
import type { ContentRepo } from "./ports/engine/content_repo";
import type { LearnerReadRepo } from "./ports/engine/learner_read_repo";
import type { HintRepo } from "./ports/engine/hint_repo";
import type { TestItemRepo } from "./ports/engine/test_item_repo";
import type { TestBlueprintRepo } from "./ports/engine/test_blueprint_repo";
import type { TutorialRepo } from "./ports/engine/tutorial_repo";
import type { ProgressRepo } from "./ports/engine/progress_repo";
import type { ExamRunRepo } from "./ports/engine/exam_run_repo";
import type { QuizSubmitNotifier } from "./ports/quiz_submit_notifier";

import type { EngineDb } from "./adapters/engine/db/engine_db";
import { pgEngineDb } from "./adapters/engine/db/drizzle_engine_db";
import { EngineRepoError } from "./ports/engine/errors";
import { DrizzleSkillTaxonomy } from "./adapters/engine/repos/drizzle_skill_taxonomy";
import { DrizzleQuestionRepo } from "./adapters/engine/repos/drizzle_question_repo";
import { DrizzleAttemptRepo } from "./adapters/engine/repos/drizzle_attempt_repo";
import { DrizzleSessionRepo } from "./adapters/engine/repos/drizzle_session_repo";
import { DrizzleContentRepo } from "./adapters/engine/repos/drizzle_content_repo";
import { FsrsScheduler } from "./adapters/engine/scheduler/fsrs_scheduler";
import { ExactLetterGrader } from "./adapters/engine/grader/exact_letter_grader";
import { DrizzleLearnerReadRepo } from "./adapters/engine/repos/drizzle_learner_read_repo";
import { DrizzleHintRepo } from "./adapters/engine/repos/drizzle_hint_repo";
import { DrizzleTestItemRepo } from "./adapters/engine/repos/drizzle_test_item_repo";
import { DrizzleTestBlueprintRepo } from "./adapters/engine/repos/drizzle_test_blueprint_repo";
import { DrizzleTutorialRepo } from "./adapters/engine/repos/drizzle_tutorial_repo";
import { DrizzleProgressRepo } from "./adapters/engine/repos/drizzle_progress_repo";
import { TestItemQuestionRepo } from "./adapters/engine/repos/test_item_question_repo";
import { DEFAULT_SUBJECT } from "./wire/engine_entities";

export interface BuildEngineAdaptersOptions {
  readonly env: Readonly<Record<string, string | undefined>>;
  /** Test seam: inject an EngineDb (e.g. a seeded InMemoryEngineDb) directly. */
  readonly engineDb?: EngineDb;
  /**
   * Which store feeds the practice quiz (ADR-0021) — mirrors the browser root
   * (Rule F3 parity). `"bank"` binds the bag's `questionRepo` + the scheduler
   * to the governed `test_item` bank via the read-only `TestItemQuestionRepo`;
   * `"practice"` (default) keeps the `question`-table wiring.
   */
  readonly questionSource?: "practice" | "bank";
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
  /** Read-only reviewed hint ladder (ADR-0014, FR-12/FR-20). */
  readonly hintRepo: HintRepo;
  /** Read-only reviewed exam-item bank (ADR-0015, FR-27.1). */
  readonly testItemRepo: TestItemRepo;
  /** Read-only test-form blueprint (ADR-0015, FR-24.3). */
  readonly testBlueprintRepo: TestBlueprintRepo;
  /** Read-only reviewed tutorial / lesson content (ADR-0028, E1a FR-1/17). */
  readonly tutorialRepo: TutorialRepo;
  /** Read-only progress-trend points (ADR-0028, E1a FR-17). */
  readonly progressRepo: ProgressRepo;
  /**
   * Official-rules exam runs (ADR-0040). Phase-0 stub: undefined until WT-1
   * fills the Drizzle adapter (W1-7). Optional so the bag stays releasable
   * and WT-2 can compile against the port type.
   */
  readonly examRunRepo?: ExamRunRepo;
  /**
   * Fire-and-forget quiz-submit signal to the coach-session marker store
   * (ADR-0012 Amendment, FR-19). Optional: absent on the server root (the
   * marker write is a browser→BFF fetch) and in legacy test bags; a missing
   * notifier fails CLOSED (the coach derives pre_submit and over-strips).
   */
  readonly quizSubmitNotifier?: QuizSubmitNotifier;
}

/**
 * Select the EngineDb seam for durable BFF / server use (coach-v3 FR-A3).
 * Pure given its env argument (the pg seam constructs lazily — no connection
 * until a query runs). **Diverges from** `selectCoachMarkerRepo` /
 * `selectThreadRepo` on the else-branch: unset `DATABASE_URL` throws a typed
 * `EngineRepoError` — never a silent `InMemoryEngineDb` fallback.
 */
export function selectEngineDb(
  env: Readonly<Record<string, string | undefined>>,
): EngineDb {
  const url = env.DATABASE_URL;
  if (url && url.trim()) {
    return pgEngineDb(url);
  }
  throw new EngineRepoError(
    "engine DATABASE_URL is required (no InMemoryEngineDb fallback)",
  );
}

export function buildEngineAdapters(
  options: BuildEngineAdaptersOptions,
): EnginePortBag {
  const db = options.engineDb ?? selectEngineDb(options.env);

  const testItemRepo = new DrizzleTestItemRepo(db);
  // ADR-0021 parity with the browser root: the bank path reuses the identical
  // FsrsScheduler bound to the read-only bank adapter; the practice repo and
  // question table stay untouched (leak unrepresentable, ADR-0015 clause 1).
  const questionRepo =
    options.questionSource === "bank"
      ? new TestItemQuestionRepo(testItemRepo, DEFAULT_SUBJECT)
      : new DrizzleQuestionRepo(db);

  // One ContentRepo instance, shared: it is both the objective-plane port AND
  // the source SessionRepo reads the per-mode target_count default from (FR-5).
  const contentRepo = new DrizzleContentRepo(db);

  return {
    skillTaxonomy: new DrizzleSkillTaxonomy(db),
    questionRepo,
    attemptRepo: new DrizzleAttemptRepo({ db }),
    sessionRepo: new DrizzleSessionRepo({ db, contentRepo }),
    // The Scheduler needs QuestionRepo to resolve a chosen skill → a reviewed
    // question (FR-A1); it is the sole writer of skill_state (FR-A2).
    scheduler: new FsrsScheduler({ db, questions: questionRepo }),
    grader: new ExactLetterGrader(),
    contentRepo,
    // Read-only skill_state view (ADR-0011): depends on the ReadableEngineDb
    // projection, so it cannot reach upsertSkillState (FR-A2, Scheduler-only).
    learnerRead: new DrizzleLearnerReadRepo(db),
    // Read-only reviewed hint ladder (ADR-0014): no write surface on the port.
    hintRepo: new DrizzleHintRepo(db),
    // Read-only governed test plane (ADR-0015): reviewed items + blueprint,
    // no write surface — serving code can never flip the gate.
    testItemRepo,
    testBlueprintRepo: new DrizzleTestBlueprintRepo(db),
    // Read-only lesson content + progress (ADR-0028): no write surface.
    tutorialRepo: new DrizzleTutorialRepo(db),
    progressRepo: new DrizzleProgressRepo(db),
  };
}
