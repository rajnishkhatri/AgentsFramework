/**
 * Phase 0.5 — session_summary_vm (FR-G1..G3, L2 contract, TAP-2 table-driven).
 *
 * Pure map: (QuizSession, RecommendedNext, nextSkill, masteryDeltaPct) →
 * SessionSummaryVM. FR-G1: stats come from the STORED session score (no
 * recompute). Three stat tiles: score (7/10), mastery delta (+8%), time (12 min);
 * plus a recommended-next card (FR-G1) that re-opens Quiz (FR-G2).
 *
 * Edge row first: an un-closed session (ended_at null) → time tile "—", no crash.
 */

import { describe, expect, it } from "vitest";
import {
  countSessionOutcomes,
  projectSessionInsights,
  toSessionSummaryVM,
} from "./session_summary_vm";
import type { QuizSession, RecommendedNext, Skill } from "../wire/engine_entities";

function session(over: Partial<QuizSession> = {}): QuizSession {
  return {
    id: "sess1",
    subject: "act-english",
    learner_id: "maya",
    mode: "adaptive",
    skill_focus: "s-punc",
    started_at: "2026-06-30T10:00:00.000Z",
    ended_at: "2026-06-30T10:12:00.000Z", // 12 min
    score_correct: 7,
    score_total: 10,
    target_count: null, // S3: this VM ignores length; null keeps the fixture endless
    ...over,
  };
}

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-conc",
    subject: "act-english",
    key: "conciseness",
    name: "Conciseness",
    share_of_test_pct: 16,
    accent_var: "--color-bucket-conciseness",
    description: "Say it in fewer words.",
    order: 5,
    ...over,
  };
}

const rec: RecommendedNext = { skill_id: "s-conc", mode: "drill" };

describe("toSessionSummaryVM — edge row first", () => {
  it("un-closed session (ended_at null) → time tile em-dash, no crash", () => {
    const vm = toSessionSummaryVM(
      session({ ended_at: null }),
      rec,
      skill(),
      8,
      null,
      false,
      false,
    );
    expect(vm.timeTile).toBe("—");
    expect(vm.scoreTile).toBe("7/10"); // still reads stored score (FR-G1)
  });

  it("sub-minute session (>0 but <60s) → '<1 min', never a fabricated '0 min'", () => {
    // S-2b: a real, closed 18s session is not zero time. Rounding to whole
    // minutes prints "0 min" — a value indistinguishable from an instant/no-op.
    // The honest form is "<1 min".
    const vm = toSessionSummaryVM(
      session({
        started_at: "2026-06-30T10:00:00.000Z",
        ended_at: "2026-06-30T10:00:18.000Z", // 18s
      }),
      rec,
      skill(),
      8,
      null,
      false,
      false,
    );
    expect(vm.timeTile).toBe("<1 min");
  });

  it("a session at/over one minute still reads whole minutes", () => {
    const vm = toSessionSummaryVM(
      session({
        started_at: "2026-06-30T10:00:00.000Z",
        ended_at: "2026-06-30T10:01:00.000Z", // exactly 60s
      }),
      rec,
      skill(),
      8,
      null,
      false,
      false,
    );
    expect(vm.timeTile).toBe("1 min");
  });
});

describe("toSessionSummaryVM — happy path (FR-G1/G2)", () => {
  const vm = toSessionSummaryVM(session(), rec, skill(), 8, null, false, true);

  it("score tile reads the STORED score, not a recompute (FR-G1)", () => {
    expect(vm.scoreTile).toBe("7/10");
    expect(vm.scoreCorrect).toBe(7);
    expect(vm.scoreTotal).toBe(10);
  });

  it("mastery-delta tile is signed percent (FR-G1)", () => {
    expect(vm.masteryDeltaTile).toBe("+8%");
  });

  it("negative mastery delta keeps its sign", () => {
    const down = toSessionSummaryVM(session(), rec, skill(), -3, null, false, true);
    expect(down.masteryDeltaTile).toBe("-3%");
  });

  it("a sub-half negative delta rounds to +0%, never -0%", () => {
    // -0.4 rounds to 0; the tile must read "+0%" (Math.round(-0.4) === -0, so
    // choosing the sign from the raw delta would print a nonsensical "-0%").
    const flat = toSessionSummaryVM(session(), rec, skill(), -0.4, null, false, true);
    expect(flat.masteryDeltaTile).toBe("+0%");
  });

  it("time tile is whole minutes from stored timestamps", () => {
    expect(vm.timeTile).toBe("12 min");
  });

  it("recommended-next card names the skill + mode and re-opens Quiz (FR-G2)", () => {
    expect(vm.recommended.skillId).toBe("s-conc");
    expect(vm.recommended.skillName).toBe("Conciseness");
    expect(vm.recommended.mode).toBe("drill");
    expect(vm.recommended.accentVar).toBe("--color-bucket-conciseness");
  });
});

