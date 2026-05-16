"use client";
/**
 * ReplayScrubber — client-side scrubber over already-fetched ReplayFrame[].
 *
 * Architecture invariant: NO new backend endpoint, NO graph re-execution.
 * Every datum on every frame comes from the events the page already loaded.
 * See `tests/architecture/test_replay_no_runtime_calls.test.ts`.
 *
 * Rule B1 — `'use client'` is justified: the only stateful UI is the slider
 * position.  Frames are passed in as props from the RSC parent.
 *
 * Rule FD4.SEM: the scrubber is a real `<input type="range">` with a label
 * and `aria-valuetext` describing the current frame.
 */
import { useId, useState } from "react";
import { cn } from "@/lib/utils";
import type { ReplayFrame } from "@/lib/translators/events_to_replay_frames";

export interface ReplayScrubberProps {
  frames: readonly ReplayFrame[];
}

export function ReplayScrubber({ frames }: ReplayScrubberProps) {
  const sliderId = useId();
  const [index, setIndex] = useState(0);

  if (frames.length === 0) {
    return (
      <div
        role="status"
        aria-label="No replay frames"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed border-border",
          "py-16 text-center text-sm text-muted-foreground",
        )}
      >
        <p className="font-medium">
          No events recorded — nothing to replay for this workflow.
        </p>
      </div>
    );
  }

  const safeIndex = Math.min(Math.max(index, 0), frames.length - 1);
  const current = frames[safeIndex]!;
  const positionLabel = `Frame ${safeIndex + 1} of ${frames.length}`;

  return (
    <div className="flex flex-col gap-4">
      <div
        className={cn(
          "flex flex-col gap-2 rounded-lg border border-border bg-card p-4",
        )}
      >
        <div className="flex items-baseline justify-between gap-3">
          <label
            htmlFor={sliderId}
            className="text-xs font-medium text-foreground"
          >
            Replay position
          </label>
          <span className="font-mono text-xs text-muted-foreground">
            {positionLabel}
          </span>
        </div>
        <input
          id={sliderId}
          type="range"
          min={0}
          max={frames.length - 1}
          value={safeIndex}
          step={1}
          onChange={(e) => setIndex(Number(e.target.value))}
          aria-valuetext={`${positionLabel} — ${current.event_type}`}
          className="w-full"
        />
        <div className="flex justify-between gap-2">
          <button
            type="button"
            onClick={() => setIndex(0)}
            disabled={safeIndex === 0}
            className={cn(
              "rounded-md border border-border px-2 py-1 text-xs font-medium",
              "hover:bg-accent hover:text-accent-foreground",
              "disabled:cursor-not-allowed disabled:opacity-40",
            )}
          >
            ⟪ Start
          </button>
          <button
            type="button"
            onClick={() => setIndex(Math.max(0, safeIndex - 1))}
            disabled={safeIndex === 0}
            className={cn(
              "rounded-md border border-border px-2 py-1 text-xs font-medium",
              "hover:bg-accent hover:text-accent-foreground",
              "disabled:cursor-not-allowed disabled:opacity-40",
            )}
          >
            ◀ Prev
          </button>
          <button
            type="button"
            onClick={() =>
              setIndex(Math.min(frames.length - 1, safeIndex + 1))
            }
            disabled={safeIndex === frames.length - 1}
            className={cn(
              "rounded-md border border-border px-2 py-1 text-xs font-medium",
              "hover:bg-accent hover:text-accent-foreground",
              "disabled:cursor-not-allowed disabled:opacity-40",
            )}
          >
            Next ▶
          </button>
          <button
            type="button"
            onClick={() => setIndex(frames.length - 1)}
            disabled={safeIndex === frames.length - 1}
            className={cn(
              "rounded-md border border-border px-2 py-1 text-xs font-medium",
              "hover:bg-accent hover:text-accent-foreground",
              "disabled:cursor-not-allowed disabled:opacity-40",
            )}
          >
            End ⟫
          </button>
        </div>
      </div>

      <FrameSnapshot frame={current} />
    </div>
  );
}

function FrameSnapshot({ frame }: { frame: ReplayFrame }) {
  return (
    <article
      data-testid="replay-snapshot"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-card p-4 text-xs",
      )}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">
          Snapshot at frame {frame.index + 1}
        </h3>
        <span className="font-mono text-[10px] text-muted-foreground">
          {frame.event_type}
        </span>
      </header>
      <dl className="grid grid-cols-2 gap-3">
        <div>
          <dt className="text-muted-foreground">Active agent</dt>
          <dd className="mt-0.5 font-mono text-foreground">
            {frame.active_agent ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Active model</dt>
          <dd className="mt-0.5 font-mono text-foreground">
            {frame.active_model ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Current step</dt>
          <dd className="mt-0.5 tabular-nums text-foreground">
            {frame.current_step ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Timestamp</dt>
          <dd className="mt-0.5 font-mono text-foreground">
            {frame.timestamp ?? "—"}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Last input</dt>
          <dd
            className={cn(
              "mt-0.5 max-h-32 overflow-auto rounded border border-border",
              "bg-background p-2 font-mono text-foreground",
            )}
          >
            {frame.last_input ?? "—"}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Last output</dt>
          <dd
            className={cn(
              "mt-0.5 max-h-32 overflow-auto rounded border border-border",
              "bg-background p-2 font-mono text-foreground",
            )}
          >
            {frame.last_output ?? "—"}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Params</dt>
          <dd
            className={cn(
              "mt-0.5 max-h-32 overflow-auto rounded border border-border",
              "bg-background p-2 font-mono text-foreground",
            )}
          >
            {Object.keys(frame.params).length === 0
              ? "—"
              : JSON.stringify(frame.params, null, 2)}
          </dd>
        </div>
      </dl>
    </article>
  );
}
