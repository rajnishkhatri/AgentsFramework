/**
 * ExactLetterGrader — the English `Grader` adapter (ADR-0006 #6).
 *
 * Pure, deterministic, verifier-first (engine spec FR-C1/C2): English grading is
 * an exact letter match between the learner's chosen letter and the question's
 * `answer_letter`. No I/O, no clock, no SDK — this adapter imports nothing but
 * the port + wire shapes, so it is trivially L1-testable and reusable as the
 * generation self-consistency gate (FR-E2).
 *
 * It is the React-OCP twin of the renderer registry: a future Math subject ships
 * a NEW grader adapter implementing the SAME `Grader` interface (symbolic
 * canonicalization), and this file is never edited (FR-H1).
 *
 * `Verdict` shape produced:
 *   - correct:        chosen letter === answer_letter
 *   - correct_letter: always the question's answer_letter (drives "Why X is correct")
 *   - rationale_key:  the chosen letter (FR-C3 — points at the per-choice rationale;
 *                     for a wrong pick this is the distractor rationale, for a
 *                     correct pick it equals correct_letter → FR-C3a celebrate)
 *   - canonical_answer: omitted for English (reserved for a symbolic grader, FR-C4)
 *
 * No SDK confinement concern: this adapter has no vendor dependency. It lives
 * under `adapters/` because it is a concrete port implementation, not because it
 * wraps an SDK.
 */

import type { Grader } from "../../../ports/engine/grader";
import type {
  Answer,
  Question,
  Verdict,
} from "../../../wire/engine_entities";

export class ExactLetterGrader implements Grader {
  /**
   * Grade by exact letter match. Returns `null` when no letter is selected
   * (FR-D2a: no selection ⇒ no Verdict ⇒ caller records no attempt). A non-null
   * letter always yields a deterministic `Verdict`.
   */
  grade(question: Question, answer: Answer): Verdict | null {
    const chosen = answer.letter;
    if (chosen === null) {
      // FR-D2a — nothing selected: no verdict, no attempt, no feedback.
      return null;
    }

    const correct = chosen === question.answer_letter;
    return {
      correct,
      correct_letter: question.answer_letter,
      // FR-C3 / FR-C3a: the rationale to surface is the one for the CHOSEN
      // letter. Wrong pick → the distractor rationale ("Why B tempted you");
      // correct pick → equals correct_letter ("Why A is correct").
      rationale_key: chosen,
      // canonical_answer intentionally omitted for English (FR-C4).
    };
  }
}
