/**
 * assemble_coach_context — pin + Question + optional misses/mastery → wire
 * `input.coach_context` (BP-3 / design §4.1 / ADR-0012).
 *
 * Pure T1: omit dishonest optionals; never invent `misses_aggregate.window`.
 * Returns null when pin is absent or Question failed to load (FR-9/FR-10).
 */

import type { CoachMode } from "./coach_context_sanitizer";
import type { CoachSurfacePin } from "./coach_surface_vm";
import type { Question, SkillState } from "../wire/engine_entities";

export interface CoachMissesAggregate {
  readonly skill_id: string;
  readonly missed: number;
  // window intentionally omitted this pass (C1a #2)
}

export interface WireCoachContext {
  readonly mode: CoachMode;
  readonly question_id: string;
  readonly skill_id: string;
  readonly question: Question;
  readonly misses_aggregate?: CoachMissesAggregate;
  readonly mastery_snapshot?: Readonly<Record<string, number>>;
}

export interface AssembleCoachContextArgs {
  readonly pin: CoachSurfacePin | null;
  readonly question: Question | null;
  /** Advisory only — BFF overwrites (FR-11 / ADR-0012). */
  readonly mode: CoachMode;
  /** null / undefined → omit misses_aggregate (FR-9). */
  readonly missesOnSkill?: number | null;
  /** Skill states for mastery_snapshot; omit when empty / unavailable. */
  readonly skillStates?: ReadonlyArray<SkillState> | null;
}

/**
 * Build wire coach_context or null when honesty forbids a payload.
 * Mastery values are percent (0–100) from SkillState.mastery (0–1).
 */
export function assembleCoachContext(
  args: AssembleCoachContextArgs,
): WireCoachContext | null {
  const { pin, question, mode } = args;
  if (pin == null || question == null) return null;
  if (question.id !== pin.questionId) return null;

  const ctx: WireCoachContext = {
    mode,
    question_id: pin.questionId,
    skill_id: pin.skillId,
    question,
  };

  const misses = args.missesOnSkill;
  const withMisses: WireCoachContext =
    misses != null && Number.isFinite(misses) && misses >= 0
      ? {
          ...ctx,
          misses_aggregate: { skill_id: pin.skillId, missed: misses },
        }
      : ctx;

  const states = args.skillStates;
  if (states == null || states.length === 0) return withMisses;

  const snapshot: Record<string, number> = {};
  for (const s of states) {
    if (typeof s.mastery === "number" && Number.isFinite(s.mastery)) {
      snapshot[s.skill_id] = Math.round(s.mastery * 100);
    }
  }
  if (Object.keys(snapshot).length === 0) return withMisses;

  return { ...withMisses, mastery_snapshot: snapshot };
}