describe("toSessionSummaryVM — C2 payoff (FR-7/FR-8/FR-11/FR-13)", () => {
  it("drill_title_uses_target_count_when_present", () => {
    const vm = toSessionSummaryVM(
      session({ target_count: 6 }),
      rec,
      skill(),
      8,
      null,
      false,
      false,
    );
    expect(vm.recommended.drillTitle).toBe("6-item drill: Conciseness");
  });

  it("drill_title_falls_back_to_skill_name_when_target_count_null", () => {
    const vm = toSessionSummaryVM(
      session({ target_count: null }),
      rec,
      skill(),
      8,
      null,
      false,
      false,
    );
    expect(vm.recommended.drillTitle).toBe("Drill: Conciseness");
  });

  it("keeps_neutral_title_when_score_ratio_below_threshold", () => {
    const vm = toSessionSummaryVM(
      session({ score_correct: 5, score_total: 10 }),
      rec,
      skill(),
      8,
      "some misconception",
      true,
      false,
    );
    expect(vm.showFramedTitle).toBe(false);
    expect(vm.title).toBe("Session summary");
    expect(vm.body).toBe("Here's how this session went.");
  });

  it("flips_framed_title_at_ratio_gte_0_6", () => {
    const vm = toSessionSummaryVM(
      session({ score_correct: 6, score_total: 10 }),
      rec,
      skill(),
      8,
      null,
      false,
      true,
    );
    expect(vm.showFramedTitle).toBe(true);
    expect(vm.title).toBe("Nice work — you found the pattern.");
  });

  it("treats_score_total_zero_as_below_threshold", () => {
    const vm = toSessionSummaryVM(
      session({ score_correct: 0, score_total: 0 }),
      rec,
      skill(),
      8,
      null,
      false,
      false,
    );
    expect(vm.showFramedTitle).toBe(false);
    expect(vm.title).toBe("Session summary");
    expect(vm.body).toBe("Here's how this session went.");
  });

  it("framed_title_body_uses_neutral_copy_when_selfCorrected_false", () => {
    const vm = toSessionSummaryVM(
      session({ score_correct: 7, score_total: 10 }),
      rec,
      skill(),
      8,
      "confusing past with participle",
      false,
      true,
    );
    expect(vm.body).toBe("You cleared the Conciseness bar.");
  });

  it("framed_title_body_references_misconception_when_selfCorrected_true", () => {
    const vm = toSessionSummaryVM(
      session({ score_correct: 7, score_total: 10 }),
      rec,
      skill(),
      8,
      "confusing past with participle",
      true,
      true,
    );
    expect(vm.body).toBe("The pattern: confusing past with participle.");
    expect(vm.misconception).toBe("confusing past with participle");
    expect(vm.selfCorrected).toBe(true);
  });
});

describe("countSessionOutcomes — commit-first FR-11", () => {
  it("counts first_try / coached / walked_through from resolving rows", () => {
    const counts = countSessionOutcomes([
      {
        question_id: "q1",
        correct: true,
        resolution: "first_try",
        created_at: "2026-07-19T00:00:01Z",
      },
      {
        question_id: "q2",
        correct: false,
        resolution: null,
        created_at: "2026-07-19T00:00:02Z",
      },
      {
        question_id: "q2",
        correct: true,
        resolution: "coached",
        created_at: "2026-07-19T00:00:03Z",
      },
      {
        question_id: "q3",
        correct: false,
        resolution: "walked_through",
        created_at: "2026-07-19T00:00:04Z",
      },
    ]);
    expect(counts).toEqual({ firstTry: 1, coached: 1, walkedThrough: 1 });
  });

  it("legacy null-resolution correct ⇒ first_try; empty ⇒ null (AP-6)", () => {
    expect(countSessionOutcomes([])).toBeNull();
    const legacy = countSessionOutcomes([
      {
        question_id: "q1",
        correct: true,
        resolution: null,
        created_at: "2026-07-19T00:00:01Z",
      },
    ]);
    expect(legacy).toEqual({ firstTry: 1, coached: 0, walkedThrough: 0 });
  });
});

