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
import { toSessionSummaryVM } from "./session_summary_vm";
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
    const vm = toSessionSummaryVM(session({ ended_at: null }), rec, skill(), 8);
    expect(vm.timeTile).toBe("—");
    expect(vm.scoreTile).toBe("7/10"); // still reads stored score (FR-G1)
  });
});

describe("toSessionSummaryVM — happy path (FR-G1/G2)", () => {
  const vm = toSessionSummaryVM(session(), rec, skill(), 8);

  it("score tile reads the STORED score, not a recompute (FR-G1)", () => {
    expect(vm.scoreTile).toBe("7/10");
    expect(vm.scoreCorrect).toBe(7);
    expect(vm.scoreTotal).toBe(10);
  });

  it("mastery-delta tile is signed percent (FR-G1)", () => {
    expect(vm.masteryDeltaTile).toBe("+8%");
  });

  it("negative mastery delta keeps its sign", () => {
    const down = toSessionSummaryVM(session(), rec, skill(), -3);
    expect(down.masteryDeltaTile).toBe("-3%");
  });

  it("a sub-half negative delta rounds to +0%, never -0%", () => {
    // -0.4 rounds to 0; the tile must read "+0%" (Math.round(-0.4) === -0, so
    // choosing the sign from the raw delta would print a nonsensical "-0%").
    const flat = toSessionSummaryVM(session(), rec, skill(), -0.4);
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
