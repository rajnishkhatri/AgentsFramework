/**
 * today_focus_vm — (NextItem, Skill) → TodayFocusVM (FR-C2).
 *
 * Pure T1 map for the dashboard Today's-focus banner: the weakest+due skill
 * (the Scheduler's `NextItem` pick) resolved against its `Skill` for the display
 * name + accent, with the primary CTA that routes to Quiz.
 *
 * Null-safe: a cold start (no due item) yields `present:false` so the dashboard
 * hides the banner rather than crashing.
 *
 * Imports `wire/` only. No I/O, no React, no SDK.
 */

import type { NextItem, Skill } from "../wire/engine_entities";

interface TodayFocusEmpty {
  readonly present: false;
}

interface TodayFocusPresent {
  readonly present: true;
  readonly skillId: string;
  readonly skillName: string;
  readonly accentVar: string;
  readonly questionId: string;
  readonly ctaLabel: string;
}

export type TodayFocusVM = TodayFocusEmpty | TodayFocusPresent;

const START_ADAPTIVE_CTA = "Start adaptive session";

export function toTodayFocusVM(
  next: NextItem | null,
  skill: Skill | null,
): TodayFocusVM {
  if (next == null || skill == null) {
    return { present: false };
  }
  return {
    present: true,
    skillId: skill.id,
    skillName: skill.name,
    accentVar: skill.accent_var,
    questionId: next.question_id,
    ctaLabel: START_ADAPTIVE_CTA,
  };
}
