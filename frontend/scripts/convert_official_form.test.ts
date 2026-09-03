/**
 * Official-form converter (FR-P2-1…4, FR-P2-17) — integrity first, then parse.
 *
 * A-1 pins the fail-closed integrity gate: a bad sha256, a count mismatch, or a
 * scored item with no answer must throw and emit no artifacts (AP-6).
 * Synthetic JSON only in the default (CI) tier — never ©ACT fixtures.
 */

import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { assetRefToUrl } from "../components/exam/exam_item_vm";
import { LocalFileAssetStore } from "../lib/adapters/engine/assets/local_file_asset_store";
import { ClientExamForm } from "../lib/wire/exam_entities";
import {
  OfficialFormIntegrityError,
  convertOfficialForm,
  parseOfficialForm,
} from "./convert_official_form";

const HERE = dirname(fileURLToPath(import.meta.url));
// Private ©ACT folder is not copied into worktrees — point at the main checkout.
const PRIVATE_SRC = resolve(
  HERE,
  "../../../../docs/preact9secure",
);
const PT2_JSON = join(PRIVATE_SRC, "json/act-practice-test-2.json");
const PT2_PDF = join(
  PRIVATE_SRC,
  "preact/ACT-Test-Prep-ACT-Practice-Test-2-Form.pdf",
);
const EXTRACT_TOOLS = join(PRIVATE_SRC, "tools");
const VENV_PYTHON = resolve(HERE, "../../.venv/bin/python");
const PT2_AVAILABLE =
  existsSync(PT2_JSON) && existsSync(PT2_PDF) && existsSync(VENV_PYTHON);

const PDF_BYTES = new TextEncoder().encode("%PDF-1.4 synthetic converter probe\n");
const PDF_SHA = createHash("sha256").update(PDF_BYTES).digest("hex");

function section(over: Record<string, unknown> = {}) {
  return {
    code: "english",
    title: "ENGLISH TEST",
    minutes: 35,
    question_count: 1,
    declared_question_count: 1,
    pages: [1, 1],
    choice_count: 4,
    directions: "Synthetic directions.",
    passages: [],
    questions: [
      {
        number: 1,
        passage: null,
        page: 1,
        column: "L",
        bbox: [0, 0, 1, 1],
        stem: "Which choice is best?",
        choices: [
          { letter: "A", text: "one" },
          { letter: "B", text: "two" },
          { letter: "C", text: "three" },
          { letter: "D", text: "four" },
        ],
        missing_choice_letters: [],
        text_fidelity: "ok",
        answer: "B",
        reporting_category: "CSE",
        scored: true,
        underlined_text: null,
        image: "synth-form/questions/english-q01.png",
        raw_text: "1. Which choice is best?",
      },
    ],
    scoring: {
      raw_max: 1,
      category_totals: { CSE: 1 },
      scale_conversion: { "1": 36, "0": 1 },
    },
    ...over,
  };
}

function officialJson(over: Record<string, unknown> = {}) {
  return {
    schema_version: "1.0",
    form_id: "synth-form",
    title: "Synthetic Official Form",
    publisher: "test",
    copyright_year: 2026,
    blueprint: "act-enhanced",
    source: { file: "synth.pdf", sha256: PDF_SHA, pages: 1 },
    extracted_at: "2026-09-03T00:00:00+00:00",
    extractor: "test",
    sections: [section()],
    ...over,
  };
}

function writeSrcTree(json: unknown, pdfBytes: Uint8Array = PDF_BYTES): string {
  const root = mkdtempSync(join(tmpdir(), "official-form-src-"));
  const jsonDir = join(root, "json");
  const preactDir = join(root, "preact");
  mkdirSync(jsonDir, { recursive: true });
  mkdirSync(preactDir, { recursive: true });
  const formId =
    json !== null &&
    typeof json === "object" &&
    "form_id" in json &&
    typeof json.form_id === "string"
      ? json.form_id
      : "synth-form";
  writeFileSync(join(jsonDir, `${formId}.json`), JSON.stringify(json), "utf8");
  writeFileSync(join(preactDir, "synth.pdf"), pdfBytes);
  return root;
}

