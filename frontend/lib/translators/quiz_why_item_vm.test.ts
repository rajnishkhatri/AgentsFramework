/**
 * T16 / SEQ-2 / VOICE-5 — "why this item" line composer (L1).
 *
 * Honest annotation sourced from real session state: skill name (taxonomy),
 * difficulty (question metadata), position (session tally). VOICE-5: no
 * decorative or fabricated numbers, and no claim about interleaving/ordering
 * the scheduler doesn't guarantee (e.g. never "because you missed this last").
 */

import { describe, expect, it } from "vitest";
import { toQuizWhyItemVM } from "./quiz_why_item_vm";

describe("toQuizWhyItemVM — SEQ-2 honest sourcing + VOICE-5", () => {
  it("composes skill + difficulty + position-of-total from real state", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 3,
      position: 2,
      total: 15,
    });
    expect(vm.line).toContain("Punctuation");
    expect(vm.line).toContain("difficulty 3");
    expect(vm.line).toContain("Question 2 of 15");
  });

  it("drops the denominator when the session is endless (total null)", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 2,
      position: 3,
      total: null,
    });
    expect(vm.line).toContain("Question 3");
    expect(vm.line).not.toMatch(/of \d+/);
  });

  it("omits the skill segment when the join failed (skillName null)", () => {
    const vm = toQuizWhyItemVM({
      skillName: null,
      difficulty: 3,
      position: 1,
      total: 15,
    });
    expect(vm.line).toContain("Question 1 of 15");
    expect(vm.line).toContain("difficulty 3");
    expect(vm.line).not.toContain("null");
  });

  it("VOICE-5: never claims ordering/interleaving the scheduler doesn't guarantee", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 3,
      position: 2,
      total: 15,
    });
    const banned = /because|last time|you missed|we picked|next up|interleav/i;
    expect(banned.test(vm.line)).toBe(false);
  });

  it("VOICE-3: uses no engine vocabulary (ladder, rung, moment, wrong-pick)", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 3,
      position: 2,
      total: 15,
    });
    expect(vm.line).not.toMatch(/\b(ladder|rung|moment|wrong-pick|assertion rung)\b/i);
  });
});
