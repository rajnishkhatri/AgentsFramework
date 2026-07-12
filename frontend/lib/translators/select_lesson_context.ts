/**
 * select_lesson_context — LearnerLessonState → LessonContext (E1a FR-4 / FR-5).
 *
 * Pure T1 translator. Deterministic if/else over primitives; imports wire/ +
 * locally-defined E1a types only. No I/O, no React, no SDK.
 *
 * Ladder (design contract §4.1 / D1):
 *   requested                           → requested
 *   firstExposure || masteryPct == null → newSkill
 *   masteryPct >= 80 && dueMisses == 0  → refresher
 *   dueMisses > 0                       → returning
 *   else                                → newSkill
 */

export type LessonContext = "newSkill" | "returning" | "refresher";

export interface LearnerLessonState {
  /** No SkillState row for this skill. */
  readonly firstExposure: boolean;
  /** SkillState.mastery mapped to 0..100; null when no row. */
  readonly masteryPct: number | null;
  /** Count of due misses for this skill (boolean-ish: >0 routes returning). */
  readonly dueMisses: number;
  /** Explicit pick — overrides diagnosis (AL-17). */
  readonly requested?: LessonContext;
}

/**
 * Select the lesson context for `/learn/skill`.
 * A misconception tag on a non-due miss is NOT an input — only `dueMisses > 0`
 * routes to `returning` (FR-5 / AC-3).
 */
export function selectLessonContext(state: LearnerLessonState): LessonContext {
  if (state.requested != null) return state.requested;
  if (state.firstExposure || state.masteryPct == null) return "newSkill";
  if (state.masteryPct >= 80 && state.dueMisses === 0) return "refresher";
  if (state.dueMisses > 0) return "returning";
  return "newSkill";
}
