/**
 * T R.7 / §6 — per-question resolution order must be ONE helper, shared by
 * tally (FR-B10), summary outcomes + misses (FR-D1/D2), and eligibility (FR-E1).
 */

import { describe, expect, it } from "vitest";
import { commitFirstTally } from "../bff/engine_tally";
import { projectAlreadyCorrectQuestionIds } from "../bff/engine_eligibility";
import type { Attempt } from "../wire/engine_entities";
import {
  countSessionOutcomes,
  projectSessionInsights,
} from "./session_summary_vm";
import { resolvingAttemptForQuestion } from "./resolving_attempt";

const TS = "2026-07-23T12:00:00.000Z";

function attempt(over: Partial<Attempt> & Pick<Attempt, "id" | "resolution" | "correct">): Attempt {
  return {
    subject: "act-english",
    session_id: "s1",
    question_id: "q1",
    chosen_letter: "A",
    elapsed_ms: 1,
    used_hint: false,
    created_at: TS,
    idempotency_key: "k",
    ...over,
  };
}

describe("resolvingAttemptForQuestion — §6 tie-break", () => {
  it("keeps greatest created_at; same timestamp → greatest id", () => {
    const earlier = attempt({
      id: "id-zzz",
      created_at: "2026-07-23T11:00:00.000Z",
      resolution: "walked_through",
      correct: false,
    });
    const sameTsLow = attempt({
      id: "id-aaa",
      created_at: TS,
      resolution: "first_try",
      correct: true,
    });
    const sameTsHigh = attempt({
      id: "id-zzz",
      created_at: TS,
      resolution: "walked_through",
      correct: false,
    });
    // Deliberately unsorted — helper must not depend on caller order.
    const map = resolvingAttemptForQuestion([sameTsLow, earlier, sameTsHigh]);
    expect(map.get("q1")?.id).toBe("id-zzz");
    expect(map.get("q1")?.resolution).toBe("walked_through");
  });
});

describe("T R.7 — four consumers agree on same-created_at pair", () => {
  it("tally / outcomes / misses / eligibility all select greatest id", () => {
    // Same created_at: low id = first_try (correct); high id = walked_through.
    // §6 winner = high id → walked_through / incorrect.
    const rows = [
      attempt({
        id: "id-aaa",
        resolution: "first_try",
        correct: true,
      }),
      attempt({
        id: "id-zzz",
        resolution: "walked_through",
        correct: false,
      }),
    ];

    const winner = resolvingAttemptForQuestion(rows).get("q1");
    expect(winner?.id).toBe("id-zzz");

    expect(commitFirstTally(rows)).toEqual({
      score_correct: 0,
      score_total: 1,
    });

    expect(countSessionOutcomes(rows)).toEqual({
      firstTry: 0,
      coached: 0,
      walkedThrough: 1,
    });

    const insights = projectSessionInsights(
      rows,
      [{ id: "q1", skill_id: "sk", stem: "stem" }],
      [{ id: "sk", name: "Skill" }],
    );
    expect(insights.misses.map((m) => m.questionId)).toEqual(["q1"]);
    expect(insights.misses[0]?.resolution).toBe("walked_through");

    // Eligibility must not require newest-first caller order when ids tie-break.
    expect(
      projectAlreadyCorrectQuestionIds(
        rows.map((r) => ({
          id: r.id,
          question_id: r.question_id,
          correct: r.correct,
          created_at: r.created_at,
        })),
      ),
    ).toEqual([]);
  });
});
