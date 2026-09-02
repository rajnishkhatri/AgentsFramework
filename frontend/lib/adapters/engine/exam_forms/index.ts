/**
 * Exam form registry (ADR-0040). Phase 1 = Test-01 English.
 * Load-time asserts (FR-6): empty form/section and unsupported choice_count
 * throw at import, never at first render.
 */

import type { ExamForm } from "../../../wire/exam_entities";
import {
  TEST01_ENGLISH_DELIVERY,
  TEST01_ENGLISH_FORM,
  TEST01_ENGLISH_FORM_ID,
} from "./test01_english";

/** Phase-1 renderer supports 4-choice items only (spec §6 / FR-6). */
export const SUPPORTED_CHOICE_COUNTS = [4] as const;

export type ExamFormDelivery = "client-bundled" | "db-served";

export type ExamFormEntry = {
  readonly form: ExamForm;
  readonly delivery: ExamFormDelivery;
};

const REGISTRY: readonly ExamFormEntry[] = [
  { form: TEST01_ENGLISH_FORM, delivery: TEST01_ENGLISH_DELIVERY },
];

export function assertExamFormLoadable(form: ExamForm): void {
  if (form.sections.length === 0) {
    throw new Error(`exam_forms: empty form '${form.id}'`);
  }
  for (const section of form.sections) {
    if (section.questions.length === 0) {
      throw new Error(
        `exam_forms: empty section '${section.code}' on form '${form.id}'`,
      );
    }
    if (
      !SUPPORTED_CHOICE_COUNTS.includes(
        section.choice_count as (typeof SUPPORTED_CHOICE_COUNTS)[number],
      )
    ) {
      throw new Error(
        `exam_forms: unsupported choice_count ${section.choice_count} ` +
          `on '${form.id}'/${section.code} (phase-1 renderer is 4 only)`,
      );
    }
  }
}

for (const entry of REGISTRY) {
  assertExamFormLoadable(entry.form);
}

export function listExamForms(): ExamForm[] {
  return REGISTRY.map((e) => e.form);
}

export function getExamForm(id: string): ExamForm {
  const hit = REGISTRY.find((e) => e.form.id === id);
  if (!hit) {
    throw new Error(`exam_forms: unknown form '${id}'`);
  }
  return hit.form;
}

export function getExamFormDelivery(id: string): ExamFormDelivery {
  const hit = REGISTRY.find((e) => e.form.id === id);
  if (!hit) {
    throw new Error(`exam_forms: unknown form '${id}'`);
  }
  return hit.delivery;
}

export { TEST01_ENGLISH_FORM_ID };