describe("parseOfficialForm integrity (A-1 / FR-P2-1)", () => {
  it("throws and emits nothing when recorded source.sha256 ≠ on-disk PDF", () => {
    const json = officialJson({
      source: { file: "synth.pdf", sha256: "a".repeat(64), pages: 1 },
    });
    const src = writeSrcTree(json);
    const outDir = mkdtempSync(join(tmpdir(), "official-form-out-"));
    expect(() =>
      convertOfficialForm({ srcDir: src, formId: "synth-form", outDir }),
    ).toThrow(OfficialFormIntegrityError);
    expect(readdirSync(outDir)).toEqual([]);
  });

  it("throws and emits nothing when recorded source.sha256 is a tampered value", () => {
    const json = officialJson({
      source: {
        file: "synth.pdf",
        sha256: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        pages: 1,
      },
    });
    expect(() => parseOfficialForm(json, { pdfBytes: PDF_BYTES })).toThrow(
      OfficialFormIntegrityError,
    );
    expect(() => parseOfficialForm(json, { pdfBytes: PDF_BYTES })).toThrow(
      /sha256/i,
    );
  });

  it("throws and emits nothing when declared_question_count ≠ actual", () => {
    const json = officialJson({
      sections: [section({ declared_question_count: 50, question_count: 50 })],
    });
    const src = writeSrcTree(json);
    const outDir = mkdtempSync(join(tmpdir(), "official-form-out-"));
    expect(() => parseOfficialForm(json)).toThrow(OfficialFormIntegrityError);
    expect(() => parseOfficialForm(json)).toThrow(/declared_question_count/i);
    expect(() =>
      convertOfficialForm({ srcDir: src, formId: "synth-form", outDir }),
    ).toThrow(OfficialFormIntegrityError);
    expect(readdirSync(outDir)).toEqual([]);
  });

  it("throws and emits nothing when a scored item has no answer", () => {
    const json = officialJson({
      sections: [
        section({
          questions: [
            {
              number: 1,
              passage: null,
              page: 1,
              column: "L",
              bbox: [0, 0, 1, 1],
              stem: "Which choice is best?",
              choices: [
                { letter: "A", text: "one" },
                { letter: "B", text: "two" },
                { letter: "C", text: "three" },
                { letter: "D", text: "four" },
              ],
              missing_choice_letters: [],
              text_fidelity: "ok",
              answer: null,
              reporting_category: "CSE",
              scored: true,
              underlined_text: null,
              image: "synth-form/questions/english-q01.png",
              raw_text: "1. Which choice is best?",
            },
          ],
        }),
      ],
    });
    const src = writeSrcTree(json);
    const outDir = mkdtempSync(join(tmpdir(), "official-form-out-"));
    expect(() => parseOfficialForm(json)).toThrow(OfficialFormIntegrityError);
    expect(() => parseOfficialForm(json)).toThrow(/answer/i);
    expect(() =>
      convertOfficialForm({ srcDir: src, formId: "synth-form", outDir }),
    ).toThrow(OfficialFormIntegrityError);
    expect(readdirSync(outDir)).toEqual([]);
  });
});

function q(over: Record<string, unknown>) {
  return {
    passage: null,
    page: 1,
    column: "L",
    bbox: [0, 0, 1, 1],
    missing_choice_letters: [],
    underlined_text: null,
    raw_text: "",
    image: null,
    reporting_category: "CSE",
    scored: true,
    ...over,
  };
}

