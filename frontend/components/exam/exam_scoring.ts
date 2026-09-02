/**
 * Pure exam scoring (W2-2 / FR-7, FR-8, FR-27, FR-28).
 *
 * Grades once per item via the injected engine `Grader`. Raw and scale
 * count scored items only. `scale_score` is honest null when the form
 * has no conversion table (FR-7 / AP-6). Composite is null until every
 * declared composite section is submitted/expired, then round(mean)
 * with official .5-up. The reducer does not grade.
 */

import type { Grader } from "@/lib/ports/engine/grader";
import type {
  ExamForm,
  ExamRunItem,
  ExamSection,
  ExamSectionAttempt,
} from "@/lib/wire/exam_entities";

export type ExamItemGrade = {
  question_id: string;
  correct: boolean | null;
};

export type ExamSectionScore = {
  grades: ExamItemGrade[];
  raw_correct: number;
  raw_scored_total: number;
  percent: number | null;
  scale_score: number | null;
};

const FINISHED: ReadonlySet<ExamSectionAttempt["status"]> = new Set([
  "submitted",
  "expired",
]);

export function scoreExamSection(
  section: Pick<ExamSection, "questions" | "scale_table">,
  items: readonly Pick<ExamRunItem, "question_id" | "chosen_letter">[],
  grader: Grader,
): ExamSectionScore {
  const chosen = new Map(items.map((i) => [i.question_id, i.chosen_letter]));
  const grades: ExamItemGrade[] = [];
  let rawCorrect = 0;
  let rawScoredTotal = 0;

  for (const question of section.questions) {
    // Missing item = never answered / never flushed — not a fabricated letter (G9).
    const letter = chosen.get(question.id) ?? null;
    const verdict = grader.grade(question, { letter });
    const correct = verdict === null ? null : verdict.correct;
    grades.push({ question_id: question.id, correct });
    if (!question.scored) continue;
    rawScoredTotal += 1;
    if (correct === true) rawCorrect += 1;
  }

  return {
    grades,
    raw_correct: rawCorrect,
    raw_scored_total: rawScoredTotal,
    // Zero scored items → percent is undecidable, not a fabricated 0 (AP-6 / G9).
    percent: rawScoredTotal === 0 ? null : rawCorrect / rawScoredTotal,
    scale_score: lookupScale(section.scale_table, rawCorrect),
  };
}

function lookupScale(
  table: ExamSection["scale_table"],
  raw: number,
): number | null {
  if (table === null) return null; // FR-7: Form 805 / Test-01 — no fabricated scale
  const hit = table[String(raw)];
  // Missing row: table does not define this raw — AP-6, do not interpolate.
  return hit === undefined ? null : hit;
}

export function examComposite(
  form: Pick<ExamForm, "composite_sections">,
  attempts: readonly Pick<
    ExamSectionAttempt,
    "section_code" | "status" | "scale_score"
  >[],
): number | null {
  const byCode = new Map(attempts.map((a) => [a.section_code, a]));
  const scales: number[] = [];
  for (const code of form.composite_sections) {
    const attempt = byCode.get(code);
    if (attempt === undefined || !FINISHED.has(attempt.status)) {
      return null; // FR-8: never a partial average
    }
    if (attempt.scale_score === null) {
      return null; // FR-7: finished composite section with no scale
    }
    scales.push(attempt.scale_score);
  }
  if (scales.length === 0) {
    return null; // form declares no composite sections — AP-6
  }
  const mean = scales.reduce((sum, n) => sum + n, 0) / scales.length;
  return roundHalfUp(mean);
}

/** Official composite rounding: nearest integer, .5 up (non-negative scores). */
function roundHalfUp(n: number): number {
  return Math.floor(n + 0.5);
}
