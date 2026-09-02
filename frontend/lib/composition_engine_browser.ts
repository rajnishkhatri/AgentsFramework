/**
 * Subject-Coach engine browser accessor (FR-C2, the C2 seam).
 *
 * The browser-side sibling of `composition_engine.ts` (server engine root),
 * exactly as `composition_browser.ts` is the client sibling of `composition.ts`
 * (chat). Both are composition roots — the layering gate
 * (`tests/architecture/test_frontend_layering.test.ts`) lists this file in the
 * composition ring, so it MAY name concrete adapters (Rule C1/C2). No other
 * client-side file names an engine adapter; consumers (the `useEngine()`
 * provider, screen hooks, translators) receive the `EnginePortBag` only.
 *
 * Why a SEPARATE root from `composition_engine.ts`, not a re-export:
 * `composition_engine.ts` imports `pgEngineDb` from `drizzle_engine_db` at
 * module top (its server substrate), which transitively pulls the `pg` driver
 * (`@sdk pg`) + `drizzle-orm`. Those are server-only and must never enter the
 * client bundle (the same reason `composition_browser.ts` avoids the WorkOS
 * adapter). So this file imports ONLY the browser-safe substrate —
 * `InMemoryEngineDb` — plus the driver-free repo / Scheduler / Grader adapters
 * (they are written against the narrow `EngineDb` interface and import no
 * driver, verified by the layering gate). The bag is assembled here rather than
 * delegated so the `pgEngineDb` import never reaches the client.
 *
 * Substrate: default `InMemoryEngineDb` (dev / flag-off). With
 * `NEXT_PUBLIC_FF_DURABLE_ENGINE=1` the atomic swap (coach-v3 FR-A4 / T A.7)
 * binds `HttpEngineDb` → BFF `/api/engine/*` → server `pgEngineDb`. Client
 * content seeding (`seedTestItemBank`) is skipped under the durable flag —
 * content is server-seeded (Track G).
 */

import type { EnginePortBag } from "./composition_engine";

import type { EngineDb } from "./adapters/engine/db/engine_db";
import { InMemoryEngineDb } from "./adapters/engine/db/in_memory_engine_db";
import { HttpEngineDb } from "./adapters/engine/db/http_engine_db";
import { EnvVarFlagsAdapter } from "./adapters/feature_flags/env_var_flags_adapter";
import type {
  Hint,
  Question,
  QuizSession,
  Skill,
  SkillState,
} from "./wire/engine_entities";
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
import { DrizzleExamRunRepo } from "./adapters/engine/repos/drizzle_exam_run_repo";
import { TestItemQuestionRepo } from "./adapters/engine/repos/test_item_question_repo";
import { FetchQuizSubmitNotifier } from "./adapters/coach_marker/marker_write_client";
import {
  seedDevCorpus,
  seedDevTaxonomy,
} from "./adapters/engine/_dev_seed";
import { seedHintBank } from "./adapters/engine/_hint_bank";
import { seedTestItemBank } from "./adapters/engine/_test_item_bank";
import { seedLessonContent } from "./adapters/engine/_lesson_seed";
import { DEFAULT_SUBJECT } from "./wire/engine_entities";
import type { SeedMode } from "./learn/resolve_learn_identity";
import { planEngineSeed } from "./engine_seed_plan";

export interface BuildBrowserEngineAdaptersOptions {
  /**
   * Test / dev seam: inject an EngineDb (e.g. a seeded InMemoryEngineDb) so the
   * loop tests can stand up a deterministic corpus. Defaults to a fresh
   * `InMemoryEngineDb` — the browser-safe substrate (never `pgEngineDb`).
   */
  readonly engineDb?: EngineDb;
  /**
   * Which store feeds the practice quiz (ADR-0021). `"bank"` binds BOTH the
   * bag's `questionRepo` AND the FsrsScheduler to the governed `test_item`
   * bank via the read-only `TestItemQuestionRepo` (openQuizItem resolves the
   * scheduled id through `ports.questionRepo.get`, so the two must agree).
   * `"practice"` (default) keeps the `question`-table wiring — existing tests
   * and the e2e seed-override path (specs inject `questions` fixtures) are
   * unchanged. The two sources never mix: an exam-item leak into the practice
   * repo stays structurally unrepresentable (ADR-0015 clause 1).
   */
  readonly questionSource?: "practice" | "bank";
}

