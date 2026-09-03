/**
 * DrizzleExamRunRepo — the `ExamRunRepo` adapter (ADR-0040 / W1-7).
 *
 * Wraps the nine learner-scoped EngineDb exam methods. Begin computes
 * `deadline_at` from the form's section minutes (FR-14). Finish grades
 * once via the injected Grader (FR-27) and writes composite when every
 * declared composite section is done (FR-8 / FR-28). Rejections →
 * `EngineRepoError` (A5).
 */

import type {
  ExamRunDetail,
  ExamRunEntry,
  ExamRunRepo,
} from "../../../ports/engine/exam_run_repo";
import type { Grader } from "../../../ports/engine/grader";
import { EngineNotFoundError, EngineRepoError } from "../../../ports/engine/errors";
import type {
  ClientExamForm,
  ExamForm,
  ExamRun,
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "../../../wire/exam_entities";
import type { EngineDb } from "../db/engine_db";
import { getExamForm, getExamFormDelivery } from "../exam_forms";
import { newUuid } from "../../../new_uuid";
import {
  examComposite,
  scoreExamSection,
} from "../../../../components/exam/exam_scoring";

export type ExamRunRepoDeps = {
  db: EngineDb;
  grader: Grader;
  getForm?: (id: string) => ExamForm;
  newId?: () => string;
  now?: () => Date;
};

export class DrizzleExamRunRepo implements ExamRunRepo {
  private readonly db: EngineDb;
  private readonly grader: Grader;
  private readonly getForm: (id: string) => ExamForm;
  private readonly newId: () => string;
  private readonly now: () => Date;

  constructor(deps: ExamRunRepoDeps) {
    this.db = deps.db;
    this.grader = deps.grader;
    this.getForm = deps.getForm ?? getExamForm;
    this.newId = deps.newId ?? newUuid;
    this.now = deps.now ?? (() => new Date());
  }

  async startRun(args: { learnerId: string; formId: string }): Promise<ExamRun> {
    const run: ExamRun = {
      id: this.newId(),
      learner_id: args.learnerId,
      form_id: args.formId,
      created_at: this.now().toISOString(),
      composite: null,
    };
    try {
      await this.db.insertExamRun(args.learnerId, run);
    } catch (err) {
      throw translate("startRun", err);
    }
    return run;
  }

  async beginSection(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
  }): Promise<ExamSectionAttempt> {
    const detail = await this.requireDetail(args.learnerId, args.runId);
    const form = await this.resolveForm(args.learnerId, detail.run.form_id);
    const section = form.sections.find((s) => s.code === args.sectionCode);
    if (section == null) {
      throw new EngineRepoError(
        `beginSection: form '${form.id}' has no section '${args.sectionCode}'`,
      );
    }
    const startedAt = this.now().toISOString();
    const deadlineAt = new Date(
      this.now().getTime() + section.minutes * 60_000,
    ).toISOString();
    try {
      return await this.db.beginExamSection(
        args.learnerId,
        args.runId,
        args.sectionCode,
        startedAt,
        deadlineAt,
      );
    } catch (err) {
      throw translate("beginSection", err);
    }
  }

  async upsertItem(args: { learnerId: string; item: ExamRunItem }): Promise<void> {
    return this.upsertItems({ learnerId: args.learnerId, items: [args.item] });
  }

  async upsertItems(args: {
    learnerId: string;
    items: readonly ExamRunItem[];
  }): Promise<void> {
    const grouped = new Map<string, ExamRunItem[]>();
    for (const item of args.items) {
      const key = `${item.run_id}\0${item.section_code}`;
      const bucket = grouped.get(key) ?? [];
      bucket.push(item);
      grouped.set(key, bucket);
    }
    try {
      for (const [key, items] of grouped) {
        const sep = key.indexOf("\0");
        const runId = key.slice(0, sep);
        const section = key.slice(sep + 1) as ExamSectionCode;
        await this.db.upsertExamRunItems(args.learnerId, runId, section, items);
      }
    } catch (err) {
      throw translate("upsertItems", err);
    }
  }

  async finishSection(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
  }): Promise<ExamSectionAttempt> {
    const detail = await this.requireDetail(args.learnerId, args.runId);
    const existing = detail.attempts.find(
      (a) => a.section_code === args.sectionCode,
    );
    if (existing == null) {
      throw new EngineNotFoundError(
        `exam section attempt not found: ${args.runId}/${args.sectionCode}`,
      );
    }
    if (existing.status === "submitted" || existing.status === "expired") {
      return existing;
    }
    const form = await this.resolveForm(args.learnerId, detail.run.form_id);
    const section = form.sections.find((s) => s.code === args.sectionCode);
    if (section == null) {
      throw new EngineRepoError(
        `finishSection: form '${form.id}' has no section '${args.sectionCode}'`,
      );
    }
    const items = detail.items.filter((i) => i.section_code === args.sectionCode);
    const remainingMs =
      existing.deadline_at == null
        ? null
        : Math.max(0, Date.parse(existing.deadline_at) - this.now().getTime());
    const status = remainingMs === 0 ? "expired" : "submitted";
    const assetServed = form.delivery === "asset-served";
    const score = assetServed
      ? null
      : scoreExamSection(
          section as ExamForm["sections"][number],
          items,
          this.grader,
        );
    const graded = assetServed
      ? items
      : items.map((row) => {
          const hit = score!.grades.find((g) => g.question_id === row.question_id);
          return { ...row, correct: hit?.correct ?? null };
        });
    try {
      if (!assetServed && graded.length > 0) {
        await this.db.upsertExamRunItems(
          args.learnerId,
          args.runId,
          args.sectionCode,
          graded,
        );
      }
      const finished = await this.db.finishExamSection(
        args.learnerId,
        args.runId,
        args.sectionCode,
        status,
        assetServed
          ? // Placeholder only — server finishExamSectionServer overwrites
            // these for asset-served forms (FR-P2-6). Not a fabricated score.
            { raw_correct: 0, raw_scored_total: 0, scale_score: null }
          : {
              raw_correct: score!.raw_correct,
              raw_scored_total: score!.raw_scored_total,
              scale_score: score!.scale_score,
            },
        remainingMs,
      );
      const after = await this.db.getExamRun(args.learnerId, args.runId);
      if (after != null) {
        const composite = examComposite(form, after.attempts);
        await this.db.setExamRunComposite(args.learnerId, args.runId, composite);
      }
      return finished;
    } catch (err) {
      throw translate("finishSection", err);
    }
  }

  async getRun(args: {
    learnerId: string;
    runId: string;
  }): Promise<ExamRun | null> {
    const detail = await this.getRunDetail(args);
    return detail?.run ?? null;
  }

  async getRunDetail(args: {
    learnerId: string;
    runId: string;
  }): Promise<ExamRunDetail | null> {
    try {
      return await this.db.getExamRun(args.learnerId, args.runId);
    } catch (err) {
      throw translate("getRunDetail", err);
    }
  }

  async listRunsByLearner(args: { learnerId: string }): Promise<ExamRun[]> {
    const entries = await this.listRunEntries(args);
    return entries.map((e) => e.run);
  }

  async listRunEntries(args: {
    learnerId: string;
    formId?: string;
  }): Promise<ExamRunEntry[]> {
    try {
      return await this.db.listExamRunsByLearner(args.learnerId, args.formId);
    } catch (err) {
      throw translate("listRunEntries", err);
    }
  }

  async listItems(args: {
    learnerId: string;
    runId: string;
  }): Promise<ExamRunItem[]> {
    const detail = await this.getRunDetail(args);
    return detail?.items ?? [];
  }

  async listItemsByLearner(args: { learnerId: string }): Promise<ExamRunItem[]> {
    try {
      return await this.db.listExamRunItemsByLearner(args.learnerId);
    } catch (err) {
      throw translate("listItemsByLearner", err);
    }
  }

  async setBookmark(args: {
    learnerId: string;
    runId: string;
    sectionCode: ExamSectionCode;
    questionId: string;
    bookmarked: boolean;
  }): Promise<void> {
    try {
      await this.db.setExamBookmark(
        args.learnerId,
        args.runId,
        args.sectionCode,
        args.questionId,
        args.bookmarked,
      );
    } catch (err) {
      throw translate("setBookmark", err);
    }
  }

  private async resolveForm(
    learnerId: string,
    formId: string,
  ): Promise<ExamForm | ClientExamForm> {
    try {
      if (getExamFormDelivery(formId) === "asset-served") {
        const client = await this.db.getExamFormForClient(learnerId, formId);
        if (client != null) return client;
      }
    } catch {
      // G9: unknown registry id — fall through to getForm / client fetch.
    }
    try {
      const bundled = this.getForm(formId);
      if (bundled.delivery === "asset-served") {
        const client = await this.db.getExamFormForClient(learnerId, formId);
        if (client != null) return client;
        return bundled;
      }
      return bundled;
    } catch (err) {
      const client = await this.db.getExamFormForClient(learnerId, formId);
      if (client != null) return client;
      throw translate("resolveForm", err);
    }
  }

  private async requireDetail(
    learnerId: string,
    runId: string,
  ): Promise<ExamRunDetail> {
    const detail = await this.getRunDetail({ learnerId, runId });
    if (detail == null) {
      throw new EngineNotFoundError(`exam run not found: ${runId}`);
    }
    return detail;
  }
}

function translate(op: string, err: unknown): EngineRepoError {
  if (err instanceof EngineRepoError) return err;
  const detail = err instanceof Error ? err.message : String(err);
  return new EngineRepoError(`exam run repo ${op} failed: ${detail}`);
}
