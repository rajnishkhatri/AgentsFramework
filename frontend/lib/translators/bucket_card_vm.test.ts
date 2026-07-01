/**
 * Phase 0.5 — bucket_card_vm (FR-C3, L2 contract, TAP-2 table-driven).
 *
 * Pure map: (Skill, SkillState | null, nowISO) → BucketCardVM for the dashboard
 * skill-mastery grid. Each card shows bucket name, mastery %, share-of-test %,
 * the bucket accent var (drives the colored progress bar), and a "Due" badge.
 *
 * Purity (T1): "now" is an injected ISO string, never read from the clock, so
 * the map is deterministic. Failure/edge rows first (Anti-Pattern 6): a skill
 * with no SkillState yet (brand-new learner) → 0% mastery, not due, no crash.
 */

import { describe, expect, it } from "vitest";
import { toBucketCardVM } from "./bucket_card_vm";
import type { Skill, SkillState } from "../wire/engine_entities";

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

function state(over: Partial<SkillState> = {}): SkillState {
  return {
    subject: "act-english",
    skill_id: "s-punc",
    learner_id: "maya",
    mastery: 0.42,
    last_seen: "2026-06-20T10:00:00.000Z",
    fsrs_stability: 3,
    fsrs_difficulty: 5,
    due_at: "2026-06-25T10:00:00.000Z",
    fsrs_card: null,
    ...over,
  };
}

const NOW = "2026-06-30T00:00:00.000Z";

describe("toBucketCardVM — edge/failure rows first", () => {
  it("brand-new skill (no SkillState) → 0% mastery, not due, no crash", () => {
    const vm = toBucketCardVM(skill(), null, NOW);
    expect(vm.masteryPct).toBe(0);
    expect(vm.due).toBe(false);
    expect(vm.name).toBe("Punctuation");
    expect(vm.accentVar).toBe("--color-bucket-punctuation");
  });

  it("due_at in the future → not due", () => {
    const vm = toBucketCardVM(skill(), state({ due_at: "2027-01-01T00:00:00.000Z" }), NOW);
    expect(vm.due).toBe(false);
  });

  // ADR-0011 §0.6d lock: when LearnerReadRepo.listSkillState returns no row for
  // a skill (brand-new learner, or the read port not yet wired), the dashboard
  // grid renders 0% / not-due WITHOUT the VM reaching across a boundary to seed
  // one. Locks the placeholder path so a future edit can't silently start
  // fabricating mastery. `masteryPct` is exactly the integer 0, not "0"/NaN.
  it("absent SkillState → masteryPct is exactly 0 (placeholder path, no boundary crossing)", () => {
    const vm = toBucketCardVM(skill(), null, NOW);
    expect(vm.masteryPct).toBe(0);
    expect(Object.is(vm.masteryPct, 0)).toBe(true); // not -0, not NaN
    expect(vm.due).toBe(false);
  });
});

describe("toBucketCardVM — happy path", () => {
  it("maps mastery 0..1 → integer percent and carries share + accent", () => {
    const vm = toBucketCardVM(skill(), state({ mastery: 0.42 }), NOW);
    expect(vm.masteryPct).toBe(42);
    expect(vm.shareOfTestPct).toBe(20);
    expect(vm.accentVar).toBe("--color-bucket-punctuation");
    expect(vm.skillId).toBe("s-punc");
  });

  it("due_at at/earlier than now → due badge shown", () => {
    const vm = toBucketCardVM(skill(), state({ due_at: "2026-06-25T10:00:00.000Z" }), NOW);
    expect(vm.due).toBe(true);
  });

  it("rounds mastery to the nearest integer percent", () => {
    expect(toBucketCardVM(skill(), state({ mastery: 0.6667 }), NOW).masteryPct).toBe(67);
    expect(toBucketCardVM(skill(), state({ mastery: 0.005 }), NOW).masteryPct).toBe(1);
  });
});