/**
 * Assemble the engine `EnginePortBag` from the browser-safe substrate. Pure
 * given its (optional) db argument. Mirrors `buildEngineAdapters` in the server
 * root, minus the `DATABASE_URL`/`pgEngineDb` branch that must not ship to the
 * client.
 */
function durableEngineEnabled(
  env?: Readonly<Record<string, string | undefined>>,
): boolean {
  // Static member access is required for Next.js to inline NEXT_PUBLIC_* into
  // the browser bundle; dynamic process.env[key] sees no value client-side.
  const browserSafeEnv = env ?? {
    NEXT_PUBLIC_FF_DURABLE_ENGINE:
      process.env.NEXT_PUBLIC_FF_DURABLE_ENGINE,
  };
  return new EnvVarFlagsAdapter({ env: browserSafeEnv }).isEnabled(
    "durable_engine",
  );
}

export function buildBrowserEngineAdapters(
  options: BuildBrowserEngineAdaptersOptions = {},
): EnginePortBag {
  // T A.7 atomic swap: one shared `db` builds every useEngine() screen's bag.
  const db =
    options.engineDb ??
    (durableEngineEnabled()
      ? new HttpEngineDb({ baseUrl: "" })
      : new InMemoryEngineDb());

  const testItemRepo = new DrizzleTestItemRepo(db);
  // ADR-0021: the bank path serves practice items from the governed test_item
  // bank through the read-only adapter; the SAME FsrsScheduler code (the sole
  // skill_state writer) is reused — only its bound QuestionRepo changes. The
  // practice DrizzleQuestionRepo and the question table are untouched.
  const questionRepo =
    options.questionSource === "bank"
      ? new TestItemQuestionRepo(testItemRepo, DEFAULT_SUBJECT)
      : new DrizzleQuestionRepo(db);

  // One shared ContentRepo: the objective-plane port AND SessionRepo's source
  // for the per-mode target_count default (FR-5).
  const contentRepo = new DrizzleContentRepo(db);

  const sessionRepo = maybeFailOnceSessionRepo(
    new DrizzleSessionRepo({ db, contentRepo }),
  );
  const grader = new ExactLetterGrader();

  return {
    skillTaxonomy: new DrizzleSkillTaxonomy(db),
    questionRepo,
    attemptRepo: new DrizzleAttemptRepo({ db }),
    sessionRepo,
    // The Scheduler needs QuestionRepo to resolve a chosen skill → a reviewed
    // question (FR-A1); it is the sole writer of skill_state (FR-A2).
    scheduler: new FsrsScheduler({ db, questions: questionRepo }),
    grader,
    contentRepo,
    // Read-only skill_state view (ADR-0011); ReadableEngineDb → no write reachable.
    learnerRead: new DrizzleLearnerReadRepo(db),
    // Read-only reviewed hint ladder (ADR-0014): no write surface on the port.
    hintRepo: new DrizzleHintRepo(db),
    // Read-only governed test plane (ADR-0015): reviewed items + blueprint.
    testItemRepo,
    testBlueprintRepo: new DrizzleTestBlueprintRepo(db),
    // Read-only lesson content + progress (ADR-0028): no write surface.
    tutorialRepo: new DrizzleTutorialRepo(db),
    progressRepo: new DrizzleProgressRepo(db),
    examRunRepo: new DrizzleExamRunRepo({ db, grader }),
    // ADR-0012 Amendment (FR-19): browser→BFF fire-and-forget marker write on
    // quiz submit, flipping the coach's derived mode to post_feedback.
    quizSubmitNotifier: new FetchQuizSubmitNotifier(),
  };
}

/**
 * C1-fix FR-2: when `NEXT_PUBLIC_PREACT_E2E_HOOKS=1`, wrap
 * `sessionRepo.listByLearner` so the first call rejects when the page was
 * opened with `?e2e_rail_fail=1` (rail unavailable → Retry path). Subsequent
 * calls delegate. Module-scoped flag resets on full page reload (new bag).
 * Composition-root only — zero domain-code branch. The query-param opt-in
 * keeps other `/learn` e2e rows from consuming the fail-once on every load.
 */
