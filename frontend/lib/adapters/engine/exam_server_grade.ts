/**
 * Server-side grade-on-finish for asset-served forms (ADR-0042 / FR-P2-6).
 *
 * Pure `scoreExamSection` fed with server keys. The route stays thin (F-R4):
 * it calls `finishExamSectionServer` instead of trusting client grades.
 */

import {
  scoreExamSection,
  type ExamSectionScore,
} from "../../../components/exam/exam_scoring";
import { getExamFormDelivery } from "./exam_forms";
import { EngineRepoError } from "../../ports/engine/errors";
import type { Grader } from "../../ports/engine/grader";
import type {
  ClientExamForm,
  ExamForm,
  ExamRunItem,
  ExamSectionAttempt,
  ExamSectionCode,
} from "../../wire/exam_entities";
import type {
  EngineDb,
  ExamFormKeyMap,
  ExamSectionFinishStatus,
  ExamSectionGrades,
} from "./db/engine_db";

export function gradeAssetServedSection(
  form: Pick<ExamForm, "sections"> | Pick<ClientExamForm, "sections">,
  keys: ExamFormKeyMap,
  sectionCode: ExamSectionCode,
  items: readonly ExamRunItem[],
  grader: Grader,
): ExamSectionScore {
  const section = form.sections.find((s) => s.code === sectionCode);
  if (section == null) {
    throw new EngineRepoError(
      `gradeAssetServedSection: form has no section '${sectionCode}'`,
    );
  }
  const keyed = {
    ...section,
    questions: section.questions.map((question) => {
      const entry = keys.keys[question.id];
      if (entry == null) {
        throw new EngineRepoError(
          `gradeAssetServedSection: missing key for '${question.id}'`,
        );
      }
      return {
        ...question,
        answer_letter: entry.answer_letter,
        why_correct_md: entry.why_correct_md,
        why_tempted_md: entry.why_tempted_md,
        per_choice_rationale: entry.per_choice_rationale,
      };
    }),
  };
  return scoreExamSection(keyed, items, grader);
}

export async function finishExamSectionServer(
  db: EngineDb,
  grader: Grader,
  learnerId: string,
  runId: string,
  section: ExamSectionCode,
  status: ExamSectionFinishStatus,
  grades: ExamSectionGrades,
  remainingMs: number | null,
): Promise<ExamSectionAttempt> {
  const detail = await db.getExamRun(learnerId, runId);
  if (detail == null) {
    throw new EngineRepoError(`finishExamSectionServer: run not found`);
  }
  const delivery = getExamFormDelivery(detail.run.form_id);
  if (delivery !== "asset-served") {
    return db.finishExamSection(
      learnerId,
      runId,
      section,
      status,
      grades,
      remainingMs,
    );
  }

  const keys = await db.getExamFormKeys(detail.run.form_id);
  const form = await db.getExamFormForClient(learnerId, detail.run.form_id);
  if (keys == null || form == null) {
    throw new EngineRepoError(
      `finishExamSectionServer: keys or form not loadable for '${detail.run.form_id}'`,
    );
  }
  const items = detail.items.filter((i) => i.section_code === section);
  const score = gradeAssetServedSection(form, keys, section, items, grader);
  const graded = items.map((row) => {
    const hit = score.grades.find((g) => g.question_id === row.question_id);
    return { ...row, correct: hit?.correct ?? null };
  });
  if (graded.length > 0) {
    await db.upsertExamRunItems(learnerId, runId, section, graded);
  }
  return db.finishExamSection(
    learnerId,
    runId,
    section,
    status,
    {
      raw_correct: score.raw_correct,
      raw_scored_total: score.raw_scored_total,
      scale_score: score.scale_score,
    },
    remainingMs,
  );
}
