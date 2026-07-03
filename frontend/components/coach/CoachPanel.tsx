/**
 * CoachPanel — the iPad quiz split's persistent live coach panel (FR-J3/J3a).
 *
 * Rendered beside the quiz item on the iPad surface. Two contracts:
 *
 *  - ONE thread (FR-J3): the transcript is the SHARED coach thread
 *    (`coach_thread_store` via `useCoach`) — a message typed here appears in
 *    the full Coach screen's thread, because they are two views of one store.
 *    The composer copy is item-scoped ("Ask about this item…").
 *
 *  - Two-tier hint (FR-J3a × FR-D5): "One more nudge" reveals the next
 *    REVIEWED ladder rung IN THE PANEL — rung 2 (conceptual) then rung 3
 *    (directive) — distinct from the item card's own Get-a-hint (rung 1).
 *    The rungs come from the ADR-0014 read seam, whose verifier cascade is
 *    the non-reveal guarantee; there is NO rung 4, so an exhausted ladder
 *    disables the control (FR-B5: disabled, never dead).
 *
 * Per F-R1 the panel owns no run logic (useCoach) and no hint logic (the
 * ladder arrives as props from the quiz page's already-loaded item). Callers
 * should key the panel by question id so nudge state resets per item.
 */

// B1: 'use client' required — nudge disclosure state + the useCoach store view.
"use client";

import * as React from "react";
import type { AgentRuntimeClient } from "@/lib/ports/agent_runtime_client";
import type { Hint } from "@/lib/wire/engine_entities";
import { CoachView } from "./CoachView";
import { useCoach } from "./use_coach";

export function CoachPanel(props: {
  runtime: AgentRuntimeClient;
  /** The current item's reviewed ladder (rung-ascending, ADR-0014). */
  hintLadder: ReadonlyArray<Hint>;
}): React.JSX.Element {
  const { runtime, hintLadder } = props;
  const { turns, busy, ask, retry } = useCoach(runtime);

  // Tier 1 (the probe rung) belongs to the item card's Get-a-hint; the panel's
  // deeper tiers are the rungs above it.
  const deeperRungs = React.useMemo(
    () => hintLadder.filter((h) => h.rung > 1),
    [hintLadder],
  );
  const [revealed, setRevealed] = React.useState(0);
  const exhausted = revealed >= deeperRungs.length;

  return (
    <aside
      data-testid="coach-panel"
      aria-label="Live coach panel"
      className="flex w-80 shrink-0 flex-col gap-3 rounded-[16px] border border-border bg-surface p-4"
    >
      <header className="flex flex-col gap-0.5">
        <p className="text-sm font-semibold">Socratic mode · watching this item</p>
        <p className="text-xs text-muted">
          Same coach, same thread — pick it up on the Coach screen anytime.
        </p>
      </header>

      <div className="flex flex-col gap-2">
        {deeperRungs.slice(0, revealed).map((h) => (
          <p
            key={h.id}
            data-testid={`panel-nudge-${h.rung}`}
            className="rounded-[13px] bg-accent-light px-3 py-2 text-sm"
          >
            {h.body_md}
          </p>
        ))}
        <button
          type="button"
          data-testid="one-more-nudge"
          disabled={exhausted}
          title={
            exhausted
              ? "That's every nudge for this one — try the coach below."
              : undefined
          }
          onClick={() => setRevealed((n) => Math.min(n + 1, deeperRungs.length))}
          className="min-h-11 w-fit rounded-full border border-dashed border-accent px-4 py-2 text-sm text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          One more nudge
        </button>
      </div>

      <div className="min-h-0 flex-1">
        <CoachView
          turns={turns}
          busy={busy}
          onAsk={ask}
          onRetry={retry}
          placeholder="Ask about this item…"
        />
      </div>
    </aside>
  );
}
