/**
 * ExamRunRepo port (ADR-0040) — durable official-rules runs on the ADR-0038 seam.
 *
 * W1-7 fills the Drizzle adapter and wires `EnginePortBag.examRunRepo`.
 * Read shapes used by the SERIAL UI (S-D1/S-D3) are declared here so the
 * port never imports EngineDb types from the adapter ring (P6).
 */

import type {
  ExamRun,
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "../../wire/exam_entities";

/** One run plus its section-attempt rows (home status + FR-12). */
export type ExamRunEntry = {
  run: ExamRun;
  attempts: ExamSectionAttempt[];
};

/** One owned run plus attempts and items; `null` if not owned. */
export type ExamRunDetail = {
  run: ExamRun;
  attempts: ExamSectionAttempt[];
  items: ExamRunItem[];
};

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
  getRunDetail(args: {
    learnerId: string;
    runId: string;
  }): Promise<ExamRunDetail | null>;
  listRunsByLearner(args: { learnerId: string }): Promise<ExamRun[]>;
  listRunEntries(args: {
    learnerId: string;
    formId?: string;
  }): Promise<ExamRunEntry[]>;
  listItems(args: {
    learnerId: string;
    runId: string;
  }): Promise<ExamRunItem[]>;
  listItemsByLearner(args: { learnerId: string }): Promise<ExamRunItem[]>;
  setBookmark(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
    questionId: string;
    bookmarked: boolean;
  }): Promise<void>;
}
