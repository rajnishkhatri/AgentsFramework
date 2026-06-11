/**
 * Pure phase derivation (eval-UI F8): AssistantRunView -> run phase.
 *
 * The liveness indicator's single source of truth. Phases derive ONLY
 * from event-fed view state -- never timers (Determinism Theater is an
 * auto-reject): `connecting → thinking → tool → writing → done|error`.
 *
 * Imports: sibling translators only.
 */

import type { AssistantRunView } from "./run_view_reducer";

export type RunPhase =
  | "connecting"
  | "thinking"
  | "tool"
  | "writing"
  | "done"
  | "error";

export function deriveRunPhase(view: AssistantRunView): RunPhase {
  if (view.status === "error") return "error";
  if (view.status === "complete") return "done";
  if (view.runId === null) return "connecting";
  const last = view.segments[view.segments.length - 1];
  if (!last) return "thinking";
  if (last.kind === "tool" && last.request.status === "running") return "tool";
  if (last.kind === "text") return "writing";
  // Last tool finished, next activity not yet started.
  return "thinking";
}
