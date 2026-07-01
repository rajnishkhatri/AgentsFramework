/**
 * Phase 1.5 — Feedback orchestration (FR-E1..E5, L1 deterministic).
 *
 * Feedback is a Quiz sub-state (plan §OD-5): after `runQuizSubmit` returns a
 * Verdict, this seam composes the FeedbackVM + the two action routes
 * ("Ask the coach" with the item in context, FR-E5; "Next question →"). Per
 * F-R1 the component holds none of this.
 *
 * Failure/edge first: a null verdict (no selection reached feedback — a caller
 * bug) yields `present:false` so the screen shows nothing rather than crashing.
 */

import { describe, expect, it } from "vitest";
import { buildFeedback } from "./use_feedback";
import type { Answer, Question, Verdict } from "@/lib/wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: { A: "A is correct.", B: "B tempted you." },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "Collective nouns are singular.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("buildFeedback — edge first", () => {
  it("null verdict (no selection reached feedback) → present:false", () => {
    const fb = buildFeedback(question(), null, { letter: null });
    expect(fb.present).toBe(false);
  });
});

describe("buildFeedback — happy path (FR-E1..E5)", () => {
  const verdict: Verdict = { correct: false, correct_letter: "A", rationale_key: "B" };
  const answer: Answer = { letter: "B" };
  const fb = buildFeedback(question(), verdict, answer);

  it("carries the composed FeedbackVM (soft banner + distractor rationale)", () => {
    if (!fb.present) throw new Error("expected feedback present");
    expect(fb.vm.banner).toBe("soft");
    expect(fb.vm.chosenRationale).toContain("B tempted you");
  });

  it("the Ask-the-coach action carries the item id in context (FR-E5)", () => {
    if (!fb.present) throw new Error("expected feedback present");
    expect(fb.askCoachContext.questionId).toBe("q1");
    expect(fb.askCoachContext.skillId).toBe("s-punc");
  });
});
