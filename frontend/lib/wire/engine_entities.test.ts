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
import {
  Attempt,
  AttemptInput,
  Question,
  QuizSession,
  TestItem,
  Tutorial,
} from "./engine_entities";
import type { Tutorial as TutorialT } from "./engine_entities";

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

// --- Tutorial teaching fields (E1a / ADR-0028 / FR-8a) --------------------

function validTutorial(over: Record<string, unknown> = {}) {
  return {
    id: "tut-1",
    subject: "act-english",
    skill_id: "s-nec",
    body_md: "A non-essential clause must be fenced by a pair of commas.",
    examples: ["My car, which is electric, is quiet."],
    generated_from: "hand:author@2026-07-11",
    reviewed: true,
    ...over,
  };
}

// --- Attempt.resolution (commit-first coach / FR-10) ----------------------

function validAttempt(over: Record<string, unknown> = {}) {
  return {
    id: "a-1",
    subject: "act-english",
    session_id: "sess-1",
    question_id: "q-1",
    chosen_letter: "B",
    correct: false,
    elapsed_ms: 1200,
    used_hint: false,
    created_at: "2026-07-19T00:00:00.000Z",
    ...over,
  };
}

describe("Attempt.resolution — commit-first FR-10 (additive nullable)", () => {
  it("accepts omitting resolution (legacy single-attempt rows)", () => {
    const parsed = Attempt.parse(validAttempt());
    expect(parsed.resolution).toBeUndefined();
  });

  it("accepts resolution: null (legacy readable)", () => {
    const parsed = Attempt.parse(validAttempt({ resolution: null }));
    expect(parsed.resolution).toBeNull();
  });

  it("round-trips each resolution enum value", () => {
    for (const resolution of ["first_try", "coached", "walked_through"] as const) {
      const parsed = Attempt.parse(validAttempt({ resolution }));
      expect(parsed.resolution).toBe(resolution);
    }
  });

  it("rejects an unknown resolution string", () => {
    expect(
      Attempt.safeParse(validAttempt({ resolution: "solved" })).success,
    ).toBe(false);
  });

  it("AttemptInput accepts resolution and omits id/created_at", () => {
    const input = AttemptInput.parse({
      subject: "act-english",
      session_id: "sess-1",
      question_id: "q-1",
      chosen_letter: "A",
      correct: true,
      elapsed_ms: 500,
      used_hint: false,
      resolution: "first_try",
    });
    expect(input.resolution).toBe("first_try");
    expect("id" in input).toBe(false);
    expect("created_at" in input).toBe(false);
  });
});

describe("Tutorial teaching fields — E1a FR-8a (ADR-0028)", () => {
  it("accepts a row without teaching fields (all optional)", () => {
    const parsed = Tutorial.parse(validTutorial());
    expect(parsed.ground_md).toBeUndefined();
    expect(parsed.pitfall_md).toBeUndefined();
    expect(parsed.question_md).toBeUndefined();
    expect(parsed.self_explain_prompt).toBeUndefined();
    expect(parsed.worked_example).toBeUndefined();
    expect(parsed.completion_try).toBeUndefined();
    expect(parsed.annotated_examples).toBeUndefined();
  });

  it("accepts a row with all teaching fields", () => {
    const parsed = Tutorial.parse(
      validTutorial({
        ground_md: "You already know commas separate items in a list.",
        pitfall_md: "Deleting commas to shorten a sentence.",
        question_md: "When does a clause need a pair of commas?",
        self_explain_prompt: "Why do both commas stay?",
        worked_example: {
          sentence: "My kitchen, which provides an alternative to eating out, is small.",
          steps: ["Remove the clause.", "Still complete → non-essential.", "Fence with commas."],
          answer: "Keep both commas.",
        },
        completion_try: {
          sentence: "The teacher, who grades fairly, is popular.",
          choices: [
            { text: "Keep both commas", correct: true },
            { text: "Delete the commas", correct: false },
          ],
          why: "Remove the clause → the sentence still stands.",
        },
        annotated_examples: [
          {
            pre: "My kitchen",
            clause: "which provides an alternative to eating out",
            post: " is small.",
            essential: false,
            callouts: ["remove it → still works", "so → fence with commas"],
          },
        ],
      }),
    );
    expect(parsed.ground_md).toBe("You already know commas separate items in a list.");
    expect(parsed.worked_example?.answer).toBe("Keep both commas.");
    expect(parsed.completion_try?.choices[0]?.correct).toBe(true);
    expect(parsed.annotated_examples?.[0]?.essential).toBe(false);
  });

  it("does not declare blocks/zone/role on the inferred type (FR-8a)", () => {
    // Compile-time: forbidden keys must not appear on Tutorial.
    type Forbidden = "blocks" | "zone" | "role" | "context" | "beats";
    type HasForbidden = Extract<keyof TutorialT, Forbidden>;
    type AssertNever<T> = [T] extends [never] ? true : false;
    const ok: AssertNever<HasForbidden> = true;
    expect(ok).toBe(true);
    const row = Tutorial.parse(validTutorial());
    expect(
      Object.prototype.hasOwnProperty.call(row, "blocks") ||
        Object.prototype.hasOwnProperty.call(row, "zone") ||
        Object.prototype.hasOwnProperty.call(row, "role"),
    ).toBe(false);
  });
});
