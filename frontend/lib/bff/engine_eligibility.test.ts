/**
 * FR-E4 / E1 / E2 — already-correct projection (inverse of outstanding misses).
 */

import { describe, expect, it } from "vitest";
import { projectAlreadyCorrectQuestionIds } from "./engine_eligibility";

describe("projectAlreadyCorrectQuestionIds — FR-E4 / E1 / E2", () => {
  it("returns question ids whose latest attempt is correct===true (FR-E4)", () => {
    const ids = projectAlreadyCorrectQuestionIds([
      { question_id: "q1", correct: true, created_at: "2026-07-22T00:02:00.000Z" },
      { question_id: "q2", correct: false, created_at: "2026-07-22T00:01:00.000Z" },
    ]);
    expect(ids).toEqual(["q1"]);
  });

  it("uses the newest created_at per question_id (FR-E1 latest)", () => {
    const ids = projectAlreadyCorrectQuestionIds([
      // newest-first
      { question_id: "q1", correct: true, created_at: "2026-07-22T00:02:00.000Z" },
      { question_id: "q1", correct: false, created_at: "2026-07-22T00:01:00.000Z" },
    ]);
    expect(ids).toEqual(["q1"]);
  });

  it("keeps misses eligible — incorrect latest is omitted (FR-E2)", () => {
    const ids = projectAlreadyCorrectQuestionIds([
      { question_id: "q-miss", correct: false, created_at: "2026-07-22T00:01:00.000Z" },
    ]);
    expect(ids).toEqual([]);
  });

  it("excludes coached-correct and keeps walked-through via correct===true only (FR-E1 edge)", () => {
    const ids = projectAlreadyCorrectQuestionIds([
      {
        question_id: "q-coached",
        correct: true, // resolution=coached — still correct===true
        created_at: "2026-07-22T00:02:00.000Z",
      },
      {
        question_id: "q-walked",
        correct: false, // resolution=walked_through
        created_at: "2026-07-22T00:01:00.000Z",
      },
    ]);
    expect(ids).toEqual(["q-coached"]);
    expect(ids).not.toContain("q-walked");
  });

  it("a later correct clears a prior miss from the preferred-exclude set", () => {
    const ids = projectAlreadyCorrectQuestionIds([
      { question_id: "q1", correct: true, created_at: "2026-07-22T00:03:00.000Z" },
      { question_id: "q1", correct: false, created_at: "2026-07-22T00:01:00.000Z" },
    ]);
    expect(ids).toEqual(["q1"]);
  });

  it("a later miss re-admits a previously-correct question (stays out of already-correct)", () => {
    const ids = projectAlreadyCorrectQuestionIds([
      { question_id: "q1", correct: false, created_at: "2026-07-22T00:03:00.000Z" },
      { question_id: "q1", correct: true, created_at: "2026-07-22T00:01:00.000Z" },
    ]);
    expect(ids).toEqual([]);
  });
});
