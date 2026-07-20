/**
 * coach_surface_vm — host chrome inputs → CoachSurfaceVM (B1 / ADR-0025).
 *
 * Pure T1 map for shared coach workspace chrome (rail, current-item, history
 * trust line, D5a mode labels, quick-reply chips). Hosts assemble inputs
 * (pin, skill-scoped misses count, derived CoachMode); this map owns copy and
 * the display-only 3→2 mode map so CoachChrome stays presentational (F-R1).
 *
 * History honesty (FR-1/FR-6): `missesOnSkill === null` → omit line; never
 * invent "of last 5". Mode labels never write to the run body (ADR-0012).
 *
 * Imports coach_context_sanitizer for CoachMode only. No I/O, no React, no SDK.
 */

import type { CoachMode } from "./coach_context_sanitizer";

/** Prototype C-7 chip seeds — static composer/`onAsk` seeds (clarify C5). */
export const COACH_CHIP_SEEDS: readonly string[] = [
  "Explain the rule simply",
  "Give me a similar item",
  "Show my comma pattern",
] as const;

export type CoachSurfacePin =
  | {
      readonly kind: "item";
      readonly questionId: string;
      readonly skillId: string;
      readonly label: string;
    }
  | {
      readonly kind: "lesson";
      readonly skillId: string;
      readonly label: string;
    };

export interface CoachSurfaceInputs {
  readonly mode: CoachMode;
  /** null = honest absent current-item (standalone until B2). */
  readonly pin: CoachSurfacePin | null;
  /**
   * Skill-scoped miss count from AttemptRepo.misses + QuestionRepo join, or
   * null when no honest aggregate (no pin / load failure / not yet loaded).
   */
  readonly missesOnSkill: number | null;
  /** Display name for the skill; skillId used when null. */
  readonly skillLabel: string | null;
  readonly chipSeeds: readonly string[];
}

export type CoachModeDisplayId = "socratic" | "deep_dive" | "misconception";

export interface CoachModeDisplay {
  readonly id: CoachModeDisplayId;
  readonly label: string;
  readonly active: boolean;
}

export interface CoachSurfaceVM {
  readonly railTitle: string;
  readonly railStatus: string;
  readonly currentItemLine: string | null;
  readonly historyLine: string | null;
  readonly modes: ReadonlyArray<CoachModeDisplay>;
  readonly chips: ReadonlyArray<string>;
}

function modeDisplays(mode: CoachMode): ReadonlyArray<CoachModeDisplay> {
  return [
    {
      id: "socratic",
      label: "In-drill Socratic",
      active: mode === "pre_submit",
    },
    {
      id: "deep_dive",
      label: "Post-answer deep-dive",
      active: mode === "post_feedback",
    },
    {
      id: "misconception",
      label: "Misconception summary",
      active: false,
    },
  ];
}

function historyLine(
  _pin: CoachSurfacePin | null,
  missesOnSkill: number | null,
  skillLabel: string | null,
): string | null {
  if (missesOnSkill === null) return null;
  // VOICE-3 (R2a): an unresolved display name degrades to "this skill" —
  // the raw `s-*` id is engine vocabulary and never learner-facing.
  const scope = skillLabel?.trim() || "this skill";
  return `Sees your history: ${missesOnSkill} misses on ${scope}`;
}

export function toCoachSurfaceVM(inputs: CoachSurfaceInputs): CoachSurfaceVM {
  const { mode, pin, missesOnSkill, skillLabel, chipSeeds } = inputs;
  // Lesson pins are skill-only — no current-item panel (E1b-D2 FR-8).
  const currentItemLine =
    pin != null && pin.kind === "item"
      ? `Current item: ${pin.label}`
      : null;
  return {
    railTitle: "Your Coach",
    railStatus: "Adaptive · always on",
    currentItemLine,
    historyLine: historyLine(pin, missesOnSkill, skillLabel),
    modes: modeDisplays(mode),
    chips: [...chipSeeds],
  };
}
