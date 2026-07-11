/**
 * L1 tests for the on-device engine wire entities (ADR-0005/0006).
 *
 * Sprint S3 (`preact-quiz-target-count.spec.md`): the bounded-session
 * `target_count` field on `QuizSession`. Failure paths first (TAP-4): the
 * invalid-target rejections are asserted BEFORE the happy-path parse.
 *
 * `target_count` is `z.number().int().positive().nullable()`:
 *   - null      → endless session (backward-compatible; FR-2/FR-3)
 *   - a value   → that many items this session (FR-4)
 *   - ≤0, non-int, NaN → rejected at parse (FR-1)
 *
 * Sprint C2 (`preact-parity-C2-summary-payoff.spec.md`): nullable
 * `misconception` on `Question` / `TestItem` (FR-9 / FR-10, ADR-0027).
 */

import { describe, expect, it } from "vitest";
import { Question, QuizSession, TestItem } from "./engine_entities";

function session(over: Record<string, unknown> = {}) {
  return {
    id: "qs-1",
    subject: "act-english",
    learner_id: "learner-1",
    mode: "drill",
    skill_focus: "s-gram",
    started_at: "2026-07-08T00:00:00.000Z",
    ended_at: null,
    score_correct: 0,
    score_total: 0,
    target_count: 30,
    ...over,
  };
}

function validQuestion(over: Record<string, unknown> = {}) {
  return {
    id: "q-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "<p>The committee <u>were</u> unanimous.</p>",
    stem: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "was", is_no_change: false },
      { letter: "C", label: "have been", is_no_change: false },
      { letter: "D", label: "being", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "a", B: "b", C: "c", D: "d" },
    why_correct_md: "singular",
    why_tempted_md: "plural people",
    rule_md: "collective nouns",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test@run1",
    ...over,
  };
}

function validTestItem(over: Record<string, unknown> = {}) {
  return {
    id: "ti-1",
    subject: "act-english",
    skill_id: "s-gram",
    difficulty: 3,
    context_html: "<p>The committee <u>were</u> unanimous.</p>",
    stem_md: "Which choice best fixes the underlined portion?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "was", is_no_change: false },
      { letter: "C", label: "have been", is_no_change: false },
      { letter: "D", label: "being", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: { A: "a", B: "b", C: "c", D: "d" },
    why_correct_md: "singular",
    why_tempted_md: "plural people",
    rule_md: "collective nouns",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test@run1",
    ...over,
  };
}

describe("QuizSession.target_count — failure paths first (FR-1)", () => {
  it("rejects a zero target_count", () => {
    expect(QuizSession.safeParse(session({ target_count: 0 })).success).toBe(false);
  });

  it("rejects a negative target_count", () => {
    expect(QuizSession.safeParse(session({ target_count: -1 })).success).toBe(false);
  });

  it("rejects a non-integer target_count", () => {
    expect(QuizSession.safeParse(session({ target_count: 2.5 })).success).toBe(false);
  });

  it("rejects a NaN target_count", () => {
    expect(QuizSession.safeParse(session({ target_count: Number.NaN })).success).toBe(false);
  });
});

describe("QuizSession.target_count — accepted shapes (FR-2/FR-4)", () => {
  it("parses a positive integer target_count (FR-4)", () => {
    const parsed = QuizSession.parse(session({ target_count: 30 }));
    expect(parsed.target_count).toBe(30);
  });

  it("accepts an explicit null = endless session (FR-2)", () => {
    const parsed = QuizSession.parse(session({ target_count: null }));
    expect(parsed.target_count).toBeNull();
  });
});

describe("Question.misconception — C2 FR-9 (ADR-0027)", () => {
  it("accepts misconception: null", () => {
    expect(Question.safeParse(validQuestion({ misconception: null })).success).toBe(true);
  });

  it("accepts misconception: string", () => {
    expect(
      Question.safeParse(validQuestion({ misconception: "some string" })).success,
    ).toBe(true);
  });

  it("rejects misconception: 42", () => {
    expect(Question.safeParse(validQuestion({ misconception: 42 })).success).toBe(false);
  });
});

describe("TestItem.misconception — C2 FR-10 (ADR-0027)", () => {
  it("accepts misconception: null", () => {
    expect(TestItem.safeParse(validTestItem({ misconception: null })).success).toBe(true);
  });

  it("accepts misconception: string", () => {
    expect(
      TestItem.safeParse(validTestItem({ misconception: "some string" })).success,
    ).toBe(true);
  });

  it("rejects misconception: 42", () => {
    expect(TestItem.safeParse(validTestItem({ misconception: 42 })).success).toBe(false);
  });
});
