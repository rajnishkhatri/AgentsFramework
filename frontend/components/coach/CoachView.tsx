/**
 * CoachView — the Coach chat screen (Screen 4, FR-F1..F6).
 *
 * Presentational only (F-R1): renders coach turns (from `useCoach`) + a
 * composer. No engine port, no run logic, no SDK. The whole transcript lives in
 * a single persistent `role="log" aria-live="polite"` region (U4) — streaming
 * tokens append there without interrupting a screen reader. A streaming turn
 * shows a typing indicator (FR-F3); a terminal error shows a RETRY affordance,
 * never a stuck spinner (FR-F4).
 *
 * `onAsk`/`onRetry` are optional so the view is SSR-testable without wiring; the
 * page supplies them from `useCoach`.
 */

import * as React from "react";
import { Composer } from "@/components/chat/Composer";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import type { CoachTurn } from "./use_coach";

function CoachBubble(props: {
  turn: CoachTurn;
  onRetry?: (() => void) | undefined;
}): React.JSX.Element {
  const { turn, onRetry } = props;
  const { coach } = turn;
  return (
    <div data-testid={`coach-turn-${turn.id}`} className="flex flex-col gap-2">
      <p className="self-end rounded-2xl bg-selected px-3 py-2 text-sm">{turn.user}</p>
      <div className="flex flex-col gap-1 rounded-2xl border border-border p-1">
        <StreamingMarkdown text={coach.markdown} />
        {coach.pending ? (
          <span data-testid="coach-typing" className="px-3 pb-2 text-xs text-muted" aria-label="Coach is typing">
            Coach is thinking&hellip;
          </span>
        ) : null}
        {coach.error && coach.canRetry ? (
          <button
            type="button"
            data-testid="coach-retry"
            onClick={onRetry}
            className="mx-3 mb-2 inline-flex w-fit items-center rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-selected"
          >
            Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function CoachView(props: {
  turns: ReadonlyArray<CoachTurn>;
  busy: boolean;
  onAsk?: (body: string) => void | Promise<void>;
  onRetry?: () => void;
  /** Composer placeholder override — the iPad panel scopes it to the item
   *  ("Ask about this item…", FR-J3); default is the full-screen copy. */
  placeholder?: string;
  /**
   * Optional honest opener (FR-12 / C4) — coach-only bubble when transcript
   * is empty and pin+misses exist. Hosts compute via `honestCoachOpener`.
   */
  openerMarkdown?: string | null;
}): React.JSX.Element {
  const {
    turns,
    busy,
    onAsk,
    onRetry,
    placeholder = "Ask the coach…",
    openerMarkdown = null,
  } = props;
  return (
    <div className="flex h-full flex-col gap-4">
      <section
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label="Coach conversation"
        className="flex flex-1 flex-col gap-4 overflow-y-auto"
      >
        {openerMarkdown && turns.length === 0 ? (
          <div
            data-testid="coach-opener"
            className="flex flex-col gap-1 rounded-2xl border border-border p-3"
          >
            <StreamingMarkdown text={openerMarkdown} />
          </div>
        ) : null}
        {turns.map((t) => (
          <CoachBubble key={t.id} turn={t} onRetry={onRetry} />
        ))}
      </section>
      <Composer
        onSend={(body) => onAsk?.(body)}
        busy={busy}
        placeholder={placeholder}
      />
    </div>
  );
}
