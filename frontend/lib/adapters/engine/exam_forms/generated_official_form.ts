/**
 * Server-only loader for git-ignored `_generated/` official-form artifacts.
 *
 * Uses `node:fs` so it must never be imported from `app/`, `components/`, or
 * `composition_engine_browser.ts` (FR-P2-4/8). Missing files → no register
 * (CI / fresh checkout — spec §6).
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  ClientExamForm,
  ExamForm,
  type ExamQuestion,
} from "../../../wire/exam_entities";
import type { ExamFormKeyMap } from "../db/engine_db";
import { registerGeneratedKeyLoader } from "../exam_form_load";
import { registerGeneratedFormLoader } from "./index";

export const PT2_FORM_ID = "act-practice-test-2";

const GENERATED_DIR = join(dirname(fileURLToPath(import.meta.url)), "_generated");

function readGeneratedExport(filePath: string, exportName: string): unknown {
  const text = readFileSync(filePath, "utf8");
  const marker = `export const ${exportName}`;
  const start = text.indexOf(marker);
  if (start < 0) {
    throw new Error(`generated_official_form: missing ${exportName} in ${filePath}`);
  }
  const eq = text.indexOf("=", start);
  if (eq < 0) {
    throw new Error(`generated_official_form: missing assignment for ${exportName}`);
  }
  let body = text.slice(eq + 1).trim();
  if (body.endsWith(";")) body = body.slice(0, -1);
  return JSON.parse(body);
}

function hydrateExamForm(client: ClientExamForm, keys: ExamFormKeyMap): ExamForm {
  return ExamForm.parse({
    ...client,
    sections: client.sections.map((section) => ({
      ...section,
      questions: section.questions.map((question) => {
        const entry = keys.keys[question.id];
        const hydrated: ExamQuestion = {
          ...question,
          answer_letter: entry?.answer_letter ?? "",
          per_choice_rationale: entry?.per_choice_rationale ?? {},
          why_correct_md: entry?.why_correct_md ?? "",
          why_tempted_md: entry?.why_tempted_md ?? "",
        };
        return hydrated;
      }),
    })),
  });
}

function adaptOfficialKeys(
  formId: string,
  raw: Record<string, { answer_letter?: unknown }>,
): ExamFormKeyMap {
  const keys: ExamFormKeyMap["keys"] = {};
  for (const [id, entry] of Object.entries(raw)) {
    if (typeof entry.answer_letter !== "string") continue;
    keys[id] = {
      answer_letter: entry.answer_letter,
      why_correct_md: "",
      why_tempted_md: "",
      per_choice_rationale: {},
    };
  }
  return { form_id: formId, keys };
}

export function tryLoadGeneratedOfficialForm(formId: string): ExamForm | null {
  const clientPath = join(GENERATED_DIR, `${formId}.client.ts`);
  const keysPath = join(GENERATED_DIR, `${formId}.keys.ts`);
  if (!existsSync(clientPath) || !existsSync(keysPath)) {
    return null; // G9: gitignored artifacts absent (CI / fresh checkout)
  }
  const client = ClientExamForm.parse(
    readGeneratedExport(clientPath, "CLIENT_EXAM_FORM"),
  );
  const keys = adaptOfficialKeys(
    formId,
    readGeneratedExport(keysPath, "FORM_KEYS") as Record<
      string,
      { answer_letter?: unknown }
    >,
  );
  return hydrateExamForm(client, keys);
}

export function tryLoadGeneratedOfficialKeys(
  formId: string,
): ExamFormKeyMap | null {
  const keysPath = join(GENERATED_DIR, `${formId}.keys.ts`);
  if (!existsSync(keysPath)) {
    return null; // G9: keys artifact absent
  }
  return adaptOfficialKeys(
    formId,
    readGeneratedExport(keysPath, "FORM_KEYS") as Record<
      string,
      { answer_letter?: unknown }
    >,
  );
}

function registerIfPresent(formId: string): void {
  const form = tryLoadGeneratedOfficialForm(formId);
  const keys = tryLoadGeneratedOfficialKeys(formId);
  if (form !== null) {
    registerGeneratedFormLoader(formId, () => form);
  }
  if (keys !== null) {
    registerGeneratedKeyLoader(formId, () => keys);
  }
}

registerIfPresent(PT2_FORM_ID);
