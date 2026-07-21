/**
 * honest_coach_opener — grounded coach-page opener (FR-12 / C4 / T26 V22).
 *
 * Pure T1: when the transcript is empty, always return an honest opener.
 * Miss counts are cited only when real; never invents "of last 5" / window.
 * Empty pin / zero misses degrade to a Ready-when-you-are invite (AP-6).
 */

import type { CoachSurfacePin } from "@/lib/translators/coach_surface_vm";

export interface HonestCoachOpenerArgs {
  readonly pin: CoachSurfacePin | null;
  /** Real skill-scoped miss count; null = no honest aggregate. */
  readonly missesOnSkill: number | null;
  /**
   * Skill DISPLAY name for the miss-cluster claim (R2c / VOICE-3): the cluster
   * is a skill-scoped statement, so it names the skill label — never the item
   * label and never a raw `s-*` id. Unresolved → "this skill".
   */
  readonly skillLabel?: string | null;
  readonly transcriptEmpty: boolean;
}

const READY_BARE =
  "Ready when you are. Ask me anything — I never reveal the answer.";

/**
 * Returns opener markdown, or null when the transcript already has turns.
 */
export function honestCoachOpener(args: HonestCoachOpenerArgs): string | null {
  const { pin, missesOnSkill, skillLabel, transcriptEmpty } = args;
  if (!transcriptEmpty) return null;

  if (pin == null) return READY_BARE;

  const itemLabel = pin.label.trim() || "this";
  const skillScope = skillLabel?.trim() || "this skill";
  const n =
    missesOnSkill != null && Number.isFinite(missesOnSkill)
      ? Math.floor(missesOnSkill)
      : null;

  if (n != null && n >= 1) {
    return (
      `Ready when you are. Want to unpack the ${itemLabel} item, or work a fresh one? ` +
      `Your misses cluster on ${skillScope} (${n} miss${n === 1 ? "" : "es"}).`
    );
  }

  return `Ready when you are. Want to unpack the ${itemLabel} item, or work a fresh one?`;
}
