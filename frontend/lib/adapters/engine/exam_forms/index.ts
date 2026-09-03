/**
 * Exam form registry (ADR-0040 / ADR-0042).
 * Load-time asserts (FR-6): empty form/section and unsupported choice_count
 * throw at import, never at first render. Asset-served forms are listed
 * only when a generated client module is registered (spec §6).
 */

import type { ExamForm, ExamFormDelivery } from "../../../wire/exam_entities";
import {
  TEST01_ENGLISH_DELIVERY,
  TEST01_ENGLISH_FORM,
  TEST01_ENGLISH_FORM_ID,
} from "./test01_english";

/** Phase-1 renderer supports 4-choice items only (spec §6 / FR-6). */
export const SUPPORTED_CHOICE_COUNTS = [4] as const;

export type { ExamFormDelivery };

export type ExamFormEntry =
  | { readonly delivery: "client-bundled"; readonly form: ExamForm }
  | { readonly delivery: "asset-served"; readonly formId: string };

const REGISTRY: readonly ExamFormEntry[] = [
  { form: TEST01_ENGLISH_FORM, delivery: TEST01_ENGLISH_DELIVERY },
  { formId: "fake-official-form", delivery: "asset-served" },
  { formId: "act-practice-test-2", delivery: "asset-served" },
];

/**
 * Generated client-form loaders. Empty in CI (`_generated/` gitignored).
 * Server-only `generated_official_form.ts` registers PT2 when artifacts exist.
 */
const GENERATED_LOADERS: Record<string, () => ExamForm> = {};

/** Server-only: bind a generated asset-served form so `listExamForms` can list it. */
export function registerGeneratedFormLoader(
  formId: string,
  load: () => ExamForm,
): void {
  GENERATED_LOADERS[formId] = load;
}

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
  if (entry.delivery === "client-bundled") {
    assertExamFormLoadable(entry.form);
  }
}

/**
 * Server-side loader for an asset-served form.
 * Returns null when `_generated/<formId>.client` is not registered
 * (fresh checkout / CI — spec §6; never a blank exam).
 */
export function loadAssetServedForm(formId: string): ExamForm | null {
  const load = GENERATED_LOADERS[formId];
  if (load === undefined) {
    return null; // G9: generated client module absent (not an I/O failure)
  }
  const form = load();
  assertExamFormLoadable(form);
  return form;
}

function entryId(entry: ExamFormEntry): string {
  return entry.delivery === "client-bundled" ? entry.form.id : entry.formId;
}

export function listRegisteredExamFormIds(): string[] {
  return REGISTRY.map(entryId);
}

export function listExamForms(): ExamForm[] {
  const out: ExamForm[] = [];
  for (const entry of REGISTRY) {
    if (entry.delivery === "client-bundled") {
      out.push(entry.form);
      continue;
    }
    const loaded = loadAssetServedForm(entry.formId);
    if (loaded !== null) {
      out.push(loaded);
    }
  }
  return out;
}

export function getExamForm(id: string): ExamForm {
  const hit = REGISTRY.find((e) => entryId(e) === id);
  if (!hit) {
    throw new Error(`exam_forms: unknown form '${id}'`);
  }
  if (hit.delivery === "client-bundled") {
    return hit.form;
  }
  const loaded = loadAssetServedForm(hit.formId);
  if (loaded === null) {
    throw new Error(`exam_forms: asset-served form '${id}' is not loadable`);
  }
  return loaded;
}

export function getExamFormDelivery(id: string): ExamFormDelivery {
  const hit = REGISTRY.find((e) => entryId(e) === id);
  if (!hit) {
    throw new Error(`exam_forms: unknown form '${id}'`);
  }
  return hit.delivery;
}

export { TEST01_ENGLISH_FORM_ID };
