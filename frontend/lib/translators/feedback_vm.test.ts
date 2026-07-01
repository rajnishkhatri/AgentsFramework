/**
 * Phase 0.5 — feedback_vm (FR-E1..E5, L2 contract, TAP-2 table-driven).
 *
 * Pure map: (Question, Verdict, Answer) → FeedbackVM for the post-answer
 * teaching screen. The named failure row runs FIRST (plan §Phase 0.5): a WRONG
 * pick (FR-E3) must surface the soft banner AND *that distractor's* specific
 * rationale, plus the correct-answer rationale — never a generic message.
 *
 * Then the correct-pick celebrate path (FR-E2), the per-choice review styling
 * states (FR-E4), and the rule under test (FR-E1).
 */

import { describe, expect, it } from "vitest";
import { toFeedbackVM } from "./feedback_vm";
import type { Answer, Question, Verdict } from "../wire/engine_entities";

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
      { letter: "C", label: "having", is_no_change: false },
      { letter: "D", label: "had", is_no_change: false },
    ],
    answer_letter: "A",
    per_choice_rationale: {
      A: "A is correct: singular collective noun → singular verb.",
      B: "B tempted you: 'committee' sounds plural but is singular.",
      C: "C is a participle, not a finite verb.",
      D: "D shifts the tense wrongly.",
    },
    why_correct_md: "Singular collective noun → singular verb.",
    why_tempted_md: "'committee' sounds plural.",
    rule_md: "Collective nouns are singular.",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

describe("toFeedbackVM — wrong pick (FR-E3, failure path first)", () => {
  const q = question({ answer_letter: "A" });
  const verdict: Verdict = { correct: false, correct_letter: "A", rationale_key: "B" };
  const answer: Answer = { letter: "B" };

  it("shows the soft (not-quite) banner, not the celebrate banner", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.correct).toBe(false);
    expect(vm.banner).toBe("soft");
  });

  it("surfaces THAT distractor's specific rationale (B), plus the correct one (A)", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.chosenRationale).toContain("B tempted you");
    expect(vm.correctRationale).toContain("A is correct");
  });

  it("marks the chosen letter and the correct letter", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.chosenLetter).toBe("B");
    expect(vm.correctLetter).toBe("A");
  });
});

describe("toFeedbackVM — correct pick (FR-E2 celebrate)", () => {
  const q = question({ answer_letter: "A" });
  const verdict: Verdict = { correct: true, correct_letter: "A", rationale_key: "A" };
  const answer: Answer = { letter: "A" };

  it("shows the celebrate banner", () => {
    const vm = toFeedbackVM(q, verdict, answer);
    expect(vm.correct).toBe(true);
    expect(vm.banner).toBe("celebrate");
  });
});

describe("toFeedbackVM — per-choice review states (FR-E4) + rule (FR-E1)", () => {
  const q = question({ answer_letter: "A" });
  const verdict: Verdict = { correct: false, correct_letter: "A", rationale_key: "B" };
  const answer: Answer = { letter: "B" };
  const vm = toFeedbackVM(q, verdict, answer);

  it("styles the correct choice as 'correct', the chosen-wrong as 'chosen-wrong', others 'other'", () => {
    const byLetter = Object.fromEntries(vm.reviewedChoices.map((c) => [c.letter, c.state]));
    expect(byLetter.A).toBe("correct");
    expect(byLetter.B).toBe("chosen-wrong");
    expect(byLetter.C).toBe("other");
    expect(byLetter.D).toBe("other");
  });

  it("carries the rule under test (FR-E1)", () => {
    expect(vm.ruleMd).toBe("Collective nouns are singular.");
  });

  it("when the learner is correct, the chosen row is styled 'correct' (not chosen-wrong)", () => {
    const cq = question({ answer_letter: "A" });
    const cVm = toFeedbackVM(cq, { correct: true, correct_letter: "A", rationale_key: "A" }, { letter: "A" });
    const a = cVm.reviewedChoices.find((c) => c.letter === "A");
    expect(a?.state).toBe("correct");
  });
});
