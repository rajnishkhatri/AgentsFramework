/**
 * CollapsibleCoachAnswer — presentational coach answer row (ADR-0035 / FR-3/4/7).
 *
 * User question always visible. Only the coach body collapses. Streaming/error
 * force-expand and ignore toggle. Collapsed body uses `hidden` (out of AX tree);
 * toggling must not re-write prior content into the live region.
 */

import * as React from "react";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import { cn } from "@/lib/utils";
import type { CoachTurn } from "./use_coach";

function firstSentence(markdown: string): string {
  const trimmed = markdown.trim();
  if (!trimmed) return "Coach reply";
  const match = trimmed.match(/^(.+?[.!?])(\s|$)/);
  const sentence = (match?.[1] ?? trimmed).replace(/\s+/g, " ");
  return sentence.length > 120 ? `${sentence.slice(0, 117)}…` : sentence;
}

export function CollapsibleCoachAnswer(props: {
  turn: CoachTurn;
  expanded: boolean;
  onToggle: () => void;
  onRetry?: (() => void) | undefined;
}): React.JSX.Element {
  const { turn, expanded, onToggle, onRetry } = props;
  const { coach } = turn;
  const forced = coach.pending || coach.error;
  const isExpanded = forced || expanded;
  const bodyId = `coach-answer-body-${turn.id}`;
  const summary = firstSentence(coach.markdown);

  return (
    <div data-testid={`coach-turn-${turn.id}`} className="flex flex-col gap-2">
      <p className="self-end rounded-2xl bg-selected px-3 py-2 text-sm">
        {turn.user}
      </p>

      <div className="flex flex-col gap-1 rounded-2xl border border-border">
        {forced ? (
          <div className="px-3 pt-2 text-xs font-medium text-muted">Coach</div>
        ) : (
          <button
            type="button"
            data-testid={`coach-answer-toggle-${turn.id}`}
            aria-expanded={isExpanded}
            aria-controls={bodyId}
            onClick={onToggle}
            className={cn(
              "flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left text-sm",
              "hover:bg-selected/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            )}
          >
            <span aria-hidden="true" className="text-muted">
              {isExpanded ? "▾" : "▸"}
            </span>
            <span className="font-semibold text-fg">Coach</span>
            {!isExpanded ? (
              <span
                data-testid={`coach-answer-summary-${turn.id}`}
                className="min-w-0 flex-1 truncate text-sm text-muted"
              >
                {summary}
              </span>
            ) : (
              <span className="flex-1" />
            )}
          </button>
        )}

        <div
          id={bodyId}
          data-testid={`coach-answer-body-${turn.id}`}
          hidden={!isExpanded}
          className="flex flex-col gap-1 p-1"
        >
          <StreamingMarkdown text={coach.markdown} tone="plain" />
          {coach.pending ? (
            <span
              data-testid="coach-typing"
              className="px-3 pb-2 text-xs text-muted"
              aria-label="Coach is typing"
            >
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
    </div>
  );
}
