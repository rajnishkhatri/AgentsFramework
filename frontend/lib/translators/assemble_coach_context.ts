/**
 * assemble_coach_context — pin + Question + optional misses/mastery → wire
 * `input.coach_context` (BP-3 / design §4.1 / ADR-0012 / ADR-0030).
 *
 * Pure T1: omit dishonest optionals; never invent `misses_aggregate.window`.
 * Item pin: null when Question failed to load or id mismatches (FR-9/FR-10).
 * Lesson pin: skill-only context, question omitted (honest-null, E1b-D2).
 */

import type { CoachMode } from "./coach_context_sanitizer";
import type { CoachSurfacePin } from "./coach_surface_vm";
import type { Question, SkillState } from "../wire/engine_entities";

export interface CoachMissesAggregate {
  readonly skill_id: string;
  readonly missed: number;
  // window intentionally omitted this pass (C1a #2)
}

/** Item-scoped coach context (quiz pin). Wire-compatible with pre-D2 shape. */
export interface WireCoachContextItem {
  readonly context_kind?: "item";
  readonly mode: CoachMode;
  readonly question_id: string;
  readonly skill_id: string;
  readonly question: Question;
  /** ADR-0035: wrong letter for Gen2 choice-conditional ladder; omit when unknown. */
  readonly choice_letter?: "A" | "B" | "C" | "D";
  readonly misses_aggregate?: CoachMissesAggregate;
  readonly mastery_snapshot?: Readonly<Record<string, number>>;
}

/**
 * Lesson-scoped coach context (E1b-D2 / ADR-0030). `question_id`/`question`
 * omitted (honest-null) — never fabricated. Mode is always pre_submit.
 */
export interface WireCoachContextLesson {
  readonly context_kind: "lesson";
  readonly mode: "pre_submit";
  readonly skill_id: string;
  readonly misses_aggregate?: CoachMissesAggregate;
  readonly mastery_snapshot?: Readonly<Record<string, number>>;
}

export type WireCoachContext = WireCoachContextItem | WireCoachContextLesson;

export interface AssembleCoachContextArgs {
  readonly pin: CoachSurfacePin | null;
  readonly question: Question | null;
  /** Advisory only — BFF overwrites (FR-11 / ADR-0012). */
  readonly mode: CoachMode;
  /** null / undefined → omit misses_aggregate (FR-9). */
  readonly missesOnSkill?: number | null;
  /** Skill states for mastery_snapshot; omit when empty / unavailable. */
  readonly skillStates?: ReadonlyArray<SkillState> | null;
  /** ADR-0035: learner's selected wrong letter when known (Gen2 ladders). */
  readonly choiceLetter?: "A" | "B" | "C" | "D" | null;
}

function withOptionals<T extends WireCoachContext>(
  ctx: T,
  args: AssembleCoachContextArgs,
  skillId: string,
): T {
  const misses = args.missesOnSkill;
  const withMisses =
    misses != null && Number.isFinite(misses) && misses >= 0
      ? {
          ...ctx,
          misses_aggregate: { skill_id: skillId, missed: misses },
        }
      : ctx;

  const states = args.skillStates;
  if (states == null || states.length === 0) return withMisses as T;

  const snapshot: Record<string, number> = {};
  for (const s of states) {
    if (typeof s.mastery === "number" && Number.isFinite(s.mastery)) {
      snapshot[s.skill_id] = Math.round(s.mastery * 100);
    }
  }
  if (Object.keys(snapshot).length === 0) return withMisses as T;

  return { ...withMisses, mastery_snapshot: snapshot } as T;
}

/**
 * Build wire coach_context or null when honesty forbids a payload.
 * Mastery values are percent (0–100) from SkillState.mastery (0–1).
 */
export function assembleCoachContext(
  args: AssembleCoachContextArgs,
): WireCoachContext | null {
  const { pin, question } = args;
  if (pin == null) return null;

  if (pin.kind === "lesson") {
    // E1b-D2: skill-only seed. Skip questionId guard; omit question (honest-null).
    // Mode forced to pre_submit — no question_id ⇒ cannot assert post_feedback.
    const ctx: WireCoachContextLesson = {
      context_kind: "lesson",
      mode: "pre_submit",
      skill_id: pin.skillId,
    };
    return withOptionals(ctx, args, pin.skillId);
  }

  // Item branch (unchanged contract).
  if (question == null) return null;
  if (question.id !== pin.questionId) return null;

  const letter = args.choiceLetter;
  const ctx: WireCoachContextItem = {
    mode: args.mode,
    question_id: pin.questionId,
    skill_id: pin.skillId,
    question,
    ...(letter === "A" ||
    letter === "B" ||
    letter === "C" ||
    letter === "D"
      ? { choice_letter: letter }
      : {}),
  };
  return withOptionals(ctx, args, pin.skillId);
}