function fourSectionSource() {
  return officialJson({
    form_id: "synth-pt",
    title: "Synthetic four-section form",
    sections: [
      section({
        code: "english",
        title: "ENGLISH TEST",
        minutes: 35,
        question_count: 2,
        declared_question_count: 2,
        passages: [
          {
            label: "I",
            title: "A Synthetic Passage",
            intro: null,
            text: "Synthetic english passage text.",
            lines: null,
            pages: [1],
            question_numbers: [1, 2],
          },
        ],
        questions: [
          q({
            number: 1,
            passage: "I",
            stem: "English stem one",
            choices: [
              { letter: "A", text: "NO CHANGE" },
              { letter: "B", text: "was" },
              { letter: "C", text: "were" },
              { letter: "D", text: "been" },
            ],
            text_fidelity: "ok",
            answer: "B",
            reporting_category: "KLA",
            scored: true,
          }),
          q({
            number: 2,
            passage: "I",
            stem: "English stem two",
            choices: [
              { letter: "F", text: "keep" },
              { letter: "G", text: "drop" },
              { letter: "H", text: "swap" },
              { letter: "J", text: "move" },
            ],
            text_fidelity: "ok",
            answer: "H",
            reporting_category: "POW",
            scored: false,
          }),
        ],
        scoring: {
          raw_max: 1,
          category_totals: { KLA: 1 },
          scale_conversion: { "1": 36, "0": 1 },
        },
      }),
      section({
        code: "math",
        title: "MATHEMATICS TEST",
        minutes: 50,
        question_count: 2,
        declared_question_count: 2,
        passages: [],
        questions: [
          q({
            number: 1,
            stem: "Math prose item",
            choices: [
              { letter: "A", text: "1" },
              { letter: "B", text: "2" },
              { letter: "C", text: "3" },
              { letter: "D", text: "4" },
            ],
            text_fidelity: "ok",
            answer: "A",
            reporting_category: "S",
            image: "synth-pt/questions/math-q01.png",
          }),
          q({
            number: 2,
            stem: "1 _ 30 of the circle",
            choices: [
              { letter: "F", text: "1/2" },
              { letter: "G", text: "1/3" },
              { letter: "H", text: "1/4" },
              { letter: "J", text: "1/5" },
            ],
            text_fidelity: "math-notation",
            answer: "J",
            reporting_category: "F",
            image: "synth-pt/questions/math-q02.png",
          }),
        ],
        scoring: {
          raw_max: 2,
          category_totals: { S: 1, F: 1 },
          scale_conversion: { "2": 36, "1": 20, "0": 1 },
        },
      }),
      section({
        code: "reading",
        title: "READING TEST",
        minutes: 40,
        question_count: 1,
        declared_question_count: 1,
        passages: [
          {
            label: "I",
            title: null,
            intro: "LITERARY NARRATIVE: a synthetic intro.",
            text: "Synthetic reading passage.",
            lines: [{ n: 1, text: "Synthetic reading passage.", page: 1 }],
            pages: [2],
            question_numbers: [1],
          },
        ],
        questions: [
          q({
            number: 1,
            passage: "I",
            stem: "Reading stem",
            choices: [
              { letter: "A", text: "one" },
              { letter: "B", text: "two" },
              { letter: "C", text: "three" },
              { letter: "D", text: "four" },
            ],
            text_fidelity: "ok",
            answer: "C",
            reporting_category: "KID",
          }),
        ],
        scoring: {
          raw_max: 1,
          category_totals: { KID: 1 },
          scale_conversion: { "1": 36, "0": 1 },
        },
      }),
      section({
        code: "science",
        title: "SCIENCE TEST",
        minutes: 40,
        question_count: 2,
        declared_question_count: 2,
        passages: [
          {
            label: "I",
            title: null,
            intro: "Figures adapted from a synthetic source.",
            text: "See Figure 1 and Table 1.",
            lines: null,
            pages: [3],
            question_numbers: [1, 2],
            is_figure: true,
          },
        ],
        questions: [
          q({
            number: 1,
            passage: "I",
            stem: "Science stem one",
            choices: [
              { letter: "A", text: "up" },
              { letter: "B", text: "down" },
              { letter: "C", text: "left" },
              { letter: "D", text: "right" },
            ],
            text_fidelity: "ok",
            answer: "D",
            reporting_category: "IOD",
            image: "synth-pt/questions/science-q01.png",
          }),
          q({
            number: 2,
            passage: "I",
            stem: "Science stem two",
            choices: [
              { letter: "F", text: "yes" },
              { letter: "G", text: "no" },
              { letter: "H", text: "maybe" },
              { letter: "J", text: "skip" },
            ],
            text_fidelity: "low",
            answer: "F",
            reporting_category: "SIN",
            image: "synth-pt/questions/science-q02.png",
          }),
        ],
        scoring: {
          raw_max: 2,
          category_totals: { IOD: 1, SIN: 1 },
          scale_conversion: { "2": 36, "1": 20, "0": 1 },
        },
      }),
    ],
  });
}

