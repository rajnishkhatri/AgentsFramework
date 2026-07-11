/**
 * L1 tests for ExactLetterGrader (engine spec §8 grader.spec rows).
 *
 * The grader is pure/deterministic, so these are pure input→output tables with
 * no mocks. Failure path first (TAP-4): no selected letter → null (FR-D2a),
 * BEFORE the correctness paths.
 *
 * Maps the engine spec named L1 tests + the §8.1 traceability rows:
 *   - grader.spec::no_selected_letter_produces_no_verdict_and_no_attempt (FR-D2a)
 *   - grader.spec::exact_letter_match_is_pure_and_deterministic (FR-C1/C2)
 *   - grader.spec::wrong_pick_yields_both_distractor_and_correct_rationale (FR-C3)
 *   - grader.spec::correct_pick_sets_celebrate (FR-C3a)
 * and the prototype-test contracts it reproduces (desktop english-coach.spec.js):
 *   - correct pick (A — NO CHANGE) → "Exactly right." + "Why A is correct"
 *   - wrong pick (B) → "Why B tempted you" AND "Why A is correct"
 */

import { describe, expect, it } from "vitest";
import { ExactLetterGrader } from "./exact_letter_grader";
import type { Answer, Question } from "../../../wire/engine_entities";

function question(over: Partial<Question> = {}): Question {
  return {
    id: "q1",
    subject: "act-english",
    skill_id: "s1",
    difficulty: 3,
    context_html: "The committee <u>have</u> decided.",
    stem: "Which choice is best?",
    choices: [
      { letter: "A", label: "NO CHANGE", is_no_change: true },
      { letter: "B", label: "has", is_no_change: false },
      { letter: "C", label: "having", is_no_change: false },
      { letter: "D", label: "had", is_no_change: false },
    ],
    answer_letter: "B",
    per_choice_rationale: {
      A: "Why A tempted you: 'committee' reads as plural here, but it is a singular collective noun.",
      B: "Why B is correct: a singular collective noun takes a singular verb.",
    },
    why_correct_md: "Singular collective noun → singular verb.",
    why_tempted_md: "'committee' sounds plural.",
    rule_md: "Collective nouns are singular.",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

const grader = new ExactLetterGrader();

describe("ExactLetterGrader — failure path first (FR-D2a)", () => {
  it("no selected letter produces no verdict (and therefore no attempt)", () => {
    const answer: Answer = { letter: null };
    expect(grader.grade(question(), answer)).toBeNull();
  });
});

describe("ExactLetterGrader — correctness + rationale handles", () => {
  it("exact letter match is pure and deterministic (FR-C1/C2)", () => {
    const q = question({ answer_letter: "B" });
    const a: Answer = { letter: "B" };
    const first = grader.grade(q, a);
    const second = grader.grade(q, a);
    expect(first).toEqual(second); // deterministic
    expect(first).toEqual({
      correct: true,
      correct_letter: "B",
      rationale_key: "B",
    });
  });

  it("correct pick sets celebrate state: correct=true + correct_letter (FR-C3a)", () => {
    // The prototype's "correct pick (A — NO CHANGE)" case → answer_letter A.
    const q = question({ answer_letter: "A" });
    const verdict = grader.grade(q, { letter: "A" });
    expect(verdict).not.toBeNull();
    expect(verdict!.correct).toBe(true);
    expect(verdict!.correct_letter).toBe("A"); // drives "Why A is correct"
    expect(verdict!.rationale_key).toBe("A"); // celebrate → same letter
  });

  it("wrong pick yields BOTH distractor and correct rationale handles (FR-C3)", () => {
    // answer is B; learner picks the wrong A. The verdict must expose the
    // distractor rationale (rationale_key = chosen 'A' → "Why A tempted you")
    // AND the correct rationale (correct_letter = 'B' → "Why B is correct").
    const q = question({ answer_letter: "B" });
    const verdict = grader.grade(q, { letter: "A" });
    expect(verdict).not.toBeNull();
    expect(verdict!.correct).toBe(false);
    expect(verdict!.rationale_key).toBe("A"); // distractor (the chosen wrong letter)
    expect(verdict!.correct_letter).toBe("B"); // the correct answer
    // Both rationale strings are reachable from these two handles:
    expect(q.per_choice_rationale[verdict!.rationale_key!]).toContain("tempted");
    expect(q.per_choice_rationale[verdict!.correct_letter!]).toContain("correct");
  });

  it("omits canonical_answer for English (FR-C4)", () => {
    const verdict = grader.grade(question(), { letter: "B" });
    expect(verdict).not.toBeNull();
    expect(verdict!.canonical_answer).toBeUndefined();
  });
});