describe("projectSessionInsights — Phase D misses (FR-D1/D1a)", () => {
  it("lists this session's resolving incorrect and walked-through questions", () => {
    const insights = projectSessionInsights(
      [
        {
          question_id: "q-coached",
          correct: false,
          resolution: null,
          created_at: "2026-07-19T00:00:01Z",
        },
        {
          question_id: "q-coached",
          correct: true,
          resolution: "coached",
          created_at: "2026-07-19T00:00:02Z",
        },
        {
          question_id: "q-walked",
          correct: false,
          resolution: "walked_through",
          created_at: "2026-07-19T00:00:03Z",
        },
        {
          question_id: "q-wrong",
          correct: false,
          resolution: null,
          created_at: "2026-07-19T00:00:04Z",
        },
      ],
      [
        { id: "q-coached", skill_id: "s1", stem: "Coached stem" },
        { id: "q-walked", skill_id: "s1", stem: "Walked stem" },
        { id: "q-wrong", skill_id: "s2", stem: "Wrong stem" },
      ],
      [
        { id: "s1", name: "Punctuation" },
        { id: "s2", name: "Grammar" },
      ],
    );

    expect(insights.misses).toEqual([
      {
        questionId: "q-walked",
        stem: "Walked stem",
        skillId: "s1",
        skillName: "Punctuation",
        resolution: "walked_through",
      },
      {
        questionId: "q-wrong",
        stem: "Wrong stem",
        skillId: "s2",
        skillName: "Grammar",
        resolution: null,
      },
    ]);
  });
});

describe("projectSessionInsights — this-session skill panel (FR-D2/D3)", () => {
  it("groups resolving rows by question skill without changing the stored headline", () => {
    const insights = projectSessionInsights(
      [
        {
          question_id: "q1",
          correct: true,
          resolution: "first_try",
          created_at: "2026-07-19T00:00:01Z",
        },
        {
          question_id: "q2",
          correct: false,
          resolution: null,
          created_at: "2026-07-19T00:00:02Z",
        },
        {
          question_id: "q2",
          correct: true,
          resolution: "coached",
          created_at: "2026-07-19T00:00:03Z",
        },
        {
          question_id: "q3",
          correct: false,
          resolution: "walked_through",
          created_at: "2026-07-19T00:00:04Z",
        },
      ],
      [
        { id: "q1", skill_id: "s1", stem: "One" },
        { id: "q2", skill_id: "s1", stem: "Two" },
        { id: "q3", skill_id: "s2", stem: "Three" },
      ],
      [
        { id: "s1", name: "Punctuation" },
        { id: "s2", name: "Grammar" },
      ],
    );

    expect(insights.skillPerformance).toEqual([
      {
        skillId: "s1",
        skillName: "Punctuation",
        correct: 2,
        total: 2,
        accuracyPct: 100,
        strength: "strong",
      },
      {
        skillId: "s2",
        skillName: "Grammar",
        correct: 0,
        total: 1,
        accuracyPct: 0,
        strength: "weak",
      },
    ]);

    const vm = toSessionSummaryVM(
      session({ score_correct: 1, score_total: 3 }),
      rec,
      skill(),
      0,
      null,
      false,
      false,
    );
    expect(vm.scoreTile).toBe("1/3");
  });

  it("omits taxonomy skills with no on-skill attempts (FR-D5)", () => {
    const insights = projectSessionInsights(
      [
        {
          question_id: "q1",
          correct: true,
          resolution: "first_try",
          created_at: "2026-07-19T00:00:01Z",
        },
      ],
      [{ id: "q1", skill_id: "s1", stem: "One" }],
      [
        { id: "s1", name: "Punctuation" },
        { id: "s-never-served", name: "Rhetoric" },
      ],
    );

    expect(insights.skillPerformance.map((row) => row.skillName)).toEqual([
      "Punctuation",
    ]);
    expect(insights.skillPerformance).not.toContainEqual(
      expect.objectContaining({ skillName: "Rhetoric", accuracyPct: 0 }),
    );
  });
});
