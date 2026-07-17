/**
 * HintLadderList — expandable revealed-nudge rows (Direction 2b / FR-5/14).
 *
 * Zone B block only — "+ One more nudge" lives in Zone C (Q-C1).
 */

"use client";

import * as React from "react";
import { StreamingMarkdown } from "@/components/chat/StreamingMarkdown";
import { cn } from "@/lib/utils";
import type { Hint } from "@/lib/wire/engine_entities";
import { useExpandableList } from "./use_expandable_list";

export const NUDGE_EXHAUSTED_REASON =
  "You've used all available nudges for this item";

/** Header prompt + optional detail (remainder). Avoids duplicating the prompt in the body. */
function splitPromptAndDetail(bodyMd: string): {
  prompt: string;
  detail: string;
} {
  const trimmed = bodyMd.trim().replace(/\s+/g, " ");
  if (!trimmed) return { prompt: "Nudge", detail: "" };
  // Prefer first sentence; ladder prompts are short by design (6–10 words).
  const match = trimmed.match(/^(.+?[.!?])(?:\s+([\s\S]+))?$/);
  if (!match) return { prompt: trimmed, detail: "" };
  return { prompt: match[1] ?? trimmed, detail: (match[2] ?? "").trim() };
}

export function HintLadderList(props: {
  revealed: ReadonlyArray<Hint>;
  totalDeeper: number;
}): React.JSX.Element | null {
  const { revealed, totalDeeper } = props;
  const ids = React.useMemo(
    () => revealed.map((h) => h.id),
    [revealed],
  );
  const { isExpanded, toggle } = useExpandableList({
    ids,
    autoExpandNewest: true,
  });

  const [announce, setAnnounce] = React.useState("");
  const prevCount = React.useRef(0);
  React.useEffect(() => {
    if (revealed.length > prevCount.current) {
      const n = revealed.length;
      setAnnounce(`Nudge ${n} revealed`);
      const t = window.setTimeout(() => setAnnounce(""), 1000);
      prevCount.current = revealed.length;
      return () => window.clearTimeout(t);
    }
    prevCount.current = revealed.length;
    return undefined;
  }, [revealed.length]);

  if (totalDeeper === 0 && revealed.length === 0) return null;

  return (
    <div data-testid="hint-ladder-list" className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
          Hint ladder
        </h3>
        <span className="text-xs text-muted">
          {revealed.length} of {totalDeeper} used
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {revealed.map((h, i) => {
          const open = isExpanded(h.id);
          const indexLabel = String(i + 1).padStart(2, "0");
          const bodyId = `ladder-body-${h.id}`;
          const { prompt, detail } = splitPromptAndDetail(h.body_md);
          const expandable = detail.length > 0;
          const tinted = expandable && open;
          return (
            <li key={h.id}>
              {/* One card: header + detail share border/radius/tint (no floating white body). */}
              <div
                className={cn(
                  "overflow-hidden rounded-md border border-border",
                  tinted && "border-accent/40 bg-[var(--color-accent-light)]",
                )}
              >
                <button
                  type="button"
                  data-testid={`panel-nudge-${h.rung}`}
                  aria-expanded={expandable ? open : undefined}
                  aria-controls={expandable ? bodyId : undefined}
                  onClick={() => {
                    if (expandable) toggle(h.id);
                  }}
                  className={cn(
                    "flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left text-sm",
                    "hover:bg-selected/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className="text-xs text-accent transition-transform duration-150 motion-reduce:transition-none"
                  >
                    {expandable ? (open ? "▾" : "▸") : "·"}
                  </span>
                  <span className="font-mono text-xs text-accent">
                    {indexLabel}
                  </span>
                  <span className="min-w-0 flex-1 text-fg">{prompt}</span>
                </button>
                {expandable ? (
                  <div
                    id={bodyId}
                    hidden={!open}
                    className="px-3.5 pb-3 pl-[34px] text-sm leading-[1.55] text-fg"
                  >
                    <StreamingMarkdown text={detail} tone="plain" />
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announce}
      </div>
    </div>
  );
}
