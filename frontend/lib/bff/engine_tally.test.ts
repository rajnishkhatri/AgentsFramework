import { describe, expect, it } from "vitest";
import { commitFirstTally } from "./engine_tally";
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
      attempt({ question_id: "q1", resolution: "first_try", correct: true }),
      attempt({ question_id: "q2", resolution: "coached", correct: true }),
      attempt({ question_id: "q3", resolution: "walked_through", correct: true }),
      // non-resolving row ignored
      attempt({ question_id: "q4", resolution: null, correct: false }),
      // duplicate question — first resolution wins
      attempt({ question_id: "q1", resolution: "coached", correct: true }),
    ];
    expect(commitFirstTally(attempts)).toEqual({
      score_correct: 1,
      score_total: 3,
    });
  });
});
