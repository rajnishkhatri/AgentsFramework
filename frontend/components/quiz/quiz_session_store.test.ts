/**
 * Phase 1.4′ — quiz_session_store round-trip (L1).
 *
 * The store is the in-session Quiz→Summary handoff for the FR-G1 mastery-delta
 * snapshot (ADR-0011 §4): the Quiz page stashes the `skillStateAtStart` map it
 * captured at `openQuizSession`, keyed by session id, and the Summary page reads
 * it back so the delta is real within an unbroken session. A fresh/deep-link
 * Summary load finds nothing → empty snapshot → delta "—" (the documented
 * resume limitation). Edge-first: a miss (unknown id, or after clear) is null,
 * never a stale/other-session snapshot.
 */

import { afterEach, describe, expect, it } from "vitest";
import type { SkillState } from "@/lib/wire/engine_entities";
import {
  clearActiveQuiz,
  clearQuizSession,
  readActiveQuiz,
  readQuizSessionSnapshot,
  setActiveQuiz,
  stashQuizSession,
} from "./quiz_session_store";

function skillState(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: "act-english",
    skill_id: "commas",
    learner_id: "maya",
    mastery: 0.42,
    last_seen: null,
    fsrs_stability: 1,
    fsrs_difficulty: 5,
    due_at: "2026-07-01T00:00:00.000Z",
    fsrs_card: {},
    ...over,
  };
}

afterEach(() => {
  // The store is a module-level singleton; keep tests isolated.
  clearQuizSession("s1");
  clearQuizSession("s2");
  clearActiveQuiz();
});

describe("quiz_session_store — miss is null (edge first)", () => {
  it("returns null for an unknown session id", () => {
    expect(readQuizSessionSnapshot("nope")).toBeNull();
  });

  it("returns null after the session is cleared", () => {
    stashQuizSession("s1", new Map([["commas", skillState()]]));
    clearQuizSession("s1");
    expect(readQuizSessionSnapshot("s1")).toBeNull();
  });
});

describe("quiz_session_store — round-trip", () => {
  it("reads back exactly the snapshot stashed for that id", () => {
    const snap = new Map([["commas", skillState({ mastery: 0.42 })]]);
    stashQuizSession("s1", snap);
    const got = readQuizSessionSnapshot("s1");
    expect(got).not.toBeNull();
    expect(got!.get("commas")?.mastery).toBe(0.42);
  });

  it("keys by session id — one session's snapshot never leaks to another", () => {
    stashQuizSession("s1", new Map([["commas", skillState({ mastery: 0.42 })]]));
    stashQuizSession("s2", new Map([["commas", skillState({ mastery: 0.9 })]]));
    expect(readQuizSessionSnapshot("s1")!.get("commas")?.mastery).toBe(0.42);
    expect(readQuizSessionSnapshot("s2")!.get("commas")?.mastery).toBe(0.9);
  });

  it("a brand-new-learner empty snapshot round-trips as an empty (non-null) map", () => {
    stashQuizSession("s1", new Map());
    const got = readQuizSessionSnapshot("s1");
    expect(got).not.toBeNull();
    expect(got!.size).toBe(0);
  });
});

describe("quiz_session_store — active quiz pointer (FR-1/FR-2)", () => {
  it("returns null when no active pointer is set", () => {
    expect(readActiveQuiz()).toBeNull();
  });

  it("returns null after the active pointer is cleared", () => {
    setActiveQuiz({
      sessionId: "s1",
      questionId: "q2",
      position: 2,
      correct: 1,
      total: 1,
    });
    clearActiveQuiz();
    expect(readActiveQuiz()).toBeNull();
  });

  it("reads back the pointer set for the live quiz (incl. stashed score)", () => {
    setActiveQuiz({
      sessionId: "s1",
      questionId: "q2",
      position: 2,
      correct: 1,
      total: 1,
      phase: "answering",
    });
    expect(readActiveQuiz()).toEqual({
      sessionId: "s1",
      questionId: "q2",
      position: 2,
      correct: 1,
      total: 1,
      phase: "answering",
    });
  });

  it("reads back a feedback-phase pointer with verdict + answeredLetter", () => {
    setActiveQuiz({
      sessionId: "s1",
      questionId: "q3",
      position: 3,
      correct: 1,
      total: 3,
      phase: "feedback",
      verdict: { correct: false, correct_letter: "D" },
      answeredLetter: "A",
      usedHint: false,
    });
    expect(readActiveQuiz()).toEqual({
      sessionId: "s1",
      questionId: "q3",
      position: 3,
      correct: 1,
      total: 3,
      phase: "feedback",
      verdict: { correct: false, correct_letter: "D" },
      answeredLetter: "A",
      usedHint: false,
    });
  });

  it("overwrites the previous pointer on a later set", () => {
    setActiveQuiz({
      sessionId: "s1",
      questionId: "q1",
      position: 1,
      correct: 0,
      total: 0,
    });
    setActiveQuiz({
      sessionId: "s1",
      questionId: "q2",
      position: 2,
      correct: 0,
      total: 1,
    });
    expect(readActiveQuiz()?.questionId).toBe("q2");
    expect(readActiveQuiz()?.total).toBe(1);
  });
});
