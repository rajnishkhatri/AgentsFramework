/**
 * Transparent-recall indicator (Phase 3, research §4) -- the Claude/ChatGPT
 * "searched past conversations" affordance. Shows, in the chat, how many
 * memories the agent recalled for the current turn.
 *
 * Sourced from the `MEMORY_RECALLED` governance carrier (count only -- NEVER
 * content; the privacy invariant holds end to end). This component is purely
 * presentational (F-R1): it takes the count as a typed prop. The parent wires
 * the count from the recall domain event / run view; this file invents no
 * transport and reads no state.
 *
 * Renders nothing when count is 0 (no recall happened) so it never adds noise
 * to a memory-off or no-hit run.
 *
 * Deterministic hook: data-testid="recall-indicator".
 */

import * as React from "react";
import { Sparkles } from "lucide-react";

export function RecallIndicator(props: {
  count: number;
}): React.JSX.Element | null {
  if (!Number.isFinite(props.count) || props.count <= 0) return null;
  const label =
    props.count === 1
      ? "Recalled 1 memory about you"
      : `Recalled ${props.count} memories about you`;
  return (
    <div
      data-testid="recall-indicator"
      className="flex items-center gap-1.5 text-xs text-accent font-medium"
    >
      {/* House style: line SVG icon, no emoji (frozen). The recall affordance
         reads in the accent to match the frozen .recall treatment. */}
      <Sparkles className="size-3.5" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
