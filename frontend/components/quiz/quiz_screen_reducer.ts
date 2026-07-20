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
 *
 * Commit-first coaching (`commitFirstCoach` on `submitted`, FR-1…14): a wrong
 * submit stays in `answering` with a `coachedLoop` sub-state (rungs 1–3);
 * resolution lands on `reviewing` with `resolution` ∈ {first_try, coached,
 * walked_through}. Flag OFF (omit/`false`) preserves the legacy instant-review
 * transitions byte-for-byte.
 */

import type {
  AttemptResolution,
  Verdict,
} from "@/lib/wire/engine_entities";
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
 *
 * Under commit-first (FR-11), `correct` counts only `first_try` resolutions;
 * wrong submits that stay in the coached loop do not bump the tally until the
 * item resolves.
 */
export type SessionTally = {
  readonly correct: number;
  readonly total: number;
};

/** Per-item coached-loop sub-state while answering under commit-first (FR-3…7). */
export type CoachedLoopState = {
  /** Wrong letters submitted this item, in order (incl. repeats suppressed). */
  readonly wrongLetters: readonly string[];
  /** Letter whose ladder is currently active (last wrong submit). */
  readonly activeLetter: string | null;
  /** Rungs revealed per wrong letter (1–rungCap). */
  readonly rungsRevealed: Readonly<Record<string, number>>;
  /** True when the active letter has all rungCap rungs revealed (FR-5). */
  readonly exhausted: boolean;
  /**
   * Honest ladder length for this wrong letter (1–3). FR-8 single-rung
   * fallbacks set 1 so empty "Show me more" clicks never appear.
   */
  readonly rungCap: number;
};

/**
 * FR-15: in-place confirmation after a coached solve. Learner opts into the
 * feedback view via `see_breakdown` — feedback does not auto-render.
 */
export type CoachedConfirmState = {
  readonly correctLetter: string;
  readonly answeredLetter: string;
  readonly whySummary: string;
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
  /**
   * Commit-first wrong-pick loop. `null` until the first wrong submit with
   * `commitFirstCoach: true` (FR-3). Cleared on a fresh `item_loaded`.
   */
  readonly coachedLoop: CoachedLoopState | null;
  /**
   * FR-15 coached-solve confirmation. Set when the learner submits the correct
   * letter after entering the loop; cleared on `item_loaded` / `see_breakdown`.
   */
  readonly coachedConfirm: CoachedConfirmState | null;
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
  /**
   * Commit-first outcome (FR-9/10). Undefined under flag OFF (legacy path).
   */
  readonly resolution?: AttemptResolution;
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
        resolution?: AttemptResolution;
      };
    }
  | { type: "select"; letter: string }
  | { type: "toggle_hint" }
  /** ADR-0035: swap in a choice-conditional ladder without resetting selection. */
  | {
      type: "ladder_loaded";
      hintLadder: QuizItemResult["hintLadder"];
      /**
       * G8 race guard: the letter this ladder was loaded for. When the active
       * wrong letter has since switched (L1→L2), a stale L1 load is ignored so
       * the rung bodies shown always match `coachedLoop.activeLetter`. Omit for
       * the legacy non-commit-first path (no active letter to guard against).
       */
      forLetter?: string | null;
    }
  | {
      type: "submitted";
      verdict: Verdict | null;
      letter: string | null;
      /** When true, wrong submits enter the coached loop (FR-3); omit/false = legacy. */
      commitFirstCoach?: boolean;
      /** Ladder length for this wrong letter (1–3); defaults to 3. */
      rungCap?: number;
    }
  /** Reveal the next ladder rung for the active wrong letter (FR-4). */
  | { type: "nudge_requested" }
  /** Clear the pick after exhaustion; retain rung counts (FR-5). */
  | { type: "try_again" }
  /** Priced escape → walked_through resolution (FR-6). */
  | { type: "escape_taken" }
  /** FR-15: learner-initiated route from coached confirm → feedback view. */
  | { type: "see_breakdown" }
  | { type: "next" }
  | { type: "finish" }
  /** Q-8: End session — distinct from `finish` (FR-Q8-6); page routes to /learn. */
  | { type: "end_session" };

