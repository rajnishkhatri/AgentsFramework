/**
 * test_runner_reducer — the timed Test-Mode phase machine (TDD, node-level L1).
 *
 * The Test-Mode surface is a FIXED, timed section (unlike the endless adaptive
 * quiz): the learner moves through a known list of items, may revisit and change
 * answers, then submits the whole section at once (or the countdown forces it).
 * All that transition logic lives here as a pure, React-free reducer (F-R1), so
 * every invariant is node-testable with no DOM — the analogue of
 * quiz_screen_reducer.
 *
 * Invariants pinned below:
 *   - The answers map persists across next/prev navigation (revisit is allowed).
 *   - Re-selecting overwrites the prior answer for that item; an item may be left
 *     unanswered (null).
 *   - `submit_section` grades EVERY item via an injected pure grade fn → results
 *     with a correct/total tally; unanswered items count as incorrect.
 *   - Navigation is clamped to [0, count-1]; you cannot next past the last item.
 *   - Grading is idempotent: a second submit does not change the tally.
 */

import { describe, it, expect } from "vitest";
import {
  initialTestRunner,
  testRunnerReducer,
  type GradeFn,
  type TestRunnerState,
} from "./test_runner_reducer";
import type { Question } from "@/lib/wire/engine_entities";

// Three tiny questions; answer_letter is the "correct" one.
function q(id: string, answer: string): Question {
  return {
    id,
    subject: "act-english",
    skill_id: "s-punc",
    difficulty: 2,
    context_html: `ctx ${id}`,
    stem: `stem ${id}`,
    choices: [
      { letter: "A", label: "a", is_no_change: true },
      { letter: "B", label: "b", is_no_change: false },
      { letter: "C", label: "c", is_no_change: false },
      { letter: "D", label: "d", is_no_change: false },
    ],
    answer_letter: answer,
    per_choice_rationale: { A: "", B: "", C: "", D: "" },
    why_correct_md: "",
    why_tempted_md: "",
    rule_md: "",
    item_type: "underlined-span-mc",
    reviewed: true,
    generated_by: "test",
  };
}

const QUESTIONS: readonly Question[] = [q("q1", "B"), q("q2", "A"), q("q3", "D")];

// Pure grade fn stand-in for the engine Grader: exact-letter match.
const grade: GradeFn = (question, letter) =>
  letter != null && letter === question.answer_letter;

function start(): TestRunnerState {
  return testRunnerReducer(initialTestRunner(QUESTIONS), { type: "start" });
}

describe("testRunnerReducer", () => {
  it("starts in intro with a zeroed answers map", () => {
    const s = initialTestRunner(QUESTIONS);
    expect(s.phase).toBe("intro");
  });

  it("start → in_section at index 0", () => {
    const s = start();
    expect(s.phase).toBe("in_section");
    if (s.phase !== "in_section") throw new Error();
    expect(s.index).toBe(0);
    expect(s.answers).toEqual({});
  });

  it("records a selection for the current item", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "select", letter: "B" });
    if (s.phase !== "in_section") throw new Error();
    expect(s.answers["q1"]).toBe("B");
  });

  it("persists answers across next/prev navigation (revisit allowed)", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "select", letter: "B" }); // q1 = B
    s = testRunnerReducer(s, { type: "next" }); // → q2
    s = testRunnerReducer(s, { type: "select", letter: "C" }); // q2 = C
    s = testRunnerReducer(s, { type: "prev" }); // ← q1
    if (s.phase !== "in_section") throw new Error();
    expect(s.index).toBe(0);
    expect(s.answers["q1"]).toBe("B"); // still there
    expect(s.answers["q2"]).toBe("C");
  });

  it("re-selecting overwrites the prior answer", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "select", letter: "B" });
    s = testRunnerReducer(s, { type: "select", letter: "D" });
    if (s.phase !== "in_section") throw new Error();
    expect(s.answers["q1"]).toBe("D");
  });

  it("clamps navigation: prev at 0 stays at 0; next past last stays at last", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "prev" });
    if (s.phase !== "in_section") throw new Error();
    expect(s.index).toBe(0);
    s = testRunnerReducer(s, { type: "next" });
    s = testRunnerReducer(s, { type: "next" });
    s = testRunnerReducer(s, { type: "next" }); // past last (count 3)
    if (s.phase !== "in_section") throw new Error();
    expect(s.index).toBe(2);
  });

  it("submit_section grades every item; unanswered counts as wrong", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "select", letter: "B" }); // q1 correct
    s = testRunnerReducer(s, { type: "next" });
    s = testRunnerReducer(s, { type: "select", letter: "C" }); // q2 wrong (ans A)
    // q3 left unanswered → wrong
    s = testRunnerReducer(s, { type: "submit_section", grade });
    expect(s.phase).toBe("results");
    if (s.phase !== "results") throw new Error();
    expect(s.correct).toBe(1);
    expect(s.total).toBe(3);
  });

  it("a fully-correct walk scores total/total", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "select", letter: "B" });
    s = testRunnerReducer(s, { type: "next" });
    s = testRunnerReducer(s, { type: "select", letter: "A" });
    s = testRunnerReducer(s, { type: "next" });
    s = testRunnerReducer(s, { type: "select", letter: "D" });
    s = testRunnerReducer(s, { type: "submit_section", grade });
    if (s.phase !== "results") throw new Error();
    expect(s.correct).toBe(3);
    expect(s.total).toBe(3);
  });

  it("submit is idempotent — a second submit does not change the tally", () => {
    let s = start();
    s = testRunnerReducer(s, { type: "select", letter: "B" });
    s = testRunnerReducer(s, { type: "submit_section", grade });
    const first = s.phase === "results" ? s.correct : -1;
    s = testRunnerReducer(s, { type: "submit_section", grade });
    if (s.phase !== "results") throw new Error();
    expect(s.correct).toBe(first);
  });

  it("timer-forced submit is the same action as a manual one", () => {
    // The page dispatches submit_section on expiry; there is no separate action,
    // so an expiry submit with no answers scores 0/total deterministically.
    let s = start();
    s = testRunnerReducer(s, { type: "submit_section", grade });
    if (s.phase !== "results") throw new Error();
    expect(s.correct).toBe(0);
    expect(s.total).toBe(3);
  });
});
