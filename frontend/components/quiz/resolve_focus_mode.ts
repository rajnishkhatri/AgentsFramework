/**
 * resolve_focus_mode — the pure FR-6 (S2) decision behind the Quiz page's
 * `?focus=` search param. Kept React-free (the F-R1 split, twin of
 * `openQuizItem`/`runQuizSubmit` in use_quiz.ts): the Quiz page fetches the
 * subject's skills, hands their ids in here, and forwards the result to
 * `openSession`. No engine port, no I/O, no React.
 *
 * Contract:
 *   - A `focus` that names a KNOWN skill id opens a DRILL on that skill.
 *   - A null, empty, or UNKNOWN `focus` falls back to ADAPTIVE with no focus —
 *     a bad/absent param never errors and never drills a nonexistent skill
 *     (spec §6 edge cases).
 */

import type { SessionMode } from "@/lib/wire/engine_entities";

/** The subset of `OpenSessionArgs` this decision produces (mode + optional focus). */
export interface FocusMode {
  readonly mode: SessionMode;
  /** Present only for a drill on a known skill. */
  readonly focus?: string;
}

/**
 * Resolve the `?focus=` param against the set of known skill ids.
 *
 * @param focus     the raw `focus` search-param value (or null when absent)
 * @param skillIds  the subject's known skill ids (`Skill.id`, e.g. "s-punc")
 */
export function resolveFocusMode(
  focus: string | null,
  skillIds: readonly string[],
): FocusMode {
  if (focus != null && focus.length > 0 && skillIds.includes(focus)) {
    return { mode: "drill", focus };
  }
  return { mode: "adaptive" };
}