let hasFailedOnce = false;

function maybeFailOnceSessionRepo(
  sessionRepo: EnginePortBag["sessionRepo"],
): EnginePortBag["sessionRepo"] {
  if (process.env.NEXT_PUBLIC_PREACT_E2E_HOOKS !== "1") return sessionRepo;
  // Class-instance methods live on the prototype — object spread would drop
  // open/close/get and break Quiz ("sessionRepo.open is not a function").
  // Bind every port method explicitly; only listByLearner is intercepted.
  const listByLearner = sessionRepo.listByLearner.bind(sessionRepo);
  return {
    open: sessionRepo.open.bind(sessionRepo),
    close: sessionRepo.close.bind(sessionRepo),
    get: sessionRepo.get.bind(sessionRepo),
    listByLearner: async (subject, learnerId, options) => {
      if (
        !hasFailedOnce &&
        typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).get("e2e_rail_fail") === "1"
      ) {
        hasFailedOnce = true;
        throw new Error("e2e forced rail failure");
      }
      return listByLearner(subject, learnerId, options);
    },
  };
}

let singleton: EnginePortBag | null = null;

/**
 * Seed mode for the next `browserEngineAdapters()` singleton build.
 * Set synchronously by `EngineProvider` from `useLearnIdentity().seedMode`
 * before the first bag construction (FR-2 / FR-7).
 * - `demo` → full Garvit corpus (bypass / learn-e2e)
 * - `fresh` → taxonomy + bank only (authenticated WorkOS)
 * Default `demo` preserves prior non-prod behavior when unset (tests inject bag).
 */
let seedModeLatch: SeedMode = "demo";

/** Latch seed mode before the first `browserEngineAdapters()` call. */
export function setBrowserEngineSeedMode(mode: SeedMode): void {
  seedModeLatch = mode;
}

/** Test-only: drop the singleton so the next call reseeds under a new mode. */
export function resetBrowserEngineSingleton(): void {
  singleton = null;
  seedModeLatch = "demo";
}

/**
 * Lazy app-wide engine bag for client components (the analogue of
 * `browserRuntimeClient()`). The `useEngine()` provider (Phase 0.4) reads this.
 * A stable singleton is required so the provider does not re-mount adapters —
 * and so the in-memory substrate keeps its state across a session.
 *
 * DEV SEED (why the guard). A fresh `InMemoryEngineDb` is empty, which makes the
 * live `/learn` surface unusable in a dev preview. Outside production we load
 * taxonomy (+ optional Garvit mastery when `seedMode=demo`) plus the
 * cascade-promoted item bank (`_test_item_bank.ts`, ADR-0021). Authenticated
 * WorkOS sessions use `seedMode=fresh` (taxonomy+bank, no demo mastery).
 * Tests inject their own bag via `buildBrowserEngineAdapters({ engineDb })` /
 * the `EngineProvider bag` prop and never call this singleton.
 */
