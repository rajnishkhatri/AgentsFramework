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

/**
 * Whole-millisecond elapsed between an item's `presentedAt` clock start and a
 * submit-time reading, for the D0 real-timing fix (`attempt.elapsed_ms`, replacing
 * the old hardcoded 0). Both readings come from the monotonic `performance.now()`.
 * Pure and clock-free so the page's timing is node-testable with fixed inputs.
 *
 *   - Non-negative floor: a wall-clock adjustment mid-answering can never yield a
 *     negative value (FR-5); `now < presentedAt` clamps to 0.
 *   - Missing start (`undefined` or non-finite `NaN`): a defensive 0, never
 *     NaN/negative (FR-2). This `!Number.isFinite` guard is the SINGLE authority on
 *     "no clock captured" — the reducer stores NaN (not 0) for a clock-less
 *     item_loaded so a miss reaches this guard instead of being laundered into a
 *     finite 0 (which would return `now`, a fabricated elapsed). Degenerate
 *     fallback, not a fabricated reading — the universal stub is gone.
 *   - Rounded to whole ms; a sub-ms delta is an honest 0.
 */
export function elapsedMsFrom(presentedAt: number | undefined, now: number): number {
  if (presentedAt == null || !Number.isFinite(presentedAt)) return 0;
  return Math.max(0, Math.round(now - presentedAt));
}

/**
 * The running session tally (FR-D3). Every graded submit increments `total`; a
 * correct one also increments `correct`. It rides on EVERY phase so it survives
 * the loading↔answering↔reviewing cycle across a multi-item walk, and is read at
 * Finish to close the session with the stored score the Summary displays
 * (`sessionRepo.close`). A `type`, not an `interface`, so the one-interface-per-
 * file discipline of the phase objects is unaffected.
 */
export type SessionTally = {
  readonly correct: number;
  readonly total: number;
};

interface LoadingPhase {
  readonly phase: "loading";
  readonly score: SessionTally;
}

interface AnsweringPhase {
  readonly phase: "answering";
  readonly item: QuizItemResult;
  readonly selectedLetter: string | null;
  readonly hintOpen: boolean;
  /** Sticky once true for this item (FR-D5 attempt accounting). */
  readonly usedHint: boolean;
  /**
   * Monotonic clock reading (`performance.now()`) captured when THIS item was
   * presented, i.e. on the `item_loaded` transition (D0 elapsed timing). The page
   * subtracts it from the submit-time reading via `elapsedMsFrom` to record a real
   * `attempt.elapsed_ms` instead of the old hardcoded 0. Per-item: a fresh
   * `item_loaded` after Next stamps a new value (never cumulative across the walk).
   */
  readonly presentedAt: number;
  readonly score: SessionTally;
}

interface ReviewingPhase {
  readonly phase: "reviewing";
  readonly item: QuizItemResult;
  /** The graded verdict (never null in this phase — see the reducer). */
  readonly verdict: Verdict;
  /** The letter the learner submitted (drives the Feedback per-choice styling). */
  readonly answeredLetter: string;
  readonly usedHint: boolean;
  readonly score: SessionTally;
}

interface DonePhase {
  readonly phase: "done";
  readonly score: SessionTally;
}

export type QuizScreenState =
  | LoadingPhase
  | AnsweringPhase
  | ReviewingPhase
  | DonePhase;

export type QuizScreenAction =
  // `presentedAt` is the monotonic clock reading at item-present time (D0 elapsed
  // timing). The page supplies `performance.now()`; the reducer stores it as data
  // and never reads a clock itself (deterministic, node-testable). Optional so the
  // transition-only tests that don't care about timing can omit it (defaults to 0).
  | { type: "item_loaded"; item: QuizItemResult; presentedAt?: number }
  // FLAG-4 resume: restore a stashed item + running tally without openSession /
  // a fresh item_loaded (FR-3). Score is required so resume never fabricates 0/0.
  // When `feedback` is set, restore reviewing (left from Feedback) so progress
  // stays on Question N and the learner can tap Next themselves.
  | {
      type: "resume_item";
      item: QuizItemResult;
      score: SessionTally;
      presentedAt?: number;
      feedback?: {
        verdict: Verdict;
        answeredLetter: string;
        usedHint: boolean;
      };
    }
  | { type: "select"; letter: string }
  | { type: "toggle_hint" }
  /** ADR-0031: swap in a choice-conditional ladder without resetting selection. */
  | { type: "ladder_loaded"; hintLadder: QuizItemResult["hintLadder"] }
  | { type: "submitted"; verdict: Verdict | null; letter: string | null }
  | { type: "next" }
  | { type: "finish" }
  /** Q-8: End session — distinct from `finish` (FR-Q8-6); page routes to /learn. */
  | { type: "end_session" };

