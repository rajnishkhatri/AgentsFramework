/**
 * ADR-0041 exam answer-key posture — a literal code switch, not env-overridable.
 * Mirrors `services/governance/coach_test_mode_posture.py` for the frontend-only
 * exam module. Flip to `"server"` in a reviewed diff when a DB-served official
 * form lands (delivery trigger) or results gain stakes.
 */

export const EXAM_KEY_POSTURE = "client" as const;
export type ExamKeyPosture = typeof EXAM_KEY_POSTURE | "server";

export const ANSWER_BEARING_FIELDS = [
  "answer_letter",
  "per_choice_rationale",
  "why_correct_md",
  "why_tempted_md",
] as const;