const ZERO_TALLY: SessionTally = { correct: 0, total: 0 };
const RUNG_CAP = 3;

function freshAnswering(
  item: QuizItemResult,
  score: SessionTally,
  presentedAt: number,
): AnsweringPhase {
  return {
    phase: "answering",
    item,
    selectedLetter: null,
    hintOpen: false,
    usedHint: false,
    presentedAt,
    score,
    coachedLoop: null,
    coachedConfirm: null,
  };
}

function clampRungCap(n: number | undefined): number {
  if (n == null || !Number.isFinite(n)) return RUNG_CAP;
  return Math.min(RUNG_CAP, Math.max(1, Math.floor(n)));
}

function withRungs(
  loop: CoachedLoopState,
  letter: string,
  rungs: number,
  rungCap: number = loop.rungCap,
): CoachedLoopState {
  const cap = clampRungCap(rungCap);
  const capped = Math.min(cap, Math.max(1, rungs));
  return {
    ...loop,
    activeLetter: letter,
    rungCap: cap,
    rungsRevealed: { ...loop.rungsRevealed, [letter]: capped },
    exhausted: capped >= cap,
  };
}

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
      return freshAnswering(
        action.item,
        state.score,
        action.presentedAt ?? Number.NaN,
      );

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
          ...(action.feedback.resolution != null
            ? { resolution: action.feedback.resolution }
            : {}),
        };
      }
      return freshAnswering(
        action.item,
        action.score,
        action.presentedAt ?? Number.NaN,
      );

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
      // Moment-router reload (ADR-0035): keep phase/selection; only the ladder
      // body changes (wrong-letter Gen2 pack or back to item-level).
      if (state.phase !== "answering" && state.phase !== "reviewing") {
        return state;
      }
      // G8 race guard: ignore a stale load whose letter no longer matches the
      // active wrong letter (a slow L1 load arriving after a switch to L2).
      // The page's effect-cleanup cancellation is the first line of defense;
      // this guard is the reducer-level backstop so the bodies shown always
      // match `coachedLoop.activeLetter`. `forLetter` null/omit = legacy path.
      if (
        state.phase === "answering" &&
        state.coachedLoop != null &&
        action.forLetter != null &&
        state.coachedLoop.activeLetter != null &&
        action.forLetter !== state.coachedLoop.activeLetter
      ) {
        return state;
      }
      if (state.phase === "answering" && state.coachedLoop != null) {
        const letter = state.coachedLoop.activeLetter;
        const cap = clampRungCap(action.hintLadder.length);
        const revealed =
          letter != null
            ? (state.coachedLoop.rungsRevealed[letter] ?? 1)
            : 1;
        return {
          ...state,
          item: { ...state.item, hintLadder: action.hintLadder },
          coachedLoop: withRungs(state.coachedLoop, letter ?? "?", revealed, cap),
        };
      }
      return {
        ...state,
        item: { ...state.item, hintLadder: action.hintLadder },
      };

    case "submitted": {
      if (state.phase !== "answering") return state;
      // FR-D2a: a no-selection submit produces no verdict — stay on the question
      // AND leave the tally untouched (nothing was answered).
      if (action.verdict == null || action.letter == null) return state;

      const commitFirst = action.commitFirstCoach === true;

      // Commit-first wrong path: stay answering, enter/advance coached loop (FR-3).
      if (commitFirst && !action.verdict.correct) {
        const letter = action.letter;
        const prev = state.coachedLoop;
        // Same-letter resubmit is inert (FR-7) — no state change, no tally bump.
        if (prev != null && prev.activeLetter === letter) {
          return state;
        }
        const rungCap = clampRungCap(action.rungCap);
        const base: CoachedLoopState = prev ?? {
          wrongLetters: [],
          activeLetter: null,
          rungsRevealed: {},
          exhausted: false,
          rungCap,
        };
        const wrongLetters = base.wrongLetters.includes(letter)
          ? base.wrongLetters
          : [...base.wrongLetters, letter];
        // Fresh letter starts at rung 1; retained rungs for other letters stay.
        // Letter switch adopts this letter's ladder length (FR-7 / FR-8).
        const nextLoop = withRungs(
          { ...base, wrongLetters },
          letter,
          1,
          rungCap,
        );
        return {
          ...state,
          coachedLoop: nextLoop,
          // Sticky: a wrong-pick loop means coaching was engaged for this item.
          usedHint: true,
        };
      }

      // Resolve path: correct (any flag) or wrong under flag OFF.
      const hadWrongAttempts =
        state.coachedLoop != null && state.coachedLoop.wrongLetters.length > 0;
      const resolution: AttemptResolution | undefined = commitFirst
        ? action.verdict.correct
          ? hadWrongAttempts
            ? "coached"
            : "first_try"
          : undefined
        : undefined;

      // FR-11: under commit-first, only first_try bumps correct; legacy counts
      // every correct submit.
      const bumpCorrect = commitFirst
        ? resolution === "first_try"
        : action.verdict.correct;

      const nextScore = {
        correct: state.score.correct + (bumpCorrect ? 1 : 0),
        total: state.score.total + 1,
      };

      // FR-15: coached solve confirms in place — no auto feedback render.
      if (commitFirst && resolution === "coached") {
        const correctLetter =
          action.verdict.correct_letter ?? state.item.question.answer_letter;
        return {
          ...state,
          selectedLetter: action.letter,
          coachedLoop: null,
          coachedConfirm: {
            correctLetter,
            answeredLetter: action.letter,
            whySummary: state.item.question.why_correct_md.trim(),
          },
          usedHint: true,
          score: nextScore,
        };
      }

      return {
        phase: "reviewing",
        item: state.item,
        verdict: action.verdict,
        answeredLetter: action.letter,
        usedHint: state.usedHint,
        score: nextScore,
        ...(resolution != null ? { resolution } : {}),
      };
    }

    case "nudge_requested": {
      if (state.phase !== "answering" || state.coachedLoop == null) return state;
      const letter = state.coachedLoop.activeLetter;
      if (letter == null || state.coachedLoop.exhausted) return state;
      const current = state.coachedLoop.rungsRevealed[letter] ?? 1;
      return {
        ...state,
        coachedLoop: withRungs(state.coachedLoop, letter, current + 1),
      };
    }

    case "try_again": {
      if (state.phase !== "answering" || state.coachedLoop == null) return state;
      // Clear the pick; retain per-letter rung counts (FR-5).
      return { ...state, selectedLetter: null };
    }

    case "escape_taken": {
      if (state.phase !== "answering" || state.coachedLoop == null) return state;
      const lastWrong =
        state.coachedLoop.activeLetter ??
        state.coachedLoop.wrongLetters[state.coachedLoop.wrongLetters.length - 1];
      if (lastWrong == null) return state;
      // FR-6: resolve as walked_through; honest wrong verdict; last wrong letter.
      return {
        phase: "reviewing",
        item: state.item,
        verdict: { correct: false, correct_letter: state.item.question.answer_letter },
        answeredLetter: lastWrong,
        usedHint: state.usedHint,
        score: {
          correct: state.score.correct,
          total: state.score.total + 1,
        },
        resolution: "walked_through",
      };
    }

    case "see_breakdown": {
      if (state.phase !== "answering" || state.coachedConfirm == null) {
        return state;
      }
      const confirm = state.coachedConfirm;
      return {
        phase: "reviewing",
        item: state.item,
        verdict: {
          correct: true,
          correct_letter: confirm.correctLetter,
        },
        answeredLetter: confirm.answeredLetter,
        usedHint: state.usedHint,
        score: state.score,
        resolution: "coached",
      };
    }

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
