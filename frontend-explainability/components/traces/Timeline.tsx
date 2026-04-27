/**
 * Timeline — Server Component (no 'use client').
 *
 * Renders the per-event waterfall lanes as accessible bars.  Visx /
 * SVG-charting is intentionally deferred until v1.1 (the brainstorm calls for
 * Visx but Sprint 1's Definition of Done caps SDK additions to the seven UI
 * libs from the reviewer's allowlist).  The DOM-only fallback below renders
 * the same data and keeps the route MVP-shippable.
 *
 * The detail panel is interactive — that lives in `TimelineWithDetail` which
 * carries the 'use client' boundary.
 */
import { cn } from "@/lib/utils";
import type { TimelineFrame, TimelineColor } from "@/lib/translators/event_to_timeline";

export interface TimelineProps {
  frames: readonly TimelineFrame[];
  /** Optional currently-selected frame id (passed by the client wrapper). */
  selectedId?: string | null;
  /** Optional click handler — only set by the client wrapper. */
  onSelect?: (id: string) => void;
}

const COLOR_TOKEN: Record<TimelineColor, string> = {
  neutral: "bg-muted",
  primary: "bg-primary",
  info: "bg-blue-500",
  success: "bg-green-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
};

const MIN_BAR_WIDTH_PX = 6;

export function Timeline({ frames, selectedId, onSelect }: TimelineProps) {
  if (frames.length === 0) {
    return (
      <div
        role="status"
        aria-label="No events"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-16 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">No events recorded for this workflow.</p>
      </div>
    );
  }

  const totalMs = Math.max(
    1,
    Math.max(...frames.map((f) => f.startMs + f.durationMs)),
  );

  return (
    <ol
      aria-label="Workflow event timeline"
      className={cn("space-y-1 rounded-lg border border-border bg-card p-3")}
    >
      {frames.map((frame) => {
        const widthPct = Math.max(
          (frame.durationMs / totalMs) * 100,
          MIN_BAR_WIDTH_PX / 6,
        );
        const offsetPct = (frame.startMs / totalMs) * 100;
        const isSelected = selectedId === frame.id;
        const Tag = onSelect ? "button" : "div";
        return (
          <li
            key={frame.id}
            className={cn(
              "grid grid-cols-[12rem_1fr] items-center gap-3 rounded-md px-2 py-1",
              isSelected && "bg-accent/60",
            )}
          >
            <span
              className="truncate text-xs font-medium text-foreground"
              title={frame.label}
            >
              {frame.label}
            </span>
            <div className="relative h-5">
              <Tag
                {...(Tag === "button"
                  ? {
                      type: "button" as const,
                      onClick: () => onSelect?.(frame.id),
                      "aria-pressed": isSelected,
                      "aria-label": `${frame.label} — open details`,
                    }
                  : {})}
                className={cn(
                  "absolute top-0 h-5 rounded",
                  COLOR_TOKEN[frame.color],
                  Tag === "button" && "transition-opacity hover:opacity-80",
                  isSelected && "ring-2 ring-foreground ring-offset-1",
                )}
                style={{
                  left: `${offsetPct}%`,
                  width: `${widthPct}%`,
                  minWidth: `${MIN_BAR_WIDTH_PX}px`,
                }}
              />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
