/**
 * Phase 1.4 — Quiz screen phase reducer (FR-D/E, L1 deterministic).
 *
 * The Quiz *screen* is a small state machine over the orchestration in use_quiz:
 *   loading → answering → reviewing → (Next → answering | Finish → done)
 * Per F-R1 the page component holds none of that transition logic — it lives in
 * this pure, React-free reducer, so the phase invariants are node-testable with
 * no DOM. The async port calls stay in the page (they're effects); the reducer
 * only folds their *results* into the next screen phase.
 *
 * Edge/failure first: a graded no-selection submit (verdict null, FR-D2a) must
 * NOT advance to review — the learner stays on the question.
 */

import { describe, expect, it } from "vitest";
import type { Question, Verdict } from "@/lib/wire/engine_entities";
import {
  quizScreenReducer,
  initialQuizScreen,
  elapsedMsFrom,
  type QuizScreenState,
} from "./quiz_screen_reducer";

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
    answer_letter: "B",
    per_choice_rationale: { A: "…", B: "…" },
    why_correct_md: "…",
    why_tempted_md: "…",
    rule_md: "…",
    item_type: "underlined-span-mc",
    misconception: null,
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

function verdict(correct: boolean): Verdict {
  return { correct, correct_letter: "B" };
}

const item = { skillId: "s-punc", question: question(), hintLadder: [] };

describe("quiz_screen_reducer — initial + item load", () => {
  it("starts in loading with no item", () => {
    expect(initialQuizScreen.phase).toBe("loading");
  });

  it("item_loaded moves to answering with the question and a cleared selection", () => {
    const s = quizScreenReducer(initialQuizScreen, { type: "item_loaded", item });
    expect(s.phase).toBe("answering");
    expect(s.phase === "answering" && s.item.question.id).toBe("q1");
    expect(s.phase === "answering" && s.selectedLetter).toBeNull();
    expect(s.phase === "answering" && s.hintOpen).toBe(false);
  });
});

describe("quiz_screen_reducer — per-item start timestamp (D0 elapsed timing)", () => {
  it("item_loaded stamps presentedAt on the answering state (FR-3)", () => {
    const s = quizScreenReducer(initialQuizScreen, {
      type: "item_loaded",
      item,
      presentedAt: 1234,
    });
    expect(s.phase === "answering" && s.presentedAt).toBe(1234);
  });

  it("a second item_loaded after next resets presentedAt (per-item, not cumulative — FR-6)", () => {
    // Item 1 presented at t=1000, answered, Next → loading.
    let s = quizScreenReducer(initialQuizScreen, {
      type: "item_loaded",
      item,
      presentedAt: 1000,
    });
    s = quizScreenReducer(s, { type: "select", letter: "B" });
    s = quizScreenReducer(s, { type: "submitted", verdict: verdict(true), letter: "B" });
    s = quizScreenReducer(s, { type: "next" });
    // Item 2 presented at t=5000 — the clock restarts for the new item.
    s = quizScreenReducer(s, { type: "item_loaded", item, presentedAt: 5000 });
    expect(s.phase === "answering" && s.presentedAt).toBe(5000);
  });

  it("a clock-less item_loaded stores a non-finite start that elapsedMsFrom reads as 0, NOT a fabricated elapsed (contract guard)", () => {
    // The reducer must NOT launder a missing presentedAt into a finite 0: feeding a
    // finite 0 into elapsedMsFrom(0, now) returns `now` — a multi-million-ms
    // fabricated elapsed, the exact D0 bug. Missing → NaN → the helper's finite-guard
    // returns 0. This locks the reducer default and the helper guard to one contract.
    const s = quizScreenReducer(initialQuizScreen, { type: "item_loaded", item });
    const start = s.phase === "answering" ? s.presentedAt : 0;
    expect(Number.isFinite(start)).toBe(false);
    expect(elapsedMsFrom(start, 9_999_999)).toBe(0);
  });
});

describe("elapsedMsFrom — monotonic, clamped, whole-ms (D0 elapsed timing)", () => {
  it("clamps to 0 when now < presentedAt (monotonic safety, never negative — FR-5)", () => {
    // A wall-clock adjustment during answering must not yield a negative elapsed.
    expect(elapsedMsFrom(3000, 1000)).toBe(0);
  });

  it("returns 0 (never NaN/negative) when the start timestamp is missing (FR-2)", () => {
    expect(elapsedMsFrom(undefined, 2500)).toBe(0);
    expect(Number.isNaN(elapsedMsFrom(undefined, 2500))).toBe(false);
  });

  it("rounds a sub-millisecond delta to an honest 0 (edge case, not the old universal stub)", () => {
    expect(elapsedMsFrom(1000.2, 1000.6)).toBe(0);
  });

  it("computes whole-ms elapsed = now − presentedAt on the happy path (FR-4)", () => {
    expect(elapsedMsFrom(1000, 3500)).toBe(2500);
  });
});

