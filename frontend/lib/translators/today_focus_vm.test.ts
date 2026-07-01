/**
 * Phase 0.5 — today_focus_vm (FR-C2, L2 contract, TAP-2 table-driven).
 *
 * Pure map: (NextItem, Skill) → TodayFocusVM for the dashboard Today's-focus
 * banner — the weakest+due skill with a primary CTA "Start adaptive session"
 * that routes to Quiz.
 *
 * Edge row first (Anti-Pattern 6): no focus available (nothing due / cold start)
 * → a null-safe "empty" banner the dashboard can hide, not a crash.
 */

import { describe, expect, it } from "vitest";
import { toTodayFocusVM } from "./today_focus_vm";
import type { NextItem, Skill } from "../wire/engine_entities";

function skill(over: Partial<Skill> = {}): Skill {
  return {
    id: "s-punc",
    subject: "act-english",
    key: "punctuation",
    name: "Punctuation",
    share_of_test_pct: 20,
    accent_var: "--color-bucket-punctuation",
    description: "Commas, semicolons, apostrophes.",
    order: 1,
    ...over,
  };
}

describe("toTodayFocusVM — edge row first", () => {
  it("no next item (cold start) → empty banner (present:false), no crash", () => {
    const vm = toTodayFocusVM(null, null);
    expect(vm.present).toBe(false);
  });
});

describe("toTodayFocusVM — happy path (FR-C2)", () => {
  const next: NextItem = { skill_id: "s-punc", question_id: "q1" };

  it("names the focus skill + carries its accent + the Quiz CTA", () => {
    const vm = toTodayFocusVM(next, skill());
    if (!vm.present) throw new Error("expected a present banner");
    expect(vm.skillId).toBe("s-punc");
    expect(vm.skillName).toBe("Punctuation");
    expect(vm.accentVar).toBe("--color-bucket-punctuation");
    expect(vm.ctaLabel).toBe("Start adaptive session");
  });

  it("carries the question id so the CTA can open the exact item", () => {
    const vm = toTodayFocusVM(next, skill());
    if (!vm.present) throw new Error("expected a present banner");
    expect(vm.questionId).toBe("q1");
  });
});