const ZERO_TALLY: SessionTally = { correct: 0, total: 0 };

export const initialQuizScreen: QuizScreenState = {
  phase: "loading",
  score: ZERO_TALLY,
};

export function quizScreenReducer(
  state: QuizScreenState,
  action: QuizScreenAction,
): QuizScreenState {
  switch (action.type) {
    case "item_loaded":
      // A freshly scheduled item always opens a clean answering slate — but the
      // running tally carries over from the prior item(s). `presentedAt` stamps the
      // per-item clock start (D0 elapsed timing); a fresh item_loaded after Next
      // resets it, so timing is per-item and never cumulative across the walk.
      // A dispatch that omits the clock reading (transition-only tests) stores NaN,
      // NOT 0: `elapsedMsFrom`'s `!Number.isFinite` guard is the single authority on
      // "no start captured" and returns 0 for it. Laundering the miss into a finite 0
      // would defeat that guard — `elapsedMsFrom(0, now)` = now = a fabricated
      // multi-million-ms elapsed, the exact D0 bug class.
      return {
        phase: "answering",
        item: action.item,
        selectedLetter: null,
        hintOpen: false,
        usedHint: false,
        presentedAt: action.presentedAt ?? Number.NaN,
        score: state.score,
      };

    case "resume_item":
      // Coach ← Back remount: restore the left item + stashed tally.
      // Left from Feedback → reviewing (same N, Next available; no re-submit).
      // Left from answering → clean answering slate.
      if (action.feedback != null) {
        return {
          phase: "reviewing",
          item: action.item,
          verdict: action.feedback.verdict,
          answeredLetter: action.feedback.answeredLetter,
          usedHint: action.feedback.usedHint,
          score: action.score,
        };
      }
      return {
        phase: "answering",
        item: action.item,
        selectedLetter: null,
        hintOpen: false,
        usedHint: false,
        presentedAt: action.presentedAt ?? Number.NaN,
        score: action.score,
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

    case "ladder_loaded":
      // Moment-router reload (ADR-0031): keep phase/selection; only the ladder
      // body changes (wrong-letter Gen2 pack or back to item-level).
      if (state.phase !== "answering" && state.phase !== "reviewing") {
        return state;
      }
      return {
        ...state,
        item: { ...state.item, hintLadder: action.hintLadder },
      };

    case "submitted":
      if (state.phase !== "answering") return state;
      // FR-D2a: a no-selection submit produces no verdict — stay on the question
      // AND leave the tally untouched (nothing was answered).
      if (action.verdict == null || action.letter == null) return state;
      return {
        phase: "reviewing",
        item: state.item,
        verdict: action.verdict,
        answeredLetter: action.letter,
        usedHint: state.usedHint,
        score: {
          correct: state.score.correct + (action.verdict.correct ? 1 : 0),
          total: state.score.total + 1,
        },
      };

    case "next":
      if (state.phase !== "reviewing") return state;
      // Back to loading; the page fetches the next scheduled item. Tally carries.
      return { phase: "loading", score: state.score };

    case "finish":
      if (state.phase !== "reviewing") return state;
      // The final tally rides to `done` so the page closes the session with it.
      return { phase: "done", score: state.score };

    case "end_session":
      // Q-8: actionable from answering OR reviewing (FR-Q8-3); no-op from
      // loading/done (FR-Q8-1/2). Converges on `done` like finish — the page
      // callback owns the route target (/learn vs /learn/summary).
      if (state.phase !== "answering" && state.phase !== "reviewing") {
        return state;
      }
      return { phase: "done", score: state.score };

    default:
      return state;
  }
}
