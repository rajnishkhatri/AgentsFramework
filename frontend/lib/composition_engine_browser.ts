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
import type {
  Hint,
  Question,
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
import { FetchQuizSubmitNotifier } from "./adapters/coach_marker/marker_write_client";
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
    // Read-only reviewed hint ladder (ADR-0014): no write surface on the port.
    hintRepo: new DrizzleHintRepo(db),
    // Read-only governed test plane (ADR-0015): reviewed items + blueprint.
    testItemRepo: new DrizzleTestItemRepo(db),
    testBlueprintRepo: new DrizzleTestBlueprintRepo(db),
    // ADR-0012 Amendment (FR-19): browser→BFF fire-and-forget marker write on
    // quiz submit, flipping the coach's derived mode to post_feedback.
    quizSubmitNotifier: new FetchQuizSubmitNotifier(),
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
      // E2E override (non-prod only): a Playwright spec may inject a larger
      // deterministic corpus on `window` via `page.addInitScript` before the
      // provider mounts. When present it REPLACES the hand-authored dev corpus,
      // so specs drive their own byte-stable fixtures without touching prod seed
      // content. Absent → the normal "Maya" dev corpus (the preview default).
      const injected = readE2ESeedOverride();
      if (injected) {
        db.seedSkills([...injected.skills]);
        db.seedQuestions([...injected.questions]);
        db.seedSkillStates([...injected.skillStates]);
        // Optional reviewed hint ladders (ADR-0014) — the iPad panel's
        // two-tier nudge (FR-J3a) needs rungs 2/3 on the served items.
        if (injected.hints) db.seedHints([...injected.hints]);
      } else {
        seedDevCorpus(db);
      }
      singleton = buildBrowserEngineAdapters({ engineDb: db });
    } else {
      // Production: an EMPTY substrate. The on-device SQLite EngineDb
      // (ADR-0005/0010) supplies real data here; the dev corpus must not ship,
      // and the e2e override is never read (guarded by NODE_ENV above).
      singleton = buildBrowserEngineAdapters();
    }
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
  };
}