describe("parseOfficialForm mapping (A-2 / FR-P2-2, FR-P2-17)", () => {
  it("emits four asset-served sections with text, images, scale, and normalized keys", () => {
    const { clientForm, keys } = parseOfficialForm(fourSectionSource());
    expect(() => ClientExamForm.parse(clientForm)).not.toThrow();
    expect(clientForm.delivery).toBe("asset-served");
    expect(clientForm.blueprint).toBe("act-enhanced");
    expect(clientForm.composite_sections).toEqual([
      "english",
      "math",
      "reading",
    ]);
    expect(clientForm.sections.map((s) => s.code)).toEqual([
      "english",
      "math",
      "reading",
      "science",
    ]);

    const [eng, math, reading, science] = clientForm.sections;
    expect(eng!.questions).toHaveLength(2);
    expect(eng!.questions[0]!.stem).toBe("English stem one");
    expect(eng!.questions[0]!.choices.map((c) => c.letter)).toEqual([
      "A",
      "B",
      "C",
      "D",
    ]);
    expect(eng!.questions[0]!.choices[0]!.is_no_change).toBe(true);
    expect(eng!.questions[1]!.choices.map((c) => c.letter)).toEqual([
      "A",
      "B",
      "C",
      "D",
    ]);
    expect(eng!.questions[0]!.reporting_category).toBe("KLA");
    expect(eng!.questions[1]!.scored).toBe(false);
    expect(eng!.questions[0]!.passage).toBe("I");
    expect(eng!.questions.every((q) => q.image === null)).toBe(true);
    expect(eng!.passages[0]).toMatchObject({
      label: "I",
      title: "A Synthetic Passage",
      text: "Synthetic english passage text.",
      question_numbers: [1, 2],
      image: null,
    });
    expect(eng!.scale_table).toEqual({ "1": 36, "0": 1 });
    expect(eng!.composite).toBe(true);
    expect(science!.composite).toBe(false);

    expect(math!.questions[0]!.image).toBeNull();
    expect(math!.questions[1]!.image).toEqual({
      store: "form-image",
      form_id: "synth-pt",
      key: "questions/math-q02.png",
    });
    expect(reading!.questions[0]!.image).toBeNull();
    expect(science!.passages[0]!.image).toEqual({
      store: "form-image",
      form_id: "synth-pt",
      key: "pages/p003.png",
    });
    expect(science!.questions[0]!.image).not.toBeNull();
    expect(science!.questions[1]!.image).not.toBeNull();

    for (const q of clientForm.sections.flatMap((s) => s.questions)) {
      expect(q).not.toHaveProperty("answer_letter");
      expect(q).not.toHaveProperty("per_choice_rationale");
      expect(q).not.toHaveProperty("why_correct_md");
      expect(q).not.toHaveProperty("why_tempted_md");
    }

    const evenEng = keys["synth-pt-english-2"];
    expect(evenEng).toEqual({
      answer_letter: "C",
      booklet_letter: "H",
      section: "english",
      number: 2,
    });
    expect(keys["synth-pt-math-2"]!.answer_letter).toBe("D");
    expect(keys["synth-pt-math-2"]!.booklet_letter).toBe("J");
    expect(keys["synth-pt-science-2"]!.answer_letter).toBe("A");
    expect(keys["synth-pt-science-2"]!.booklet_letter).toBe("F");
  });

  it("sets composite_sections to all four for preact-secure-legacy", () => {
    const { clientForm } = parseOfficialForm(
      officialJson({ blueprint: "preact-secure-legacy" }),
    );
    expect(clientForm.composite_sections).toEqual([
      "english",
      "math",
      "reading",
      "science",
    ]);
    expect(clientForm.sections[0]!.composite).toBe(true);
  });

  it("emits store-relative AssetRef keys (CV4-1 / FR-P2-14)", () => {
    const { clientForm } = parseOfficialForm(fourSectionSource());
    const formId = clientForm.id;
    const questionImages = clientForm.sections.flatMap((s) =>
      s.questions.map((q) => q.image).filter((img) => img != null),
    );
    const passageImages = clientForm.sections.flatMap((s) =>
      s.passages.map((p) => p.image).filter((img) => img != null),
    );
    expect(questionImages.length).toBeGreaterThan(0);
    expect(passageImages.length).toBeGreaterThan(0);
    for (const img of [...questionImages, ...passageImages]) {
      expect(img.key.startsWith(`${formId}/`)).toBe(false);
      expect(img.form_id).toBe(formId);
    }
    for (const img of questionImages) {
      expect(img.key).toMatch(/^questions\//);
    }
    for (const img of passageImages) {
      expect(img.key).toMatch(/^pages\//);
    }
  });

  it("fallback image key is store-relative when JSON image is absent (CV4-1)", () => {
    const { clientForm } = parseOfficialForm(
      officialJson({
        form_id: "synth-pt",
        sections: [
          section({
            code: "math",
            title: "MATHEMATICS TEST",
            question_count: 1,
            declared_question_count: 1,
            passages: [],
            questions: [
              q({
                number: 2,
                stem: "notation item without image field",
                choices: [
                  { letter: "A", text: "1" },
                  { letter: "B", text: "2" },
                  { letter: "C", text: "3" },
                  { letter: "D", text: "4" },
                ],
                text_fidelity: "math-notation",
                answer: "A",
                reporting_category: "F",
                image: null,
              }),
            ],
            scoring: {
              raw_max: 1,
              category_totals: { F: 1 },
              scale_conversion: { "1": 36, "0": 1 },
            },
          }),
        ],
      }),
    );
    expect(clientForm.sections[0]!.questions[0]!.image).toEqual({
      store: "form-image",
      form_id: "synth-pt",
      key: "questions/math-q02.png",
    });
  });

  it("store-relative keys resolve at the official disk layout and encode as one route segment (CV4-3)", async () => {
    const { clientForm } = parseOfficialForm(fourSectionSource());
    const baseDir = mkdtempSync(join(tmpdir(), "exam-serve-"));
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47]);
    const refs = [
      ...clientForm.sections.flatMap((s) =>
        s.questions.map((q) => q.image).filter((img) => img != null),
      ),
      ...clientForm.sections.flatMap((s) =>
        s.passages.map((p) => p.image).filter((img) => img != null),
      ),
    ];
    expect(refs.length).toBeGreaterThan(0);
    for (const img of refs) {
      const dest = join(baseDir, img.form_id, img.key);
      mkdirSync(dirname(dest), { recursive: true });
      writeFileSync(dest, png);
    }
    const store = new LocalFileAssetStore(baseDir);
    const misses: string[] = [];
    for (const img of refs) {
      if (!(await store.has(img))) misses.push(img.key);
      const url = assetRefToUrl(img);
      const keySegment = url.split("/").pop()!;
      expect(keySegment).toBe(encodeURIComponent(img.key));
      expect(keySegment).not.toContain("/");
      expect(decodeURIComponent(keySegment)).toBe(img.key);
    }
    expect(misses).toEqual([]);
  });
});

