/**
 * bucket_card_vm — Skill (+ its SkillState) → BucketCardVM (FR-C3).
 *
 * Pure T1 map for the dashboard skill-mastery grid: one card per bucket showing
 * name, mastery %, share-of-test %, the bucket accent var (drives the colored
 * progress bar + 30–32% border tint, FR-A3), and a "Due" badge.
 *
 * Purity (T1): "due" is computed against an INJECTED `nowISO`, never `Date.now()`
 * — the map is deterministic and testable without faking the clock. A skill with
 * no `SkillState` yet (brand-new learner) maps to 0% mastery and not-due.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type { Skill, SkillState } from "../wire/engine_entities";

export interface BucketCardVM {
  readonly skillId: string;
  readonly name: string;
  /** Mastery as an integer 0..100 (SkillState.mastery is 0..1). */
  readonly masteryPct: number;
  readonly shareOfTestPct: number;
  /** The `--color-bucket-*` custom property the card scopes to (FR-A3). */
  readonly accentVar: string;
  /** True when the skill is due for review (`due_at <= now`). */
  readonly due: boolean;
}

export function toBucketCardVM(
  skill: Skill,
  skillState: SkillState | null,
  nowISO: string,
): BucketCardVM {
  const mastery = skillState?.mastery ?? 0;
  const due =
    skillState != null &&
    Date.parse(skillState.due_at) <= Date.parse(nowISO);

  return {
    skillId: skill.id,
    name: skill.name,
    masteryPct: Math.round(mastery * 100),
    shareOfTestPct: skill.share_of_test_pct,
    accentVar: skill.accent_var,
    due,
  };
}
