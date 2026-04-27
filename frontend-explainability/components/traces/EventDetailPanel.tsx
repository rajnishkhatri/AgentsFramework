/**
 * EventDetailPanel — pure presentational component.
 *
 * Renders the inputs/outputs from the event `details` dict.  Used by the
 * client-side wrapper to surface whichever frame the user clicked on the
 * timeline.
 */
import { cn } from "@/lib/utils";
import type { TimelineFrame } from "@/lib/translators/event_to_timeline";

export interface EventDetailPanelProps {
  frame: TimelineFrame | null;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
  return `${(ms / 60_000).toFixed(2)} min`;
}

export function EventDetailPanel({ frame }: EventDetailPanelProps) {
  if (frame === null) {
    return (
      <aside
        aria-label="Event details"
        className={cn(
          "flex h-full flex-col rounded-lg border border-dashed border-border",
          "p-4 text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium text-foreground">No event selected</p>
        <p className="mt-1 text-xs">
          Click any bar on the timeline to inspect its inputs and outputs.
        </p>
      </aside>
    );
  }

  const detailEntries = Object.entries(frame.details);

  return (
    <aside
      aria-label="Event details"
      className={cn(
        "flex h-full flex-col gap-3 rounded-lg border border-border bg-card p-4 text-sm",
      )}
    >
      <header className="flex flex-col gap-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {frame.kind}
        </p>
        <h3 className="text-base font-semibold text-foreground">{frame.label}</h3>
      </header>

      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted-foreground">id</dt>
        <dd className="font-mono text-foreground">{frame.id}</dd>

        <dt className="text-muted-foreground">parent</dt>
        <dd className="font-mono text-foreground">{frame.parentId ?? "—"}</dd>

        <dt className="text-muted-foreground">starts at</dt>
        <dd className="text-foreground">{formatDuration(frame.startMs)}</dd>

        <dt className="text-muted-foreground">duration</dt>
        <dd className="text-foreground">{formatDuration(frame.durationMs)}</dd>

        <dt className="text-muted-foreground">step</dt>
        <dd className="text-foreground">{frame.step ?? "—"}</dd>
      </dl>

      <section>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Details
        </h4>
        {detailEntries.length === 0 ? (
          <p className="text-xs text-muted-foreground">No details captured.</p>
        ) : (
          <dl
            className={cn(
              "grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 rounded border border-border",
              "bg-background p-2 text-xs",
            )}
          >
            {detailEntries.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="break-all font-mono text-foreground">
                  {renderValue(value)}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </aside>
  );
}

function renderValue(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
