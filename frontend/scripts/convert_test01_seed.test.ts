/**
 * L1 tests for the Test-01 seed demotion (Phase 6, ADR-0015, FR-25).
 *
 * The converter keeps its oracle-tested parser + the frozen serving corpus; a
 * SEPARATE seed-emission maps parsed questions to neutral governed-bank seed
 * rows. Failure path FIRST (TAP-4): a self-stamped `reviewed:true` question is
 * DEMOTED to `reviewed=false` on entry, asserted before the shape checks.
 *
 * `_test01_english_corpus.ts` is NOT read here — this pins the demotion, not
 * the frozen fixture (FR-25.3's byte-lock lives with the corpus itself). Pure,
 * no file I/O.
 */

import { describe, expect, it } from "vitest";
import { toTestItemSeed } from "./convert_test01_seed";
import { TestItem } from "../lib/wire/engine_entities";
import type { Question } from "../lib/wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "t01-eng-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "The team <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
      { letter: "C", label: "having", is_no_change: false },
      { letter: "D", label: "had", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "…", B: "…" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    // The converter self-stamps these — the seed must retroactively unearn them.
    reviewed: true,
    generated_by: "test01-convert",
  };
}

describe("toTestItemSeed — demotion first (FR-25.1)", () => {
  it("demotes a self-stamped reviewed:true question to reviewed=false", () => {
    const seed = toTestItemSeed([question({ reviewed: true })]);
    expect(seed[0]!.reviewed).toBe(false);
  });

  it("stamps provenance test01-import (FR-25.2)", () => {
    const seed = toTestItemSeed([question()]);
    expect(seed[0]!.generated_by).toBe("test01-import");
  });
});

describe("toTestItemSeed — shape", () => {
  it("emits rows that parse under the Zod TestItem schema", () => {
    const seed = toTestItemSeed([question()]);
    for (const row of seed) {
      expect(() => TestItem.parse(row)).not.toThrow();
    }
  });

  it("carries the parsed stem, choices, and declared key for re-verification", () => {
    const seed = toTestItemSeed([question()]);
    const row = seed[0]!;
    expect(row.stem_md).toBe("Which choice is best?");
    expect(row.answer_letter).toBe("B");
    expect(row.choices.map((c) => c.letter)).toEqual(["A", "B", "C", "D"]);
    expect(row.skill_id).toBe("s-gram");
  });
});
