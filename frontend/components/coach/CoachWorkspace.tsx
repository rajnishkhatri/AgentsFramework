/**
 * CoachWorkspace — standalone `/learn/coach` composition shell (BP-1.5).
 *
 * Presentational (F-R1): header Back / Wrap-up, layout variants (desktop rail
 * vs iPad strip), chrome without chips + chips beside composer (C3). Page
 * supplies navigation handlers and surface VM; no router import here so L1
 * tests stay free of next/navigation.
 */

import * as React from "react";
import { Composer } from "@/components/chat/Composer";
import { cn } from "@/lib/utils";
import type { CoachSurfaceVM } from "@/lib/translators/coach_surface_vm";
import type { CoachTurn } from "./use_coach";
import { CoachChrome, CoachChips, type CoachChromeLayout } from "./CoachChrome";
import { CoachView } from "./CoachView";

export function CoachWorkspace(props: {
  readonly vm: CoachSurfaceVM;
  readonly turns: ReadonlyArray<CoachTurn>;
  readonly busy: boolean;
  readonly onAsk: (body: string) => void | Promise<void>;
  readonly onRetry: () => void;
  readonly onBack: () => void;
  readonly onWrapUp: () => void;
  /** `rail` = desktop two-column; `strip` = iPad standalone header-strip. */
  readonly layout: Exclude<CoachChromeLayout, "stacked">;
  /** Optional honest opener (FR-12) when transcript empty + pin+misses. */
  readonly openerMarkdown?: string | null;
}): React.JSX.Element {
  const {
    vm,
    turns,
    busy,
    onAsk,
    onRetry,
    onBack,
    onWrapUp,
    layout,
    openerMarkdown = null,
  } = props;
  const isRail = layout === "rail";

  return (
    <div
      data-testid="coach-workspace"
      data-layout={layout}
      className="flex h-full flex-col gap-4"
    >
      {/* Zone A — chrome + nav (fullscreen host; FR-18) */}
      <div data-testid="coach-zone-a" className="flex shrink-0 flex-col gap-3">
        <header
          data-testid="coach-header"
          className="flex items-center justify-between gap-3"
        >
          <button
            type="button"
            data-testid="coach-back"
            onClick={onBack}
            className="text-sm text-muted hover:text-fg"
          >
            ← Back
          </button>
          <button
            type="button"
            data-testid="coach-wrap-up"
            onClick={onWrapUp}
            className="text-sm font-medium text-accent hover:underline"
          >
            Wrap up session →
          </button>
        </header>
        <div
          data-testid="coach-context-column"
          className={cn(isRail ? "w-64 shrink-0" : "w-full shrink-0")}
        >
          <CoachChrome
            vm={vm}
            busy={busy}
            onAsk={onAsk}
            layout={layout}
            showChips={false}
          />
        </div>
      </div>

      <div
        data-testid="coach-workspace-body"
        className={cn(
          "flex min-h-0 flex-1",
          isRail ? "flex-row gap-4" : "mx-auto w-full max-w-[600px] flex-col",
        )}
      >
        <div
          data-testid="coach-chat-column"
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          {/* Zone B scrolls; Zone C chips+composer pinned (same contract as CoachPanel) */}
          <div
            data-testid="coach-zone-b"
            className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain"
          >
            <CoachView
              turns={turns}
              busy={busy}
              onAsk={onAsk}
              onRetry={onRetry}
              openerMarkdown={openerMarkdown}
              showComposer={false}
            />
          </div>
          <div
            data-testid="coach-zone-c"
            className="flex shrink-0 flex-col gap-3 border-t border-border px-1 py-3"
          >
            <CoachChips seeds={vm.chips} busy={busy} onAsk={onAsk} />
            <Composer
              onSend={(body) => onAsk(body)}
              busy={busy}
              placeholder="Ask the coach…"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
