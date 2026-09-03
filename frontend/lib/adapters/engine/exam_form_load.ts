/**
 * Server-side exam form / key loaders (ADR-0042).
 *
 * Client payloads go through `ClientExamForm.strict()` so answer-bearing
 * fields cannot leak. Generated key loaders stay empty until S-I1 registers
 * a real `_generated/*.keys.ts` (never imported from a client module).
 */

import type { ClientExamForm, ExamForm } from "../../wire/exam_entities";
import { ClientExamForm as ClientExamFormSchema } from "../../wire/exam_entities";
import {
  getExamForm,
  getExamFormDelivery,
  loadAssetServedForm,
} from "./exam_forms";
import type {
  ExamFormKeyEntry,
  ExamFormKeyMap,
  ExamReviewReveal,
  ExamRunDetail,
} from "./db/engine_db";

/** S-I1 registers PT2 here. Empty in CI — `_generated/` is gitignored. */
const GENERATED_KEY_LOADERS: Record<string, () => ExamFormKeyMap> = {};

export function stripExamFormForClient(form: ExamForm): ClientExamForm {
  return ClientExamFormSchema.parse({
    ...form,
    sections: form.sections.map((section) => ({
      ...section,
      questions: section.questions.map((question) => {
        const {
          answer_letter: _answer,
          per_choice_rationale: _rationale,
          why_correct_md: _why,
          why_tempted_md: _tempted,
          ...rest
        } = question;
        return rest;
      }),
    })),
  });
}

export function extractExamFormKeys(form: ExamForm): ExamFormKeyMap {
  const keys: Record<string, ExamFormKeyEntry> = {};
  for (const section of form.sections) {
    for (const question of section.questions) {
      keys[question.id] = {
        answer_letter: question.answer_letter,
        why_correct_md: question.why_correct_md,
        why_tempted_md: question.why_tempted_md,
        per_choice_rationale: question.per_choice_rationale,
      };
    }
  }
  return { form_id: form.id, keys };
}

export function loadExamFormForClient(formId: string): ClientExamForm | null {
  try {
    const delivery = getExamFormDelivery(formId);
    const form =
      delivery === "asset-served"
        ? loadAssetServedForm(formId)
        : getExamForm(formId);
    // G9: asset-served `_generated` module absent (spec §6).
    if (form == null) return null;
    return stripExamFormForClient(form);
  } catch {
    // G9: unknown form id — not an I/O failure.
    return null;
  }
}

const FINISHED = new Set(["submitted", "expired"]);

/** Merge keys onto getExamRun only for finished section attempts (FR-P2-9). */
export function attachExamReviewReveal(
  detail: ExamRunDetail,
  keys: ExamFormKeyMap | null,
): ExamRunDetail {
  if (keys == null) return { ...detail, review: [] };
  const finished = new Set(
    detail.attempts
      .filter((a) => FINISHED.has(a.status))
      .map((a) => a.section_code),
  );
  const review: ExamReviewReveal[] = [];
  for (const item of detail.items) {
    if (!finished.has(item.section_code)) continue;
    const entry = keys.keys[item.question_id];
    if (entry == null) continue;
    review.push({
      question_id: item.question_id,
      section_code: item.section_code,
      ...entry,
    });
  }
  return { ...detail, review };
}

export function loadExamFormKeys(formId: string): ExamFormKeyMap | null {
  try {
    const delivery = getExamFormDelivery(formId);
    if (delivery === "asset-served") {
      const load = GENERATED_KEY_LOADERS[formId];
      // G9: generated keys artifact absent (CI / fresh checkout).
      if (load === undefined) return null;
      return load();
    }
    return extractExamFormKeys(getExamForm(formId));
  } catch {
    // G9: unknown form id.
    return null;
  }
}
