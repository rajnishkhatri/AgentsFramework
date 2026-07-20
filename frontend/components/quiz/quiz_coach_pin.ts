/**
 * quiz_coach_pin — pure map from the live Quiz item → coach_thread_store pin.
 *
 * Desktop Quiz has no CoachPanel, so sidebar "Coach" used to open cold / stale
 * unless the learner had just hit Ask-the-coach. This helper is the shared
 * label + mode contract so the quiz page can sync the store on every item /
 * phase change (same chrome iPad CoachPanel already writes).
 */

import type { CoachMode } from "@/lib/translators/coach_context_sanitizer";
import type { CoachSurfacePin } from "@/lib/translators/coach_surface_vm";

export function toQuizCoachPin(args: {
  questionId: string;
  skillId: string;
  /** Skill DISPLAY name; null when the taxonomy join is unresolved (R2b). */
  skillName: string | null;
  /** 1-based QuizProgress position. */
  position: number;
  phase: "answering" | "reviewing";
}): { pin: CoachSurfacePin; mode: CoachMode } {
  // VOICE-3 (R2b): the label is learner-facing (Current-item line + opener) —
  // skill display name only; unresolved → bare position (AP-6), never `s-*`.
  const name = args.skillName?.trim();
  return {
    pin: {
      kind: "item",
      questionId: args.questionId,
      skillId: args.skillId,
      label: name ? `Q${args.position} · ${name}` : `Q${args.position}`,
    },
    mode: args.phase === "reviewing" ? "post_feedback" : "pre_submit",
  };
}
