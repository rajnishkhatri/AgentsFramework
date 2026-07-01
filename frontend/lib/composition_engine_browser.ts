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
 * Substrate (ADR-0005 local-first / ADR-0010): the browser runs the on-device
 * path. Today that is `InMemoryEngineDb` (dev / the before-DB state); the live
 * on-device SQLite `EngineDb` is wired here — same contract — once the
 * Capacitor SQLite driver lands. The pg store stays on the SERVER root, reached
 * via RSC + Server Actions (plan §"Where the engine runs"), never from here.
 */

import type { EnginePortBag } from "./composition_engine";

import type { EngineDb } from "./adapters/engine/db/engine_db";
import { InMemoryEngineDb } from "./adapters/engine/db/in_memory_engine_db";
import { DrizzleSkillTaxonomy } from "./adapters/engine/repos/drizzle_skill_taxonomy";
import { DrizzleQuestionRepo } from "./adapters/engine/repos/drizzle_question_repo";
import { DrizzleAttemptRepo } from "./adapters/engine/repos/drizzle_attempt_repo";
import { DrizzleSessionRepo } from "./adapters/engine/repos/drizzle_session_repo";
import { DrizzleContentRepo } from "./adapters/engine/repos/drizzle_content_repo";
import { FsrsScheduler } from "./adapters/engine/scheduler/fsrs_scheduler";
import { ExactLetterGrader } from "./adapters/engine/grader/exact_letter_grader";
import { DrizzleLearnerReadRepo } from "./adapters/engine/repos/drizzle_learner_read_repo";
import { seedDevCorpus } from "./adapters/engine/_dev_seed";

export interface BuildBrowserEngineAdaptersOptions {
  /**
   * Test / dev seam: inject an EngineDb (e.g. a seeded InMemoryEngineDb) so the
   * loop tests can stand up a deterministic corpus. Defaults to a fresh
   * `InMemoryEngineDb` — the browser-safe substrate (never `pgEngineDb`).
   */
  readonly engineDb?: EngineDb;
}

/**
 * Assemble the engine `EnginePortBag` from the browser-safe substrate. Pure
 * given its (optional) db argument. Mirrors `buildEngineAdapters` in the server
 * root, minus the `DATABASE_URL`/`pgEngineDb` branch that must not ship to the
 * client.
 */
export function buildBrowserEngineAdapters(
  options: BuildBrowserEngineAdaptersOptions = {},
): EnginePortBag {
  const db = options.engineDb ?? new InMemoryEngineDb();

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
    // Read-only skill_state view (ADR-0011); ReadableEngineDb → no write reachable.
    learnerRead: new DrizzleLearnerReadRepo(db),
  };
}

let singleton: EnginePortBag | null = null;

/**
 * Lazy app-wide engine bag for client components (the analogue of
 * `browserRuntimeClient()`). The `useEngine()` provider (Phase 0.4) reads this.
 * A stable singleton is required so the provider does not re-mount adapters —
 * and so the in-memory substrate keeps its state across a session.
 *
 * DEV SEED (why the guard). A fresh `InMemoryEngineDb` is empty, which makes the
 * live `/learn` surface unusable in a dev preview (0% dashboard; the Quiz route
 * throws `no reviewed question` from `openQuizItem`). Outside production we load
 * the small hand-authored "Maya" corpus (`_dev_seed.ts`) so the Dashboard → Quiz
 * → Summary loop is exercisable in the browser. The guard keeps it off the
 * production path, where the on-device SQLite substrate (ADR-0005/0010) is
 * expected to supply real data. Tests never reach this branch: they inject their
 * own seeded bag via `buildBrowserEngineAdapters({ engineDb })` / the
 * `EngineProvider bag` prop and never call this singleton.
 */
export function browserEngineAdapters(): EnginePortBag {
  if (singleton === null) {
    if (process.env.NODE_ENV !== "production") {
      const db = new InMemoryEngineDb();
      seedDevCorpus(db);
      singleton = buildBrowserEngineAdapters({ engineDb: db });
    } else {
      // Production: an EMPTY substrate. The on-device SQLite EngineDb
      // (ADR-0005/0010) supplies real data here; the dev corpus must not ship.
      singleton = buildBrowserEngineAdapters();
    }
  }
  return singleton;
}
