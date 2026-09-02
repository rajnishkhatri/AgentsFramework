/**
 * ExamRunRepo port (ADR-0040) — durable official-rules runs on the ADR-0038 seam.
 *
 * Phase-0 stub: the interface is declared so WT-2 can compile against the
 * port type. The Drizzle adapter + EngineDb methods land in WT-1 (W1-7).
 * `EnginePortBag.examRunRepo` stays undefined until that adapter is wired.
 */

import type {
  ExamRun,
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "../../wire/exam_entities";

/**
 * ExamRunRepo — learner-scoped official-rules run persistence (ADR-0040).
 *
 * Behavioral contract:
 *   1. LEARNER-SCOPED. Every method takes a named `{ learnerId }` argument
 *      (connascence of name, FR-38 / R4). The dispatcher overrides that
 *      argument from the server claim; default deny if unmapped.
 *   2. BEGIN KEEP-FIRST (FR-37). `beginSection` on an already in-progress
 *      `(runId, sectionCode)` returns the stored `started_at` and does not
 *      reset the deadline.
 *   3. FINISH-ONCE (FR-2). Finishing an already-finished attempt is a no-op
 *      that returns the stored result; it cannot reopen.
 *   4. ITEM UPSERTS are idempotent and apply `mergeExamDwell` (FR-4 / FR-39).
 *   5. Returns `wire/exam_entities` shapes only — no SDK type escapes (F-R8).
 *
 * @throws EngineRepoError on persistence failure.
 */
export interface ExamRunRepo {
  startRun(args: { learnerId: string; formId: string }): Promise<ExamRun>;
  beginSection(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
  }): Promise<ExamSectionAttempt>;
  upsertItem(args: { learnerId: string; item: ExamRunItem }): Promise<void>;
  upsertItems(args: {
    learnerId: string;
    items: readonly ExamRunItem[];
  }): Promise<void>;
  finishSection(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
  }): Promise<ExamSectionAttempt>;
  getRun(args: { learnerId: string; runId: string }): Promise<ExamRun | null>;
  listRunsByLearner(args: { learnerId: string }): Promise<ExamRun[]>;
  listItems(args: {
    learnerId: string;
    runId: string;
  }): Promise<ExamRunItem[]>;
  setBookmark(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
    questionId: string;
    bookmarked: boolean;
  }): Promise<void>;
}
