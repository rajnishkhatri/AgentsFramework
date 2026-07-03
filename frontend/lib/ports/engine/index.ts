/**
 * Barrel re-export for the nine Subject-Coach engine ports (7 ADR-0006 +
 * LearnerReadRepo, ADR-0011 + HintRepo, ADR-0014).
 *
 * Grouped under `ports/engine/` (not flat in `ports/`) so the engine bounded
 * context stays distinct from the eight V3 chat ports, and the chat
 * conformance gate (`test_port_conformance.test.ts`, which asserts the FLAT
 * `ports/` dir contains exactly the 8 chat ports) is unaffected. The engine
 * ports have their own sibling gate, `test_engine_port_conformance.test.ts`.
 *
 * Composition root and engine policy import from `@/lib/ports/engine`.
 */

export type { SkillTaxonomy } from "./skill_taxonomy";
export type { QuestionRepo } from "./question_repo";
export type { AttemptRepo } from "./attempt_repo";
export type { SessionRepo, SessionScore } from "./session_repo";
export type { Scheduler } from "./scheduler";
export type { Grader } from "./grader";
export type { ContentRepo } from "./content_repo";
export type { LearnerReadRepo } from "./learner_read_repo";
export type { HintRepo } from "./hint_repo";

export {
  EngineError,
  EngineRepoError,
  SchedulerError,
  EngineNotFoundError,
} from "./errors";
