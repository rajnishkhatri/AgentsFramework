/**
 * quiz_screen_reducer — the Quiz screen's phase machine (Phase 1.4, FR-D/E).
 *
 * The Quiz page walks a small state machine:
 *   loading → answering → reviewing → (Next → loading | Finish → done)
 * Per F-R1 the page component holds none of this transition logic — it lives
 * here as a pure, React-free reducer so every phase invariant is node-testable
 * with no DOM (the analogue of the `openQuizItem`/`runQuizSubmit` split in
 * use_quiz.ts). The async port calls stay in the page (they are effects); the
 * reducer only folds their *results* — a loaded item, a graded verdict — into
 * the next phase.
 *
 * Two invariants are structural here, not left to the component:
 *   - A no-selection submit (verdict null, FR-D2a) does NOT advance: the learner
 *     stays on the question.
 *   - `usedHint` is sticky per item (FR-D5 accounting): once a hint is opened it
 *     stays true for that item even after the hint is closed, so the recorded
 *     attempt reflects that a hint was consulted.
 */

import type { Verdict } from "@/lib/wire/engine_entities";
import type { QuizItemResult } from "./use_quiz";

interface LoadingPhase {
  readonly phase: "loading";
}

interface AnsweringPhase {
  readonly phase: "answering";
  readonly item: QuizItemResult;
  readonly selectedLetter: string | null;
  readonly hintOpen: boolean;
  /** Sticky once true for this item (FR-D5 attempt accounting). */
  readonly usedHint: boolean;
}

interface ReviewingPhase {
  readonly phase: "reviewing";
  readonly item: QuizItemResult;
  /** The graded verdict (never null in this phase — see the reducer). */
  readonly verdict: Verdict;
  /** The letter the learner submitted (drives the Feedback per-choice styling). */
  readonly answeredLetter: string;
  readonly usedHint: boolean;
}

interface DonePhase {
  readonly phase: "done";
}

export type QuizScreenState =
  | LoadingPhase
  | AnsweringPhase
  | ReviewingPhase
  | DonePhase;

export type QuizScreenAction =
  | { type: "item_loaded"; item: QuizItemResult }
  | { type: "select"; letter: string }
  | { type: "toggle_hint" }
  | { type: "submitted"; verdict: Verdict | null; letter: string | null }
  | { type: "next" }
  | { type: "finish" };

export const initialQuizScreen: QuizScreenState = { phase: "loading" };

export function quizScreenReducer(
  state: QuizScreenState,
  action: QuizScreenAction,
): QuizScreenState {
  switch (action.type) {
    case "item_loaded":
      // A freshly scheduled item always opens a clean answering slate.
      return {
        phase: "answering",
        item: action.item,
        selectedLetter: null,
        hintOpen: false,
        usedHint: false,
      };

    case "select":
      if (state.phase !== "answering") return state;
      return { ...state, selectedLetter: action.letter };

    case "toggle_hint":
      if (state.phase !== "answering") return state;
      return {
        ...state,
        hintOpen: !state.hintOpen,
        // usedHint is sticky: opening it once marks the item hinted for good.
        usedHint: state.usedHint || !state.hintOpen,
      };

    case "submitted":
      if (state.phase !== "answering") return state;
      // FR-D2a: a no-selection submit produces no verdict — stay on the question.
      if (action.verdict == null || action.letter == null) return state;
      return {
        phase: "reviewing",
        item: state.item,
        verdict: action.verdict,
        answeredLetter: action.letter,
        usedHint: state.usedHint,
      };

    case "next":
      if (state.phase !== "reviewing") return state;
      // Back to loading; the page fetches the next scheduled item.
      return { phase: "loading" };

    case "finish":
      if (state.phase !== "reviewing") return state;
      return { phase: "done" };

    default:
      return state;
  }
}