describe("quiz_screen_reducer — selection + hint (answering)", () => {
  const answering = quizScreenReducer(initialQuizScreen, { type: "item_loaded", item });

  it("select sets the chosen letter", () => {
    const s = quizScreenReducer(answering, { type: "select", letter: "B" });
    expect(s.phase === "answering" && s.selectedLetter).toBe("B");
  });

  it("toggle_hint flips the hint and marks the item hinted (FR-D5 usedHint)", () => {
    const s = quizScreenReducer(answering, { type: "toggle_hint" });
    expect(s.phase === "answering" && s.hintOpen).toBe(true);
    expect(s.phase === "answering" && s.usedHint).toBe(true);
    // Closing again keeps usedHint sticky (a hint WAS used this item).
    const s2 = quizScreenReducer(s, { type: "toggle_hint" });
    expect(s2.phase === "answering" && s2.hintOpen).toBe(false);
    expect(s2.phase === "answering" && s2.usedHint).toBe(true);
  });
});

describe("quiz_screen_reducer — submit (answering → reviewing)", () => {
  const answered = quizScreenReducer(
    quizScreenReducer(initialQuizScreen, { type: "item_loaded", item }),
    { type: "select", letter: "B" },
  );

  it("a null-verdict submit does NOT advance (no selection, FR-D2a — edge first)", () => {
    const s = quizScreenReducer(answered, { type: "submitted", verdict: null, letter: null });
    expect(s.phase).toBe("answering");
  });

  it("a real verdict advances to reviewing, carrying the graded verdict + answered letter", () => {
    const v = verdict(false);
    const s = quizScreenReducer(answered, { type: "submitted", verdict: v, letter: "B" });
    expect(s.phase).toBe("reviewing");
    expect(s.phase === "reviewing" && s.verdict.correct).toBe(false);
    expect(s.phase === "reviewing" && s.answeredLetter).toBe("B");
  });
});

describe("quiz_screen_reducer — advance + finish (reviewing)", () => {
  const reviewing: QuizScreenState = quizScreenReducer(
    quizScreenReducer(
      quizScreenReducer(initialQuizScreen, { type: "item_loaded", item }),
      { type: "select", letter: "B" },
    ),
    { type: "submitted", verdict: verdict(true), letter: "B" },
  );

  it("next returns to loading (the page then fetches the next item)", () => {
    const s = quizScreenReducer(reviewing, { type: "next" });
    expect(s.phase).toBe("loading");
  });

  it("finish moves to done (the page then navigates to Summary)", () => {
    const s = quizScreenReducer(reviewing, { type: "finish" });
    expect(s.phase).toBe("done");
  });
});

describe("quiz_screen_reducer — end_session (D1 Q-8)", () => {
  const answering: QuizScreenState = quizScreenReducer(initialQuizScreen, {
    type: "item_loaded",
    item,
  });
  const reviewing: QuizScreenState = quizScreenReducer(
    quizScreenReducer(answering, { type: "select", letter: "B" }),
    { type: "submitted", verdict: verdict(true), letter: "B" },
  );

  it("end_session from answering → done, score carries (FR-Q8-6)", () => {
    const s = quizScreenReducer(answering, { type: "end_session" });
    expect(s.phase).toBe("done");
    expect(s.score).toEqual(answering.score);
  });

  it("end_session from reviewing → done, score carries (FR-Q8-6)", () => {
    const s = quizScreenReducer(reviewing, { type: "end_session" });
    expect(s.phase).toBe("done");
    expect(s.score).toEqual({ correct: 1, total: 1 });
  });

  it("end_session from loading is a no-op (FR-Q8-1)", () => {
    const s = quizScreenReducer(initialQuizScreen, { type: "end_session" });
    expect(s.phase).toBe("loading");
  });

  it("end_session from done is a no-op (FR-Q8-2)", () => {
    const done = quizScreenReducer(reviewing, { type: "finish" });
    const s = quizScreenReducer(done, { type: "end_session" });
    expect(s).toBe(done);
  });

  it("finish still routes to done from reviewing (regression, FR-Q8-6)", () => {
    const s = quizScreenReducer(reviewing, { type: "finish" });
    expect(s.phase).toBe("done");
    expect(s.score).toEqual({ correct: 1, total: 1 });
  });
});

