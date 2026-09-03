/**
 * Exam-method LEARNER_ARG map for the BFF dispatcher (FR-38 / R4 / W1-3).
 *
 * Plan §1: every exam method is learnerId-first ⇒ LEARNER_ARG = 0.
 * Default deny: `resolveExamLearnerArg` returns `"deny"` when an exam
 * method is missing from the map (do not trust a client-supplied learnerId).
 *
 * `insertExamRun` also carries `run.learner_id`. LEARNER_FIELD_ARG is not
 * applied — the plan specifies positional LEARNER_ARG = 0 only (the
 * existing FIELD convention is for object-only args like `insertSession`).
 * Store impls (W1-4/W1-5) must persist the positional `learnerId`.
 */

import type { EngineDbMethodName } from "./engine_db_disposition";

export const EXAM_ENGINE_DB_METHODS = [
  "insertExamRun",
  "listExamRunsByLearner",
  "getExamRun",
  "beginExamSection",
  "upsertExamRunItems",
  "finishExamSection",
  "setExamRunComposite",
  "setExamBookmark",
  "listExamRunItemsByLearner",
  "getExamFormForClient",
] as const satisfies readonly EngineDbMethodName[];

export type ExamEngineDbMethod = (typeof EXAM_ENGINE_DB_METHODS)[number];

/** Plan §1: learnerId first ⇒ dispatcher LEARNER_ARG = 0. */
export const EXAM_LEARNER_ARG = {
  insertExamRun: 0,
  listExamRunsByLearner: 0,
  getExamRun: 0,
  beginExamSection: 0,
  upsertExamRunItems: 0,
  finishExamSection: 0,
  setExamRunComposite: 0,
  setExamBookmark: 0,
  listExamRunItemsByLearner: 0,
  getExamFormForClient: 0,
} as const satisfies Record<ExamEngineDbMethod, 0>;

export function isExamEngineDbMethod(
  method: string,
): method is ExamEngineDbMethod {
  return (EXAM_ENGINE_DB_METHODS as readonly string[]).includes(method);
}

/**
 * Resolve the learner-arg index for a method.
 *
 * - exam + mapped → index
 * - exam + missing → `"deny"` (FR-38 default; do not trust client learnerId)
 * - non-exam → `undefined` (caller uses the inherited LEARNER_ARG / FIELD maps)
 */
export function resolveExamLearnerArg(
  method: EngineDbMethodName,
  map: Partial<Record<string, number>> = EXAM_LEARNER_ARG,
): number | "deny" | undefined {
  if (!isExamEngineDbMethod(method)) return undefined;
  const idx = map[method];
  return typeof idx === "number" ? idx : "deny";
}
