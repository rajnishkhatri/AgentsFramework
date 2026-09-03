/**
 * Official-form JSON → client ExamForm + server-only keys (ADR-0042).
 *
 * Offline converter: integrity-fail-closed (FR-P2-1), then a pure parse
 * (FR-P2-2/17) and a thin emit of git-ignored `_generated/` artifacts (FR-P2-3/4).
 * Scripts layer — no React, no composition import.
 */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { needsImage } from "../lib/adapters/engine/exam_forms/exam_image_rule";
import {
  ClientExamForm,
  type AssetRef,
  type ClientExamQuestion,
  type ClientExamSection,
  type ExamBlueprint,
  type ExamPassage,
  type ExamSectionCode,
} from "../lib/wire/exam_entities";

export class OfficialFormIntegrityError extends Error {
  readonly code: OfficialFormIntegrityCode;

  constructor(code: OfficialFormIntegrityCode, message: string) {
    super(message);
    this.name = "OfficialFormIntegrityError";
    this.code = code;
  }
}

export type OfficialFormIntegrityCode =
  | "sha256"
  | "declared_count"
  | "missing_answer";

export type OfficialFormKeyEntry = {
  readonly answer_letter: string;
  readonly booklet_letter: string;
  readonly section: string;
  readonly number: number;
};

export type OfficialFormKeyMap = Readonly<
  Record<string, OfficialFormKeyEntry>
>;

export type ParseOfficialFormResult = {
  readonly clientForm: ClientExamForm;
  readonly keys: OfficialFormKeyMap;
};

export type ParseOfficialFormOptions = {
  readonly pdfBytes?: Uint8Array;
};

const AD = ["A", "B", "C", "D", "E"] as const;
const ODD_LETTERS = "ABCDE";
const EVEN_LETTERS = "FGHJK";
const SECTION_CODES: readonly ExamSectionCode[] = [
  "english",
  "math",
  "reading",
  "science",
];
const SUBJECT_BY_CODE: Record<ExamSectionCode, string> = {
  english: "act-english",
  math: "act-math",
  reading: "act-reading",
  science: "act-science",
};

type SourceJson = {
  form_id?: unknown;
  title?: unknown;
  blueprint?: unknown;
  source?: { sha256?: unknown; file?: unknown };
  sections?: unknown;
};

type SourceQuestion = {
  number?: unknown;
  answer?: unknown;
  scored?: unknown;
  passage?: unknown;
  stem?: unknown;
  choices?: unknown;
  text_fidelity?: unknown;
  reporting_category?: unknown;
  underlined_text?: unknown;
  image?: unknown;
};

type SourcePassage = {
  label?: unknown;
  title?: unknown;
  intro?: unknown;
  text?: unknown;
  pages?: unknown;
  question_numbers?: unknown;
  is_figure?: unknown;
};

type SourceSection = {
  code?: unknown;
  title?: unknown;
  minutes?: unknown;
  declared_question_count?: unknown;
  choice_count?: unknown;
  directions?: unknown;
  questions?: unknown;
  passages?: unknown;
  scoring?: unknown;
};

function asRecord(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new OfficialFormIntegrityError(
      "declared_count",
      `official form ${label} is not an object`,
    );
  }
  return value as Record<string, unknown>;
}

