/**
 * feedback_vm — (Question, Verdict, Answer) → FeedbackVM (FR-E1..E5).
 *
 * Pure T1 map for the post-answer teaching screen (the core teaching moment).
 * It composes the ALREADY-COMPUTED grading `Verdict` (from the Grader — grading
 * never happens here) with the question's per-choice rationale into the view:
 *
 *   - banner: "celebrate" (FR-E2) when correct, "soft" (FR-E3) when wrong;
 *   - chosenRationale: THAT distractor's specific rationale (FR-E3) — never a
 *     generic message; correctRationale: the answer rationale (FR-E1);
 *   - reviewedChoices: each choice tagged with its per-state style
 *     (correct / chosen-wrong / other) for FR-E4;
 *   - ruleMd: the rule under test (FR-E1).
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type { Answer, Question, Verdict } from "../wire/engine_entities";

export type FeedbackBanner = "celebrate" | "soft";

/** Per-choice review styling state (FR-E4). */
export type ReviewedChoiceState = "correct" | "chosen-wrong" | "other";

export interface ReviewedChoiceVM {
  readonly letter: string;
  readonly label: string;
  readonly state: ReviewedChoiceState;
}

export interface FeedbackVM {
  readonly correct: boolean;
  readonly banner: FeedbackBanner;
  readonly chosenLetter: string | null;
  readonly correctLetter: string | null;
  /** Rationale for the learner's chosen letter (FR-E3 distractor-specific / FR-E2). */
  readonly chosenRationale: string;
  /** Rationale for the correct letter — "Why A is correct" (FR-E1). */
  readonly correctRationale: string;
  readonly reviewedChoices: ReadonlyArray<ReviewedChoiceVM>;
  readonly ruleMd: string;
}

function stateFor(
  letter: string,
  correctLetter: string | null,
  chosenLetter: string | null,
): ReviewedChoiceState {
  if (letter === correctLetter) return "correct";
  if (letter === chosenLetter) return "chosen-wrong";
  return "other";
}

export function toFeedbackVM(
  question: Question,
  verdict: Verdict,
  answer: Answer,
): FeedbackVM {
  const chosenLetter = answer.letter;
  const correctLetter = verdict.correct_letter ?? question.answer_letter;
  const rationale = question.per_choice_rationale;

  return {
    correct: verdict.correct,
    banner: verdict.correct ? "celebrate" : "soft",
    chosenLetter,
    correctLetter,
    chosenRationale: (chosenLetter && rationale[chosenLetter]) || "",
    correctRationale: rationale[correctLetter] ?? "",
    reviewedChoices: question.choices.map((c) => ({
      letter: c.letter,
      label: c.label,
      // A correct learner's chosen row IS the correct row → "correct" wins
      // (stateFor checks correctLetter first), matching FR-E4.
      state: stateFor(c.letter, correctLetter, chosenLetter),
    })),
    ruleMd: question.rule_md,
  };
}
