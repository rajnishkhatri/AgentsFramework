/**
 * Converter test (TDD) — Test-01.md English section → engine Question[] + key.
 *
 * The converter is a build-time, offline parser (not app runtime): it turns the
 * hand-authored ACT practice markdown into the vendor-neutral `Question` shape
 * the Test-Mode runner consumes, plus a `{ questionId: letter }` answer-key map
 * that doubles as a GRADING ORACLE (every parsed `answer_letter` must equal the
 * official key). These tests pin the parse contract against the real Test-01.md.
 *
 * Pure functions only — `parseTest01English(md)` takes the markdown string and
 * returns `{ questions, answerKey }`; no file I/O here (that lives in the script's
 * thin `main()`), so this is node-testable with a `readFileSync` of the source.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { parseTest01English } from "./convert_test01_english";
import { Question } from "../lib/wire/engine_entities";

const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(HERE, "../../PreAct/practice-tests/Test-01.md");
const MD = readFileSync(SOURCE, "utf8");

describe("parseTest01English", () => {
  const { questions, answerKey } = parseTest01English(MD);

  it("extracts all 48 English questions", () => {
    expect(questions).toHaveLength(48);
  });

  it("every question validates against the engine Question schema", () => {
    for (const q of questions) {
      expect(() => Question.parse(q)).not.toThrow();
    }
  });

  it("normalizes every choice set to internal A–D letters", () => {
    for (const q of questions) {
      expect(q.choices.map((c) => c.letter)).toEqual(["A", "B", "C", "D"]);
    }
  });

  it("answer key covers all 48 questions and every answer is A–D", () => {
    expect(Object.keys(answerKey)).toHaveLength(48);
    for (const letter of Object.values(answerKey)) {
      expect(["A", "B", "C", "D"]).toContain(letter);
    }
  });

  it("ORACLE: each question's answer_letter equals its official-key letter", () => {
    for (const q of questions) {
      expect(q.answer_letter).toBe(answerKey[q.id]);
    }
  });

  it("maps every question onto one of the six engine skill buckets", () => {
    const SKILLS = new Set([
      "s-punc",
      "s-gram",
      "s-sent",
      "s-rhet",
      "s-org",
      "s-style",
    ]);
    for (const q of questions) {
      expect(SKILLS.has(q.skill_id)).toBe(true);
    }
  });

  it("marks NO CHANGE as choice A (is_no_change) where present", () => {
    // Q1 answer is B ("taught"); its A choice is the NO CHANGE option.
    const q1 = questions.find((q) => q.id === "t01-eng-1")!;
    expect(q1).toBeDefined();
    expect(q1.choices[0]!.is_no_change).toBe(true);
    expect(q1.answer_letter).toBe("B");
  });

  it("carries provenance + reviewed gate so it is learner-eligible", () => {
    for (const q of questions) {
      expect(q.reviewed).toBe(true);
      expect(q.generated_by).toBe("test01-convert");
      expect(q.item_type).toBe("underlined-span-mc");
      expect(q.subject).toBe("act-english");
    }
  });

  it("renders passage context as HTML underlines, not raw markdown markers", () => {
    // Q1 lives in the "Learning to Sail" passage whose first span is **teached**[1].
    const q1 = questions.find((q) => q.id === "t01-eng-1")!;
    // The underlined span is real HTML…
    expect(q1.context_html).toContain("<u>teached</u>");
    // …the *Osprey* title is emphasis…
    expect(q1.context_html).toContain("<em>Osprey</em>");
    // …and no raw markdown / bare sentence markers survive.
    expect(q1.context_html).not.toContain("**");
    expect(q1.context_html).not.toMatch(/\[\d+\]/);
  });

  it("gives ★ ceiling items a higher difficulty than plain items", () => {
    // Q6 is a ★ item; Q1 is not. Difficulty must reflect that spread.
    const q6 = questions.find((q) => q.id === "t01-eng-6")!;
    const q1 = questions.find((q) => q.id === "t01-eng-1")!;
    expect(q6.difficulty).toBeGreaterThan(q1.difficulty);
  });
});