function sha256Hex(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

export function assertOfficialFormIntegrity(
  json: unknown,
  opts: ParseOfficialFormOptions = {},
): void {
  const form = asRecord(json, "root") as SourceJson;
  const source = asRecord(form.source, "source");
  const recorded = source.sha256;
  if (opts.pdfBytes !== undefined) {
    const onDisk = sha256Hex(opts.pdfBytes);
    if (typeof recorded !== "string" || recorded !== onDisk) {
      throw new OfficialFormIntegrityError(
        "sha256",
        `source.sha256 ${String(recorded)} ≠ on-disk PDF ${onDisk}`,
      );
    }
  }

  const sections = form.sections;
  if (!Array.isArray(sections) || sections.length === 0) {
    throw new OfficialFormIntegrityError(
      "declared_count",
      "official form has no sections",
    );
  }
  for (const raw of sections) {
    const section = asRecord(raw, "section") as SourceSection;
    const questions = section.questions;
    if (!Array.isArray(questions)) {
      throw new OfficialFormIntegrityError(
        "declared_count",
        `section ${String(section.code)} has no questions array`,
      );
    }
    const declared = section.declared_question_count;
    if (typeof declared === "number" && declared !== questions.length) {
      throw new OfficialFormIntegrityError(
        "declared_count",
        `declared_question_count ${declared} ≠ actual ${questions.length} ` +
          `on ${String(section.code)}`,
      );
    }
    for (const qRaw of questions) {
      const q = asRecord(qRaw, "question") as SourceQuestion;
      if (q.scored === true) {
        const answer = q.answer;
        if (typeof answer !== "string" || answer.length === 0) {
          throw new OfficialFormIntegrityError(
            "missing_answer",
            `scored item ${String(section.code)} Q${String(q.number)} has no answer`,
          );
        }
      }
    }
  }
}

function nullableString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function normalizeLetter(raw: string, choiceCount: 4 | 5): string | null {
  const even = EVEN_LETTERS.slice(0, choiceCount);
  const odd = ODD_LETTERS.slice(0, choiceCount);
  const evenIdx = even.indexOf(raw);
  if (evenIdx >= 0) return AD[evenIdx]!;
  const oddIdx = odd.indexOf(raw);
  if (oddIdx >= 0) return AD[oddIdx]!;
  return null;
}

function isFigurePassage(
  sectionCode: ExamSectionCode,
  passage: SourcePassage,
): boolean {
  if (passage.is_figure === true) return true;
  if (passage.is_figure === false) return false;
  // Official JSON has no is_figure flag; Science figure/table passages say so.
  if (sectionCode !== "science") return false;
  const blob = `${nullableString(passage.intro) ?? ""} ${nullableString(passage.text) ?? ""}`;
  return /\bfigures?\b|\btables?\b/i.test(blob);
}

function asset(formId: string, key: string): AssetRef {
  return { store: "form-image", form_id: formId, key };
}

function padPage(n: number): string {
  return String(n).padStart(3, "0");
}

function padQuestion(n: number): string {
  return String(n).padStart(2, "0");
}

function asSectionCode(value: unknown): ExamSectionCode {
  if (
    typeof value === "string" &&
    (SECTION_CODES as readonly string[]).includes(value)
  ) {
    return value as ExamSectionCode;
  }
  throw new Error(`unknown section code ${String(value)}`);
}

function asBlueprint(value: unknown): ExamBlueprint {
  if (
    value === "act-enhanced" ||
    value === "preact-secure-legacy" ||
    value === "test01"
  ) {
    return value;
  }
  throw new Error(`unknown blueprint ${String(value)}`);
}

function asChoiceCount(value: unknown): 4 | 5 {
  if (value === 5) return 5;
  return 4;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function scaleTable(scoring: unknown): Record<string, number> | null {
  if (scoring === null || typeof scoring !== "object" || Array.isArray(scoring)) {
    return null;
  }
  const raw = (scoring as { scale_conversion?: unknown }).scale_conversion;
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof v === "number") out[k] = v;
  }
  return Object.keys(out).length > 0 ? out : null;
}

/**
 * Pure parse: official-form JSON → client-safe ExamForm + server-only keys.
 */