describe("quiz_screen_reducer — running score tally (FR-D3 close)", () => {
  it("starts the tally at 0/0", () => {
    expect(initialQuizScreen.score).toEqual({ correct: 0, total: 0 });
  });

  it("a graded submit increments total; a correct one also increments correct", () => {
    const answered = quizScreenReducer(
      quizScreenReducer(initialQuizScreen, { type: "item_loaded", item }),
      { type: "select", letter: "B" },
    );
    const reviewing = quizScreenReducer(answered, {
      type: "submitted",
      verdict: verdict(true),
      letter: "B",
    });
    expect(reviewing.score).toEqual({ correct: 1, total: 1 });
  });

  it("a wrong submit increments total only", () => {
    const answered = quizScreenReducer(
      quizScreenReducer(initialQuizScreen, { type: "item_loaded", item }),
      { type: "select", letter: "A" },
    );
    const reviewing = quizScreenReducer(answered, {
      type: "submitted",
      verdict: verdict(false),
      letter: "A",
    });
    expect(reviewing.score).toEqual({ correct: 0, total: 1 });
  });

  it("a no-selection submit leaves the tally untouched (FR-D2a)", () => {
    const answered = quizScreenReducer(
      quizScreenReducer(initialQuizScreen, { type: "item_loaded", item }),
      { type: "select", letter: "B" },
    );
    const same = quizScreenReducer(answered, {
      type: "submitted",
      verdict: null,
      letter: null,
    });
    expect(same.score).toEqual({ correct: 0, total: 0 });
  });

  it("the tally survives item_loaded, next, and finish across a two-item walk", () => {
    // Item 1: correct.
    let s = quizScreenReducer(initialQuizScreen, { type: "item_loaded", item });
    s = quizScreenReducer(s, { type: "select", letter: "B" });
    s = quizScreenReducer(s, { type: "submitted", verdict: verdict(true), letter: "B" });
    s = quizScreenReducer(s, { type: "next" }); // → loading, tally preserved
    expect(s.score).toEqual({ correct: 1, total: 1 });
    // Item 2: wrong.
    s = quizScreenReducer(s, { type: "item_loaded", item });
    s = quizScreenReducer(s, { type: "select", letter: "A" });
    s = quizScreenReducer(s, { type: "submitted", verdict: verdict(false), letter: "A" });
    expect(s.score).toEqual({ correct: 1, total: 2 });
    // Finish carries the final tally to `done` for the session-close.
    s = quizScreenReducer(s, { type: "finish" });
    expect(s.phase).toBe("done");
    expect(s.score).toEqual({ correct: 1, total: 2 });
  });
});

describe("quiz_screen_reducer — resume_item (FLAG-4 / FR-3)", () => {
  const item2 = {
    skillId: "s-punc",
    question: question({ id: "q2", stem: "Which choice fixes the comma splice?" }),
    hintLadder: [],
  };

  it("resume_item restores answering with the stashed item and score (not 0/0)", () => {
    const s = quizScreenReducer(initialQuizScreen, {
      type: "resume_item",
      item: item2,
      score: { correct: 1, total: 1 },
      presentedAt: 42,
    });
    expect(s.phase).toBe("answering");
    expect(s.phase === "answering" && s.item.question.id).toBe("q2");
    expect(s.phase === "answering" && s.item.question.stem).toBe(
      "Which choice fixes the comma splice?",
    );
    expect(s.score).toEqual({ correct: 1, total: 1 });
    expect(s.phase === "answering" && s.selectedLetter).toBeNull();
    expect(s.phase === "answering" && s.hintOpen).toBe(false);
    expect(s.phase === "answering" && s.usedHint).toBe(false);
    expect(s.phase === "answering" && s.presentedAt).toBe(42);
  });

  it("resume_item with feedback restores reviewing at the same score (not answering N+1)", () => {
    const s = quizScreenReducer(initialQuizScreen, {
      type: "resume_item",
      item: item2,
      score: { correct: 1, total: 2 },
      feedback: {
        verdict: verdict(false),
        answeredLetter: "A",
        usedHint: true,
      },
    });
    expect(s.phase).toBe("reviewing");
    expect(s.phase === "reviewing" && s.item.question.id).toBe("q2");
    expect(s.score).toEqual({ correct: 1, total: 2 });
    expect(s.phase === "reviewing" && s.answeredLetter).toBe("A");
    expect(s.phase === "reviewing" && s.verdict.correct).toBe(false);
    expect(s.phase === "reviewing" && s.usedHint).toBe(true);
  });

  it("resume_item from a mid-walk loading state still restores the stashed tally", () => {
    let s = quizScreenReducer(initialQuizScreen, { type: "item_loaded", item });
    s = quizScreenReducer(s, { type: "select", letter: "B" });
    s = quizScreenReducer(s, { type: "submitted", verdict: verdict(true), letter: "B" });
    s = quizScreenReducer(s, { type: "next" });
    expect(s.phase).toBe("loading");
    s = quizScreenReducer(s, {
      type: "resume_item",
      item: item2,
      score: { correct: 1, total: 1 },
    });
    expect(s.phase).toBe("answering");
    expect(s.score).toEqual({ correct: 1, total: 1 });
  });
});
