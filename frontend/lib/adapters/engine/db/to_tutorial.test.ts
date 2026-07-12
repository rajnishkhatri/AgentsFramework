/**
 * E1a FR-8b — toTutorial round-trip: a raw row with teaching fields maps equal.
 * Failure-first: teaching fields absent from the mapper → undefined (red).
 */

import { describe, expect, it } from "vitest";

import { toTutorial } from "./drizzle_engine_db";

const BASE_ROW = {
  id: "tut-1",
  subject: "act-english",
  skill_id: "s-nec",
  body_md: "Fence non-essential clauses with a pair of commas.",
  examples: ["My car, which is electric, is quiet."],
  generated_from: "hand:author@2026-07-11",
  reviewed: true,
};

const TEACHING = {
  ground_md: "You already know list commas.",
  pitfall_md: "Deleting commas to shorten.",
  question_md: "When does a clause need a pair?",
  self_explain_prompt: "Why do both commas stay?",
  worked_example: {
    sentence: "My kitchen, which provides an alternative to eating out, is small.",
    steps: ["Remove.", "Still complete.", "Fence."],
    answer: "Keep both commas.",
  },
  completion_try: {
    sentence: "The teacher, who grades fairly, is popular.",
    choices: [
      { text: "Keep both commas", correct: true },
      { text: "Delete the commas", correct: false },
    ],
    why: "Remove the clause → still stands.",
  },
  annotated_examples: [
    {
      pre: "My kitchen",
      clause: "which provides an alternative to eating out",
      post: " is small.",
      essential: false,
      callouts: ["remove it → still works"],
    },
  ],
};

describe("toTutorial — E1a FR-8b", () => {
  it("maps a row without teaching fields (fields absent, not null)", () => {
    const t = toTutorial(BASE_ROW);
    expect(t.ground_md).toBeUndefined();
    expect(t.worked_example).toBeUndefined();
    expect(t.completion_try).toBeUndefined();
    expect(t.annotated_examples).toBeUndefined();
  });

  it("round-trips teaching fields equal to the seeded row", () => {
    const t = toTutorial({ ...BASE_ROW, ...TEACHING });
    expect(t.ground_md).toBe(TEACHING.ground_md);
    expect(t.pitfall_md).toBe(TEACHING.pitfall_md);
    expect(t.question_md).toBe(TEACHING.question_md);
    expect(t.self_explain_prompt).toBe(TEACHING.self_explain_prompt);
    expect(t.worked_example).toEqual(TEACHING.worked_example);
    expect(t.completion_try).toEqual(TEACHING.completion_try);
    expect(t.annotated_examples).toEqual(TEACHING.annotated_examples);
  });

  it("treats SQL null teaching columns as absent (undefined)", () => {
    const t = toTutorial({
      ...BASE_ROW,
      ground_md: null,
      worked_example: null,
      completion_try: null,
      annotated_examples: null,
    });
    expect(t.ground_md).toBeUndefined();
    expect(t.worked_example).toBeUndefined();
    expect(t.completion_try).toBeUndefined();
    expect(t.annotated_examples).toBeUndefined();
  });
});
