/**
 * Phase 0.5 — bucket_card_vm (FR-C3, L2 contract, TAP-2 table-driven).
 *
 * Pure map: (Skill, SkillState | null, nowISO) → BucketCardVM for the dashboard
 * skill-mastery grid. Each card shows bucket name, mastery %, share-of-test %,
 * the bucket accent var (drives the colored progress bar), and a "Due" badge.
 *
 * Purity (T1): "now" is an injected ISO string, never read from the clock, so
 * the map is deterministic. Failure/edge rows first (Anti-Pattern 6): a skill
 * with no SkillState yet (brand-new learner) → mastery UNKNOWN (masteryKnown
 * false), not due, no crash — never a fabricated 0% (Epic F FR-4 honest-null).
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
  it("brand-new skill (no SkillState) → mastery UNKNOWN, not due, no crash", () => {
    const vm = toBucketCardVM(skill(), null, NOW);
    expect(vm.masteryKnown).toBe(false);
    expect(vm.due).toBe(false);
    expect(vm.name).toBe("Punctuation");
    expect(vm.accentVar).toBe("--color-bucket-punctuation");
  });

  it("due_at in the future → not due", () => {
    const vm = toBucketCardVM(skill(), state({ due_at: "2027-01-01T00:00:00.000Z" }), NOW);
    expect(vm.due).toBe(false);
  });

  // Epic F FR-4 (honest-null): when LearnerReadRepo.listSkillState returns no row
  // for a skill (brand-new learner, or the read port not yet wired), mastery is
  // UNKNOWN — the VM carries `masteryKnown: false` so the view renders an honest
  // "no data" form, NEVER a fabricated 0% bar (indistinguishable from a real 0).
  // This is the guard the spec promised (progress_screen_vm.test.ts::
  // bucket_missing_mastery_is_honest_not_zero) but that never existed; it lives
  // here, at the translator seam where the fabrication was born.
  it("bucket_missing_mastery_is_honest_not_zero", () => {
    const vm = toBucketCardVM(skill(), null, NOW);
    expect(vm.masteryKnown).toBe(false);
    // masteryPct is still a number (0) for type-stability, but the KNOWN flag —
    // not the number — is what the view must gate on. A consumer that reads
    // masteryPct without checking masteryKnown is the P-4 bug.
    expect(vm.due).toBe(false);
  });
});

describe("toBucketCardVM — happy path", () => {
  it("maps mastery 0..1 → integer percent and carries share + accent", () => {
    const vm = toBucketCardVM(skill(), state({ mastery: 0.42 }), NOW);
    expect(vm.masteryKnown).toBe(true);
    expect(vm.masteryPct).toBe(42);
    expect(vm.shareOfTestPct).toBe(20);
    expect(vm.accentVar).toBe("--color-bucket-punctuation");
    expect(vm.skillId).toBe("s-punc");
  });

  it("a genuine mastery of 0 is KNOWN (distinct from absent SkillState)", () => {
    // The honest-null point: a real, measured mastery of exactly 0 (learner has
    // attempted and missed everything) is DIFFERENT from "no data yet". Both
    // have masteryPct 0; only the absent case has masteryKnown false.
    const vm = toBucketCardVM(skill(), state({ mastery: 0 }), NOW);
    expect(vm.masteryKnown).toBe(true);
    expect(vm.masteryPct).toBe(0);
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