export function parseOfficialForm(
  json: unknown,
  opts: ParseOfficialFormOptions = {},
): ParseOfficialFormResult {
  assertOfficialFormIntegrity(json, opts);
  const root = asRecord(json, "root") as SourceJson;
  const formId = typeof root.form_id === "string" ? root.form_id : "";
  if (!formId) throw new Error("official form is missing form_id");
  const blueprint = asBlueprint(root.blueprint);
  const compositeSections: ExamSectionCode[] =
    blueprint === "preact-secure-legacy"
      ? ["english", "math", "reading", "science"]
      : ["english", "math", "reading"];
  const compositeSet = new Set(compositeSections);
  const keys: Record<string, OfficialFormKeyEntry> = {};
  const sections: ClientExamSection[] = [];

  for (const rawSec of root.sections as unknown[]) {
    const sec = asRecord(rawSec, "section") as SourceSection;
    const code = asSectionCode(sec.code);
    const choiceCount = asChoiceCount(sec.choice_count);
    const rawPassages = Array.isArray(sec.passages) ? sec.passages : [];
    const rawQuestions = sec.questions as unknown[];
    const sourcePassages: SourcePassage[] = rawPassages.map((p) =>
      asRecord(p, "passage"),
    );
    const figureByLabel = new Map<string, boolean>();
    const passages: ExamPassage[] = sourcePassages.map((p) => {
      const label = typeof p.label === "string" ? p.label : "";
      const figure = isFigurePassage(code, p);
      figureByLabel.set(label, figure);
      const pages = Array.isArray(p.pages)
        ? p.pages.filter((n): n is number => typeof n === "number")
        : [];
      const qnums = Array.isArray(p.question_numbers)
        ? p.question_numbers.filter((n): n is number => typeof n === "number")
        : [];
      const pageKey =
        pages[0] !== undefined
          ? `${formId}/pages/p${padPage(pages[0])}.png`
          : null;
      return {
        label,
        title: nullableString(p.title),
        intro: nullableString(p.intro),
        text: nullableString(p.text),
        image: figure && pageKey ? asset(formId, pageKey) : null,
        question_numbers: qnums,
      };
    });

    const questions: ClientExamQuestion[] = rawQuestions.map((qRaw) => {
      const q = asRecord(qRaw, "question") as SourceQuestion;
      const number = typeof q.number === "number" ? q.number : 0;
      const label = nullableString(q.passage);
      const figure = label !== null && figureByLabel.get(label) === true;
      const fidelity =
        typeof q.text_fidelity === "string" ? q.text_fidelity : "ok";
      const wantsImage = needsImage({ text_fidelity: fidelity }, { is_figure: figure });
      const imageKey =
        typeof q.image === "string" && q.image.length > 0
          ? q.image
          : `${formId}/questions/${code}-q${padQuestion(number)}.png`;
      const rawChoices = Array.isArray(q.choices) ? q.choices : [];
      const choices = rawChoices.map((cRaw) => {
        const c = asRecord(cRaw, "choice");
        const booklet =
          typeof c.letter === "string" ? c.letter : "";
        const letter = normalizeLetter(booklet, choiceCount) ?? booklet;
        const text = typeof c.text === "string" ? c.text : "";
        return {
          letter,
          label: text,
          is_no_change: /^NO CHANGE$/i.test(text),
        };
      });
      const bookletAnswer =
        typeof q.answer === "string" ? q.answer : "";
      const answerLetter =
        bookletAnswer.length > 0
          ? (normalizeLetter(bookletAnswer, choiceCount) ?? bookletAnswer)
          : "";
      const id = `${formId}-${code}-${number}`;
      if (answerLetter) {
        keys[id] = {
          answer_letter: answerLetter,
          booklet_letter: bookletAnswer,
          section: code,
          number,
        };
      }
      const category = nullableString(q.reporting_category);
      const context = passages.find((p) => p.label === label)?.text ?? "";
      return {
        id,
        subject: SUBJECT_BY_CODE[code],
        skill_id: category ? `s-${category.toLowerCase()}` : "s-field-test",
        difficulty: 3,
        context_html: escapeHtml(context),
        stem: typeof q.stem === "string" ? q.stem : "",
        choices,
        rule_md: "",
        item_type: nullableString(q.underlined_text)
          ? "underlined-span-mc"
          : "mc",
        misconception: null,
        reviewed: true,
        generated_by: "official-form-convert",
        reporting_category: category,
        scored: q.scored === true,
        passage: label,
        image: wantsImage ? asset(formId, imageKey) : null,
      };
    });

    sections.push({
      code,
      title: typeof sec.title === "string" ? sec.title : code,
      minutes: typeof sec.minutes === "number" ? sec.minutes : 1,
      choice_count: choiceCount,
      directions: typeof sec.directions === "string" ? sec.directions : "",
      composite: compositeSet.has(code),
      scale_table: scaleTable(sec.scoring),
      questions,
      passages,
    });
  }

  const clientForm = ClientExamForm.parse({
    id: formId,
    title: typeof root.title === "string" ? root.title : formId,
    blueprint,
    composite_sections: compositeSections,
    delivery: "asset-served",
    sections,
  });
  return { clientForm, keys };
}

