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
    reviewed: true,
    generated_by: "test",
    ...over,
  };
}

function verdict(correct: boolean): Verdict {
  return { correct, correct_letter: "B" };
}

const item = { skillId: "s-punc", question: question() };

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
