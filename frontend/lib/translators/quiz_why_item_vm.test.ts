/**
 * T25 / SEQ-2 / VOICE-5 — purpose card composer (L1).
 *
 * Honest annotation sourced from real session state: skill name (taxonomy),
 * difficulty (question metadata), position (session tally). VOICE-5: no
 * decorative or fabricated numbers, and no claim about interleaving/ordering
 * the scheduler doesn't guarantee (e.g. never "because you missed this last").
 */

import { describe, expect, it } from "vitest";
import { toQuizWhyItemVM, WHY_ITEM_EYEBROW } from "./quiz_why_item_vm";

describe("toQuizWhyItemVM — T25 purpose card (SEQ-2 / V11)", () => {
  it("composes labeled purpose card with skill + difficulty + position", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 3,
      position: 2,
      total: 15,
    });
    expect(vm.eyebrow).toBe(WHY_ITEM_EYEBROW);
    expect(vm.body).toContain("Opening in Punctuation at difficulty 3");
    expect(vm.body).toContain("item 2 of 15 reviewed items");
    expect(vm.line).toContain(WHY_ITEM_EYEBROW);
  });

  it("uses 'the first of N' for position 1", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Usage",
      difficulty: 2,
      position: 1,
      total: 15,
    });
    expect(vm.body).toContain("the first of 15 reviewed items");
  });

  it("drops the denominator when the session is endless (total null)", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 2,
      position: 3,
      total: null,
    });
    expect(vm.body).toContain("reviewed item 3");
    expect(vm.body).not.toMatch(/of \d+ reviewed/);
  });

  it("omits the skill segment when the join failed (skillName null)", () => {
    const vm = toQuizWhyItemVM({
      skillName: null,
      difficulty: 3,
      position: 1,
      total: 15,
    });
    expect(vm.body).toContain("Opening at difficulty 3");
    expect(vm.body).not.toContain("null");
  });

  it("VOICE-5: never claims ordering/interleaving the scheduler doesn't guarantee", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 3,
      position: 2,
      total: 15,
    });
    const banned = /because|last time|you missed|next up|interleav/i;
    expect(banned.test(vm.body)).toBe(false);
  });

  it("VOICE-3: uses no engine vocabulary (ladder, rung, moment, wrong-pick)", () => {
    const vm = toQuizWhyItemVM({
      skillName: "Punctuation",
      difficulty: 3,
      position: 2,
      total: 15,
    });
    expect(vm.line).not.toMatch(
      /\b(ladder|rung|moment|wrong-pick|assertion rung)\b/i,
    );
  });
});
