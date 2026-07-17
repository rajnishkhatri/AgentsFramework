/**
 * CoachChrome — shared coach workspace chrome (B1 / ADR-0025 + BP-1.5).
 *
 * Presentational leaf (F-R1): renders a `CoachSurfaceVM` as rail / strip /
 * stacked context, optional current-item / history lines, display-only mode
 * labels (D5a — no mode override), and optional quick-reply chips that seed
 * `onAsk`. Used by both `/learn/coach` and iPad `CoachPanel` (D6).
 *
 * Layout variants (C3 / FR-1, FR-3):
 *  - `rail`    — desktop left context column (`coach-layout-rail`)
 *  - `strip`   — iPad standalone header strip (no left-rail column)
 *  - `stacked` — iPad quiz panel / default (no left-rail column)
 *
 * When the host places chips beside the composer, pass `showChips={false}`.
 *
 * No engine I/O, no SDK, no mode mutation.
 */

import * as React from "react";
import { cn } from "@/lib/utils";
import type { CoachSurfaceVM } from "@/lib/translators/coach_surface_vm";

export type CoachChromeLayout = "rail" | "strip" | "stacked";

/** Quick-reply chips — host may place beside the composer (C3 / FR-3). */
export function CoachChips(props: {
  readonly seeds: ReadonlyArray<string>;
  readonly busy: boolean;
  readonly onAsk: (body: string) => void | Promise<void>;
}): React.JSX.Element {
  const { seeds, busy, onAsk } = props;
  return (
    <div
      data-testid="coach-chips"
      role="group"
      aria-label="Quick replies"
      // Horizontal scroll (not wrap) so Zone C stays short on narrow panels (FR-9/10).
      className="flex flex-nowrap gap-2 overflow-x-auto overscroll-x-contain"
    >
      {seeds.map((seed) => (
        <button
          key={seed}
          type="button"
          data-testid="coach-chip"
          disabled={busy}
          onClick={() => {
            if (!busy) void onAsk(seed);
          }}
          className={cn(
            "shrink-0 rounded-[13px] border border-border bg-surface px-3 py-1.5 text-xs",
            "hover:bg-accent-light hover:text-accent disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {seed}
        </button>
      ))}
    </div>
  );
}

export function CoachChrome(props: {
  readonly vm: CoachSurfaceVM;
  readonly busy: boolean;
  readonly onAsk: (body: string) => void | Promise<void>;
  /** Surface composition variant; default `stacked` (B1 / panel compat). */
  readonly layout?: CoachChromeLayout;
  /** When false, chips are omitted so the host can place them by the composer. */
  readonly showChips?: boolean;
}): React.JSX.Element {
  const {
    vm,
    busy,
    onAsk,
    layout = "stacked",
    showChips = true,
  } = props;

  return (
    <div
      data-testid="coach-chrome"
      data-layout={layout}
      className={cn(
        "flex flex-col gap-3",
        layout === "rail" && "coach-layout-rail",
      )}
      aria-label="Coach workspace"
    >
      <div
        data-testid="coach-rail"
        className="flex items-center justify-between gap-2"
      >
        <div className="flex flex-col gap-0.5">
          <p className="text-sm font-semibold">{vm.railTitle}</p>
          <p className="flex items-center gap-1.5 text-xs text-muted">
            <span
              aria-hidden
              className="inline-block size-1.5 rounded-full bg-[var(--color-success)]"
            />
            {vm.railStatus}
          </p>
        </div>
      </div>

      {vm.currentItemLine ? (
        <p
          data-testid="coach-current-item"
          className="text-sm text-muted"
        >
          {vm.currentItemLine}
        </p>
      ) : null}

      {vm.historyLine ? (
        <p data-testid="coach-history" className="text-sm text-muted">
          {vm.historyLine}
        </p>
      ) : null}

      <div
        data-testid="coach-modes"
        role="group"
        aria-label="Coach modes"
        className={cn(
          "flex gap-2",
          // Stacked panel is narrow — wrap blows Zone A and starves the log (W9).
          layout === "stacked"
            ? "flex-nowrap overflow-x-auto overscroll-x-contain"
            : "flex-wrap",
        )}
      >
        {vm.modes.map((m) => (
          <span
            key={m.id}
            data-active={m.active ? "true" : "false"}
            aria-current={m.active ? "true" : undefined}
            className={cn(
              "shrink-0 rounded-[13px] border px-2.5 py-1 text-xs",
              m.active
                ? "border-accent bg-accent-light text-accent"
                : "border-border bg-surface text-muted",
            )}
          >
            {m.label}
          </span>
        ))}
      </div>

      {showChips ? (
        <CoachChips seeds={vm.chips} busy={busy} onAsk={onAsk} />
      ) : null}
    </div>
  );
}
