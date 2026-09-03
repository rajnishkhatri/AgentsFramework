/**
 * ADR-0041 exam answer-key posture — a literal code switch, not env-overridable.
 * Mirrors `services/governance/coach_test_mode_posture.py` for the frontend-only
 * exam module. Per-form `examKeyPosture` flips to `"server"` for asset-served
 * forms (ADR-0042 / FR-P2-5); Test-01 stays the recorded client-bundled exemption.
 */

import type { ExamFormDelivery } from "@/lib/wire/exam_entities";

export const EXAM_KEY_POSTURE = "client" as const;
export type ExamKeyPosture = typeof EXAM_KEY_POSTURE | "server";

export const ANSWER_BEARING_FIELDS = [
  "answer_letter",
  "per_choice_rationale",
  "why_correct_md",
  "why_tempted_md",
] as const;

/**
 * Per-form posture (FR-P2-5). asset-served ⇒ server-side keys;
 * client-bundled keeps the ADR-0041 Test-01 exemption. Code switch only —
 * not env-overridable.
 */
export function examKeyPosture(delivery: ExamFormDelivery): ExamKeyPosture {
  return delivery === "asset-served" ? "server" : "client";
}