export function browserEngineAdapters(): EnginePortBag {
  if (singleton === null) {
    const isProd = process.env.NODE_ENV === "production";

    // Coach-v3 durable path (T A.7): HttpEngineDb → BFF; content is server-seeded
    // (Track G). E2E seed overrides still force InMemory for deterministic specs.
    if (durableEngineEnabled()) {
      const injected = isProd ? null : readE2ESeedOverride();
      if (!injected) {
        singleton = buildBrowserEngineAdapters({
          engineDb: new HttpEngineDb({ baseUrl: "" }),
          questionSource: "bank",
        });
        return singleton;
      }
    }

    // E2E override (non-prod only — FR-5): a Playwright spec may inject a larger
    // deterministic corpus on `window` via `page.addInitScript` before the
    // provider mounts. When present it REPLACES the dev seed entirely — specs
    // drive their own byte-stable QUESTION fixtures, so the override keeps the
    // practice-table wiring (their oracles predate the bank; migrating them is
    // a separate task). Never read in a prod build (guarded by `!isProd`).
    const injected = isProd ? null : readE2ESeedOverride();
    if (injected) {
      const db = new InMemoryEngineDb();
      db.seedSkills([...injected.skills]);
      db.seedQuestions([...injected.questions]);
      db.seedSkillStates([...injected.skillStates]);
      // Optional reviewed hint ladders (ADR-0014) — the iPad panel's
      // two-tier nudge (FR-J3a) needs rungs 2/3 on the served items.
      if (injected.hints) db.seedHints([...injected.hints]);
      if (injected.sessions) {
        for (const s of injected.sessions) {
          void db.insertSession({ ...s });
        }
      }
      // Lesson content is independent of the quiz corpus (E1a / ADR-0028).
      seedLessonContent(db);
      singleton = buildBrowserEngineAdapters({ engineDb: db });
      return singleton;
    }

    // D7 (FR-1..4): the pure helper decides the seed pack from (isProd,
    // seedMode). In prod ONLY `fresh` seeds (the reviewed web corpus); every
    // non-fresh prod mode (demo/unset/undecidable) → `"none"` → an EMPTY bag,
    // never the Garvit `seedDevCorpus` or a partial pack (AP-6 undecidable→empty).
    // The on-device SQLite EngineDb (ADR-0005/0010) is the intended prod-data
    // path; until it lands, `fresh` ships the in-bundle reviewed corpus.
    const plan = planEngineSeed({ isProd, seedMode: seedModeLatch });
    if (plan === "none") {
      singleton = buildBrowserEngineAdapters();
      return singleton;
    }

    const db = new InMemoryEngineDb();
    // fresh-pack → taxonomy only (empty progress slate, FR-4); demo-corpus →
    // full Garvit mastery. Both share the bank/hints/lessons tail below.
    if (plan === "fresh-pack") {
      seedDevTaxonomy(db);
    } else {
      seedDevCorpus(db);
    }
    seedTestItemBank(db);
    // Generated hint ladders for the bank items (coach-bank-hints FR-C1):
    // without them every bank item degrades to the generic nudge.
    seedHintBank(db);
    // Hand-authored lesson content for /learn/skill (ADR-0028 / E1a).
    seedLessonContent(db);
    singleton = buildBrowserEngineAdapters({
      engineDb: db,
      questionSource: "bank",
    });
  }
  return singleton;
}

/** The `window` key an e2e spec sets to inject a seed corpus (non-prod only). */
const E2E_SEED_GLOBAL_KEY = "__PREACT_E2E_SEED__";

interface InjectedSeedCorpus {
  readonly skills: readonly Skill[];
  readonly questions: readonly Question[];
  readonly skillStates: readonly SkillState[];
  /** Optional reviewed hint ladders (ADR-0014); absent in older specs. */
  readonly hints?: readonly Hint[];
  /** Optional closed sessions for Dashboard rail e2e (C1 / ADR-0026). */
  readonly sessions?: readonly QuizSession[];
}

/**
 * Read the e2e seed override off `window`, if a spec injected one. Returns null
 * outside the browser or when unset/malformed (the caller then falls back to the
 * dev corpus). Kept intentionally narrow: it validates only that the three arrays
 * are present, so it imports no test module (the `lib` ring must not depend on
 * `e2e/`). The corpus rows are `wire/engine_entities` shapes serialized across
 * `addInitScript`.
 */
function readE2ESeedOverride(): InjectedSeedCorpus | null {
  if (typeof window === "undefined") return null;
  const raw = (window as unknown as Record<string, unknown>)[E2E_SEED_GLOBAL_KEY];
  if (raw == null || typeof raw !== "object") return null;
  const c = raw as Partial<InjectedSeedCorpus>;
  if (
    !Array.isArray(c.skills) ||
    !Array.isArray(c.questions) ||
    !Array.isArray(c.skillStates)
  ) {
    return null;
  }
  return {
    skills: c.skills,
    questions: c.questions,
    skillStates: c.skillStates,
    ...(Array.isArray(c.hints) ? { hints: c.hints } : {}),
    ...(Array.isArray(c.sessions) ? { sessions: c.sessions } : {}),
  };
}
