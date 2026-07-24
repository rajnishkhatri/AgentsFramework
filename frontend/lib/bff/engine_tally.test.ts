import { describe, expect, it } from "vitest";
import { commitFirstTally, isAtTargetCount } from "./engine_tally";
import type { Attempt } from "../wire/engine_entities";

function attempt(over: Partial<Attempt>): Attempt {
  return {
    id: "a",
    subject: "act-english",
    session_id: "s",
    question_id: "q1",
    chosen_letter: "A",
    correct: false,
    elapsed_ms: 1,
    used_hint: false,
    created_at: "2026-07-22T00:00:00.000Z",
    resolution: null,
    idempotency_key: "k",
    ...over,
  };
}

describe("commitFirstTally — FR-B10", () => {
  it("counts unique first_try / unique resolved", () => {
    const attempts = [
      attempt({ id: "a1", question_id: "q1", resolution: "first_try", correct: true }),
      attempt({ id: "a2", question_id: "q2", resolution: "coached", correct: true }),
      attempt({ id: "a3", question_id: "q3", resolution: "walked_through", correct: true }),
      // non-resolving row ignored
      attempt({ id: "a4", question_id: "q4", resolution: null, correct: false }),
      // duplicate question — §6 latest (greater created_at) wins, not first
      attempt({
        id: "a5",
        question_id: "q1",
        resolution: "coached",
        correct: true,
        created_at: "2026-07-22T00:00:01.000Z",
      }),
    ];
    expect(commitFirstTally(attempts)).toEqual({
      score_correct: 0, // q1's latest is coached, not first_try
      score_total: 3,
    });
  });

  it("same created_at → greatest id wins (T R.7 / §6)", () => {
    const ts = "2026-07-22T00:00:00.000Z";
    expect(
      commitFirstTally([
        attempt({
          id: "id-aaa",
          question_id: "q1",
          resolution: "first_try",
          correct: true,
          created_at: ts,
        }),
        attempt({
          id: "id-zzz",
          question_id: "q1",
          resolution: "walked_through",
          correct: false,
          created_at: ts,
        }),
      ]),
    ).toEqual({ score_correct: 0, score_total: 1 });
  });
});

describe("isAtTargetCount — FR-C2 / T R.3", () => {
  it("is true when score_total meets a non-null target", () => {
    expect(isAtTargetCount(30, 30)).toBe(true);
    expect(isAtTargetCount(30, 31)).toBe(true);
  });

  it("is false below target, and never for endless (null) sessions", () => {
    expect(isAtTargetCount(30, 29)).toBe(false);
    expect(isAtTargetCount(null, 100)).toBe(false);
    expect(isAtTargetCount(undefined, 30)).toBe(false);
  });
});