export type ConvertOfficialFormArgs = {
  readonly srcDir: string;
  readonly formId: string;
  readonly outDir: string;
};

export function convertOfficialForm(args: ConvertOfficialFormArgs): {
  clientPath: string;
  keysPath: string;
} {
  const jsonPath = join(args.srcDir, "json", `${args.formId}.json`);
  const json = JSON.parse(readFileSync(jsonPath, "utf8")) as SourceJson;
  const sourceFile =
    typeof json.source === "object" &&
    json.source !== null &&
    "file" in json.source &&
    typeof json.source.file === "string"
      ? json.source.file
      : `${args.formId}.pdf`;
  const pdfPath = join(args.srcDir, "preact", sourceFile);
  const pdfBytes = existsSync(pdfPath) ? new Uint8Array(readFileSync(pdfPath)) : null;
  // Parse (integrity first) before any write — a throw leaves outDir untouched.
  const result =
    pdfBytes !== null
      ? parseOfficialForm(json, { pdfBytes })
      : parseOfficialForm(json);
  mkdirSync(args.outDir, { recursive: true });
  const clientPath = join(args.outDir, `${args.formId}.client.ts`);
  const keysPath = join(args.outDir, `${args.formId}.keys.ts`);
  writeFileSync(clientPath, renderClientModule(result.clientForm), "utf8");
  writeFileSync(keysPath, renderKeysModule(result.keys), "utf8");
  return { clientPath, keysPath };
}

function renderClientModule(form: ClientExamForm): string {
  return `/**
 * GENERATED by scripts/convert_official_form.ts — DO NOT EDIT BY HAND.
 * Client-safe official form (FR-P2-3): zero answer-bearing fields.
 * Git-ignored (FR-P2-4). Re-generate with \`pnpm convert:official\`.
 */
import type { ClientExamForm } from "../../../wire/exam_entities";

export const CLIENT_EXAM_FORM: ClientExamForm = ${JSON.stringify(form, null, 2)};
`;
}

function renderKeysModule(keys: OfficialFormKeyMap): string {
  return `/**
 * GENERATED by scripts/convert_official_form.ts — DO NOT EDIT BY HAND.
 * Server-only answer keys. Never import from app/, components/, or
 * composition_engine_browser.ts (FR-P2-8).
 */
export const FORM_KEYS = ${JSON.stringify(keys, null, 2)};
`;
}

function parseCli(argv: readonly string[]): ConvertOfficialFormArgs {
  let formId = "act-practice-test-2";
  let srcDir = "";
  let outDir = "";
  const args = argv.slice(2);
  for (let i = 0; i < args.length; i++) {
    const a = args[i]!;
    if (a === "--src") {
      srcDir = args[++i] ?? "";
    } else if (a === "--out") {
      outDir = args[++i] ?? "";
    } else if (!a.startsWith("-")) {
      formId = a;
    }
  }
  if (!srcDir) {
    throw new Error(
      "convert:official requires --src <path-to-docs/preact9secure>",
    );
  }
  if (!outDir) {
    outDir = join(
      dirname(fileURLToPath(import.meta.url)),
      "../lib/adapters/engine/exam_forms/_generated",
    );
  }
  return { formId, srcDir, outDir };
}

function main(): void {
  const args = parseCli(process.argv);
  const { clientPath, keysPath } = convertOfficialForm(args);
  // eslint-disable-next-line no-console
  console.log(`convert:official ${args.formId} → ${clientPath}\n  keys → ${keysPath}`);
}

const invokedDirectly =
  process.argv[1] != null &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) main();

