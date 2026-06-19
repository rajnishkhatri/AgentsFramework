// Pure presentational leaf (F-R1): renders the nav tab group from a data table
// and reports selection via onSelect. No state, no lifecycle — the chrome hook
// at the shell level owns `activeTab`. Adding Cowork/Code later is appending to
// TABS, not a rewrite (UI refresh plan §D4).
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import type { SidebarTab } from "./use_sidebar_chrome";

const TABS: ReadonlyArray<{ id: SidebarTab; label: string }> = [
  { id: "chat", label: "Chat" },
];

export function SidebarTabBar(props: {
  activeTab: SidebarTab;
  onSelect?: (tab: SidebarTab) => void;
}): React.JSX.Element {
  return (
    <div
      role="tablist"
      aria-label="Sidebar sections"
      data-testid="sidebar-tabbar"
      className="flex items-center gap-1"
    >
      {TABS.map((tab) => {
        const selected = tab.id === props.activeTab;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            data-testid={`sidebar-tab-${tab.id}`}
            onClick={() => props.onSelect?.(tab.id)}
            className={cn(
              "px-2.5 py-1 rounded-sm text-sm cursor-pointer bg-transparent border-0",
              selected
                ? "text-fg font-medium bg-accent-light"
                : "text-muted hover:text-fg",
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
