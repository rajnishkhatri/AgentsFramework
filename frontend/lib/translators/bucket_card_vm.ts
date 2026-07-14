/**
 * bucket_card_vm — Skill (+ its SkillState) → BucketCardVM (FR-C3).
 *
 * Pure T1 map for the dashboard skill-mastery grid: one card per bucket showing
 * name, mastery %, share-of-test %, the bucket accent var (drives the colored
 * progress bar + 30–32% border tint, FR-A3), and a "Due" badge.
 *
 * Purity (T1): "due" is computed against an INJECTED `nowISO`, never `Date.now()`
 * — the map is deterministic and testable without faking the clock.
 *
 * Honest-null (Epic F FR-4): a skill with no `SkillState` yet (brand-new learner,
 * or the read port unwired) has UNKNOWN mastery — `masteryKnown` is `false` and
 * the view renders an honest "no data" form, NEVER a fabricated 0% bar. A genuine
 * measured mastery of 0 is distinct: `masteryKnown` `true`, `masteryPct` 0. The
 * KNOWN flag, not the number, is the signal consumers gate on. See the
 * honest-null translator convention in `docs/adr/decisions.md`.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type { Skill, SkillState } from "../wire/engine_entities";

export interface BucketCardVM {
  readonly skillId: string;
  readonly name: string;
  /**
   * True when a `SkillState` exists and `masteryPct` reflects a real measurement.
   * False for a brand-new/unwired skill: mastery is UNKNOWN and the view must
   * render "no data", not a 0% bar (Epic F FR-4). `masteryPct` is still a number
   * (0) for type-stability, but this flag — not the number — is the signal.
   */
  readonly masteryKnown: boolean;
  /** Mastery as an integer 0..100 (SkillState.mastery is 0..1). Meaningful only when `masteryKnown`. */
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
  const masteryKnown = skillState != null;
  const mastery = skillState?.mastery ?? 0;
  const due =
    skillState != null &&
    Date.parse(skillState.due_at) <= Date.parse(nowISO);

  return {
    skillId: skill.id,
    name: skill.name,
    masteryKnown,
    masteryPct: Math.round(mastery * 100),
    shareOfTestPct: skill.share_of_test_pct,
    accentVar: skill.accent_var,
    due,
  };
}
