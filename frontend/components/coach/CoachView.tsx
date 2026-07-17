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
 * Wide-layout: Zone B scrolls (`flex-1 min-h-0 overflow-y-auto`); Zone C
 * composer is a `shrink-0` sibling. Answers collapse via CollapsibleCoachAnswer
 * (ADR-0035 / FR-3/4/7/11).
 *
 * `onAsk`/`onRetry` are optional so the view is SSR-testable without wiring; the
 * page supplies them from `useCoach`.
 */

"use client";

import * as React from "react";
import { Composer } from "@/components/chat/Composer";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import { CollapsibleCoachAnswer } from "./CollapsibleCoachAnswer";
import type { CoachTurn } from "./use_coach";
import { useExpandableList } from "./use_expandable_list";

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
  /**
   * When false, omit the Composer (host pins it in Zone C — CoachPanel).
   * Default true for standalone / backward-compat.
   */
  showComposer?: boolean;
  /** Imperative focus target for Feedback→coach bridge (FR-14). */
  composerFocusRef?: React.RefObject<HTMLTextAreaElement | null>;
}): React.JSX.Element {
  const {
    turns,
    busy,
    onAsk,
    onRetry,
    placeholder = "Ask the coach…",
    openerMarkdown = null,
    showComposer = true,
    composerFocusRef,
  } = props;
  const turnIds = React.useMemo(() => turns.map((t) => t.id), [turns]);
  const forceExpandedIds = React.useMemo(() => {
    const forced = new Set<string>();
    for (const t of turns) {
      if (t.coach.pending || t.coach.error) forced.add(t.id);
    }
    return forced;
  }, [turns]);
  const { isExpanded, toggle } = useExpandableList({
    ids: turnIds,
    forceExpandedIds,
    autoCollapseOnComplete: true,
  });

  // Embedded in CoachPanel Zone B: flow with the panel's single scroll.
  // Standalone (composer on): keep an internal scroll region for the log.
  const embedded = !showComposer;

  return (
    <div
      className={
        embedded
          ? "flex min-w-0 flex-col gap-4"
          : "flex h-full min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-hidden"
      }
    >
      <section
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label="Coach conversation"
        data-testid="coach-log"
        className={
          embedded
            ? "flex flex-col gap-4"
            : "flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain"
        }
      >
        {openerMarkdown && turns.length === 0 ? (
          <div
            data-testid="coach-opener"
            className="flex flex-col gap-1 rounded-2xl border border-border p-3"
          >
            <StreamingMarkdown text={openerMarkdown} tone="plain" />
          </div>
        ) : null}
        {turns.map((t) => (
          <CollapsibleCoachAnswer
            key={t.id}
            turn={t}
            expanded={isExpanded(t.id)}
            onToggle={() => toggle(t.id)}
            onRetry={onRetry}
          />
        ))}
      </section>
      {showComposer ? (
        <div data-testid="coach-zone-c" className="shrink-0">
          <Composer
            onSend={(body) => onAsk?.(body)}
            busy={busy}
            placeholder={placeholder}
            {...(composerFocusRef != null
              ? { textareaRef: composerFocusRef }
              : {})}
          />
        </div>
      ) : null}
    </div>
  );
}
