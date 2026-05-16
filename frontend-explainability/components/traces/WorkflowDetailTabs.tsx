"use client";
/**
 * WorkflowDetailTabs — single client-side state holder for the /traces/[wf_id]
 * route's tab selection (Timeline / Cascade / Replay).
 *
 * Rule B1 — `'use client'` is justified: the only stateful UI on this route
 * is the tab selection.  Each tab body is rendered once at mount; switching
 * tabs is a CSS visibility toggle to preserve any future per-tab scroll
 * position.
 *
 * Rule FD4.SEM: tabs are real `<button role="tab">` elements; the active tab
 * sets `aria-selected` and `tabIndex={0}` per WAI-ARIA Authoring Practices.
 */
import { useId, useState } from "react";
import { cn } from "@/lib/utils";

export type DetailTab = "timeline" | "cascade" | "replay";

const TAB_LABEL: Record<DetailTab, string> = {
  timeline: "Timeline",
  cascade: "Cascade Analysis",
  replay: "Replay",
};

const ALL_TABS: readonly DetailTab[] = ["timeline", "cascade", "replay"];

export interface WorkflowDetailTabsProps {
  timeline: React.ReactNode;
  cascade: React.ReactNode;
  replay: React.ReactNode;
  initial?: DetailTab;
}

export function WorkflowDetailTabs({
  timeline,
  cascade,
  replay,
  initial = "timeline",
}: WorkflowDetailTabsProps) {
  const [active, setActive] = useState<DetailTab>(initial);
  const id = useId();

  return (
    <div className="flex flex-col gap-3">
      <div
        role="tablist"
        aria-label="Workflow detail views"
        className={cn(
          "flex gap-1 rounded-lg border border-border bg-card p-1 text-sm",
        )}
      >
        {ALL_TABS.map((tab) => {
          const isActive = active === tab;
          return (
            <button
              key={tab}
              type="button"
              role="tab"
              id={`${id}-tab-${tab}`}
              aria-selected={isActive}
              aria-controls={`${id}-panel-${tab}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActive(tab)}
              className={cn(
                "flex-1 rounded-md px-3 py-1.5 font-medium transition-colors",
                isActive
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              {TAB_LABEL[tab]}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel-timeline`}
        aria-labelledby={`${id}-tab-timeline`}
        hidden={active !== "timeline"}
      >
        {timeline}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel-cascade`}
        aria-labelledby={`${id}-tab-cascade`}
        hidden={active !== "cascade"}
      >
        {cascade}
      </div>
      <div
        role="tabpanel"
        id={`${id}-panel-replay`}
        aria-labelledby={`${id}-tab-replay`}
        hidden={active !== "replay"}
      >
        {replay}
      </div>
    </div>
  );
}
