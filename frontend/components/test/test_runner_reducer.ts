/**
 * test_runner_reducer — the timed Test-Mode phase machine (F-R1, pure/React-free).
 *
 * Test Mode is a FIXED timed section (decoupled from the adaptive `/learn/quiz`
 * drip): the learner walks a known list of questions, may revisit and change
 * answers, then submits the whole section at once — or the countdown forces a
 * `submit_section` at zero. This reducer owns all that transition logic so the
 * page component holds none (the analogue of `quiz_screen_reducer`). It shares
 * NOTHING with the quiz: no scheduler, no session, no attempt — grading happens
 * once, at submit, via an injected pure `GradeFn` (the engine `Grader`).
 *
 * The answers map persists across next/prev (revisit is a first-class Test-Mode
 * feature, unlike the one-shot adaptive quiz). Grading treats an unanswered item
 * as incorrect, and is idempotent (a second submit re-grades the same map to the
 * same tally).
 *
 * Import rule: `wire/` shapes only. No React, no SDK, no clock (the clock lives in
 * use_countdown; this reducer only folds its RESULT — a `submit_section` — in).
 */

import type { Question } from "@/lib/wire/engine_entities";

/** Injected pure grader: true iff `letter` is the correct answer for `question`. */
export type GradeFn = (question: Question, letter: string | null) => boolean;

/** `{ [questionId]: chosenLetter | undefined }` — undefined = unanswered. */
export type AnswersMap = Readonly<Record<string, string>>;

interface IntroPhase {
  readonly phase: "intro";
  readonly questions: readonly Question[];
}

interface InSectionPhase {
  readonly phase: "in_section";
  readonly questions: readonly Question[];
  readonly index: number;
  readonly answers: AnswersMap;
}

interface ResultsPhase {
  readonly phase: "results";
  readonly questions: readonly Question[];
  readonly answers: AnswersMap;
  readonly correct: number;
  readonly total: number;
}

export type TestRunnerState = IntroPhase | InSectionPhase | ResultsPhase;

export type TestRunnerAction =
  | { type: "start" }
  | { type: "select"; letter: string }
  | { type: "next" }
  | { type: "prev" }
  | { type: "submit_section"; grade: GradeFn };

export function initialTestRunner(questions: readonly Question[]): TestRunnerState {
  return { phase: "intro", questions };
}

function clamp(i: number, count: number): number {
  if (i < 0) return 0;
  if (i > count - 1) return count - 1;
  return i;
}

function gradeAll(
  questions: readonly Question[],
  answers: AnswersMap,
  grade: GradeFn,
): { correct: number; total: number } {
  let correct = 0;
  for (const q of questions) {
    const letter = answers[q.id] ?? null;
    if (grade(q, letter)) correct += 1;
  }
  return { correct, total: questions.length };
}

export function testRunnerReducer(
  state: TestRunnerState,
  action: TestRunnerAction,
): TestRunnerState {
  switch (action.type) {
    case "start":
      if (state.phase !== "intro") return state;
      return { phase: "in_section", questions: state.questions, index: 0, answers: {} };

    case "select": {
      if (state.phase !== "in_section") return state;
      const current = state.questions[state.index];
      if (current == null) return state;
      return {
        ...state,
        answers: { ...state.answers, [current.id]: action.letter },
      };
    }

    case "next":
      if (state.phase !== "in_section") return state;
      return { ...state, index: clamp(state.index + 1, state.questions.length) };

    case "prev":
      if (state.phase !== "in_section") return state;
      return { ...state, index: clamp(state.index - 1, state.questions.length) };

    case "submit_section": {
      // Grade the whole section at once (manual submit OR timer-forced expiry —
      // the page dispatches the same action either way). Idempotent: re-grading
      // the same answers map yields the same tally.
      if (state.phase === "results") {
        const { correct, total } = gradeAll(state.questions, state.answers, action.grade);
        return { ...state, correct, total };
      }
      if (state.phase !== "in_section") return state;
      const { correct, total } = gradeAll(state.questions, state.answers, action.grade);
      return {
        phase: "results",
        questions: state.questions,
        answers: state.answers,
        correct,
        total,
      };
    }

    default:
      return state;
  }
}
