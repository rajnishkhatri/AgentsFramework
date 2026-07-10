/**
 * honest_coach_opener — optional C-6 seed bubble (BP-3c / FR-12 / C4).
 *
 * Pure T1: one opener ONLY when pin + real misses count + empty transcript.
 * Copy may cite N; never invents "of last 5" / window.
 */

import type { CoachSurfacePin } from "@/lib/translators/coach_surface_vm";

export interface HonestCoachOpenerArgs {
  readonly pin: CoachSurfacePin | null;
  /** Real skill-scoped miss count; null = no honest aggregate. */
  readonly missesOnSkill: number | null;
  readonly transcriptEmpty: boolean;
}

/**
 * Returns opener markdown, or null when the gate fails (leave log empty).
 */
export function honestCoachOpener(args: HonestCoachOpenerArgs): string | null {
  const { pin, missesOnSkill, transcriptEmpty } = args;
  if (!transcriptEmpty) return null;
  if (pin == null) return null;
  if (missesOnSkill == null || !Number.isFinite(missesOnSkill) || missesOnSkill < 1) {
    return null;
  }
  const n = Math.floor(missesOnSkill);
  const label = pin.label.trim() || "this skill";
  return (
    `I see ${n} miss${n === 1 ? "" : "es"} on ${label}. ` +
    `Want to unpack what keeps tripping you up?`
  );
}