function pdfScoringKeys(): Record<string, Record<string, string>> {
  const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(EXTRACT_TOOLS)})
from extract_forms import FORMS, locate_sections, parse_keys
import fitz
doc = fitz.open(${JSON.stringify(PT2_PDF)})
sections = locate_sections(doc)
keys = parse_keys(doc, FORMS["act-practice-test-2"]["key_style"], sections[-1]["end"] + 1)
print(json.dumps({code: {str(n): L for n, L in block["answers"].items()} for code, block in keys.items()}))
`;
  const proc = spawnSync(VENV_PYTHON, ["-c", py], { encoding: "utf8" });
  if (proc.status !== 0) {
    throw new Error(`PT2 key extract failed: ${proc.stderr || proc.stdout}`);
  }
  return JSON.parse(proc.stdout) as Record<string, Record<string, string>>;
}

describe.skipIf(!PT2_AVAILABLE)(
  "parseOfficialForm local PT2 (A-2 / FR-P2-2, FR-P2-17)",
  () => {
    it("matches PT2 counts, scored totals, image rule, and PDF scoring-key page", () => {
      const raw = JSON.parse(readFileSync(PT2_JSON, "utf8")) as unknown;
      const { clientForm, keys } = parseOfficialForm(raw);
      expect(clientForm.id).toBe("act-practice-test-2");
      expect(clientForm.delivery).toBe("asset-served");
      expect(clientForm.composite_sections).toEqual([
        "english",
        "math",
        "reading",
      ]);
      const byCode = Object.fromEntries(
        clientForm.sections.map((s) => [s.code, s]),
      );
      expect(byCode.english!.questions).toHaveLength(50);
      expect(byCode.math!.questions).toHaveLength(45);
      expect(byCode.reading!.questions).toHaveLength(36);
      expect(byCode.science!.questions).toHaveLength(40);
      expect(byCode.english!.questions.filter((q) => q.scored).length).toBe(40);
      expect(byCode.math!.questions.filter((q) => q.scored).length).toBe(41);
      expect(byCode.reading!.questions.filter((q) => q.scored).length).toBe(27);
      expect(byCode.science!.questions.filter((q) => q.scored).length).toBe(34);
      expect(byCode.english!.questions.filter((q) => q.image).length).toBe(0);
      expect(byCode.reading!.questions.filter((q) => q.image).length).toBe(0);
      expect(byCode.math!.questions.filter((q) => q.image).length).toBe(34);
      expect(byCode.science!.questions.some((q) => q.image !== null)).toBe(true);
      expect(byCode.english!.scale_table).not.toBeNull();
      expect(byCode.english!.scale_table!["40"]).toBe(36);
      expect(byCode.english!.scale_table!["0"]).toBe(1);

      const official = pdfScoringKeys();
      const mismatches: string[] = [];
      for (const section of clientForm.sections) {
        for (const q of section.questions) {
          const entry = keys[q.id];
          const want = official[section.code]?.[String(entry!.number)];
          if (want === undefined || entry!.booklet_letter !== want) {
            mismatches.push(
              `${section.code} Q${entry!.number}: converter=${entry?.booklet_letter} pdf=${want}`,
            );
          }
        }
      }
      expect(mismatches, mismatches.join("\n")).toEqual([]);
    });

    it("Math 34/34 + Science images resolve store→VM (CV4-3 / FR-P2-11/13/19)", async () => {
      const raw = JSON.parse(readFileSync(PT2_JSON, "utf8")) as unknown;
      const { clientForm } = parseOfficialForm(raw);
      const store = new LocalFileAssetStore(join(PRIVATE_SRC, "json"));
      const byCode = Object.fromEntries(
        clientForm.sections.map((s) => [s.code, s]),
      );
      const mathImages = byCode.math!.questions
        .map((q) => q.image)
        .filter((img) => img != null);
      const scienceQuestionImages = byCode.science!.questions
        .map((q) => q.image)
        .filter((img) => img != null);
      const sciencePassageImages = byCode.science!.passages
        .map((p) => p.image)
        .filter((img) => img != null);
      expect(mathImages).toHaveLength(34);
      expect(scienceQuestionImages.length).toBeGreaterThan(0);
      expect(sciencePassageImages.length).toBeGreaterThan(0);

      const misses: string[] = [];
      for (const img of [
        ...mathImages,
        ...scienceQuestionImages,
        ...sciencePassageImages,
      ]) {
        if (!(await store.has(img))) misses.push(img.key);
        const url = assetRefToUrl(img);
        const keySegment = url.split("/").pop()!;
        expect(keySegment).toBe(encodeURIComponent(img.key));
        expect(keySegment).not.toContain("/");
        expect(decodeURIComponent(keySegment)).toBe(img.key);
      }
      expect(misses, misses.join("\n")).toEqual([]);
    });
  },
);

const ANSWER_FIELDS = [
  "answer_letter",
  "per_choice_rationale",
  "why_correct_md",
  "why_tempted_md",
] as const;

function parseExportedObject(src: string, name: string): unknown {
  const marker = `export const ${name}`;
  const at = src.indexOf(marker);
  if (at < 0) throw new Error(`export ${name} not found`);
  const start = src.indexOf("{", at);
  if (start < 0) throw new Error(`export ${name} has no object literal`);
  return JSON.parse(src.slice(start).replace(/;\s*$/, ""));
}

describe("convertOfficialForm emit (A-3 / FR-P2-3, FR-P2-4)", () => {
  it("writes a ClientExamForm.strict() client artifact with zero answer-bearing fields", () => {
    const src = writeSrcTree(fourSectionSource());
    const outDir = mkdtempSync(join(tmpdir(), "official-form-out-"));
    const { clientPath, keysPath } = convertOfficialForm({
      srcDir: src,
      formId: "synth-pt",
      outDir,
    });
    expect(clientPath).toBe(join(outDir, "synth-pt.client.ts"));
    expect(keysPath).toBe(join(outDir, "synth-pt.keys.ts"));
    const clientSrc = readFileSync(clientPath, "utf8");
    const keysSrc = readFileSync(keysPath, "utf8");
    const form = parseExportedObject(clientSrc, "CLIENT_EXAM_FORM");
    const parsed = ClientExamForm.parse(form);
    expect(parsed.delivery).toBe("asset-served");
    for (const field of ANSWER_FIELDS) {
      expect(clientSrc).not.toContain(field);
      for (const q of parsed.sections.flatMap((s) => s.questions)) {
        expect(q).not.toHaveProperty(field);
      }
    }
    const keys = parseExportedObject(keysSrc, "FORM_KEYS") as Record<
      string,
      { booklet_letter: string }
    >;
    expect(keys["synth-pt-english-2"]!.booklet_letter).toBe("H");
  });

  it("registers convert:official as a tsx script with no new dependency", () => {
    const pkg = JSON.parse(
      readFileSync(resolve(HERE, "../package.json"), "utf8"),
    ) as {
      scripts: Record<string, string>;
      dependencies?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };
    expect(pkg.scripts["convert:official"]).toBe(
      "tsx scripts/convert_official_form.ts",
    );
    expect(pkg.dependencies?.["tsx"]).toBeUndefined();
  });

  it("git-ignores both generated artifact paths (FR-P2-4)", () => {
    const repo = resolve(HERE, "../..");
    const client =
      "frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.client.ts";
    const keys =
      "frontend/lib/adapters/engine/exam_forms/_generated/act-practice-test-2.keys.ts";
    const proc = spawnSync("git", ["check-ignore", client, keys], {
      cwd: repo,
      encoding: "utf8",
    });
    expect(proc.status).toBe(0);
    expect(proc.stdout).toContain(client);
    expect(proc.stdout).toContain(keys);
  });
});
