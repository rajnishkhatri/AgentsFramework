/**
 * Guaranteed-answer fallback (eval-UI F11, decision D-C).
 *
 * A completed run must never leave the answer slot empty -- the
 * GJ-F-008/GJ-012 inadmissible captures were runs that ended on a tool
 * call with no prose. The agent graph's continuation logic forces a
 * synthesis pass after tool results in the normal path; this fallback
 * covers the abnormal terminations (budget / max-steps / no-progress)
 * by synthesizing a deterministic recap from the trajectory.
 *
 * Returns `null` while streaming, on error (the error slot owns that
 * state), or when a real text answer exists. The caller renders the
 * result with a visible "summary generated from tool results" marker so
 * a synthesized recap is never mistaken for model prose.
 *
 * Imports: sibling translators only. No SDK, no React, no model call.
 */

import type { AssistantRunView } from "./run_view_reducer";
import { narrateTrajectory } from "./run_narration";

export function synthesizeFallbackAnswer(
  view: AssistantRunView,
): string | null {
  if (view.status !== "complete") return null;

  const hasText = view.segments.some(
    (s) => s.kind === "text" && s.text.trim().length > 0,
  );
  if (hasText) return null;

  const toolCount = view.segments.filter((s) => s.kind === "tool").length;
  if (toolCount === 0) {
    return "The run completed without producing any output.";
  }
  const recap = narrateTrajectory(view.segments).split(" → ").join(", ");
  const noun = toolCount === 1 ? "step" : "steps";
  return `Completed ${toolCount} ${noun}: ${recap}.`;
}
