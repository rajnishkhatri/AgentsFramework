/**
 * SidebarPanel — the left-rail CHROME wrapper (UI refresh Phase 1-4).
 *
 * Pure presentational leaf (F-R1): all state (collapsed / search / activeTab)
 * is owned by `useSidebarChrome` at the shell level and passed in as props;
 * thread DATA is owned by `useChatSidebars`. This component only lays out the
 * affordances — collapse toggle, tab bar, New chat, Search — above the existing
 * `ThreadSidebar` list, and forwards every interaction via callbacks.
 *
 * Collapse animates the panel's own WIDTH (w-64 ↔ w-12), not the parent grid
 * template (cross-browser-unreliable); the collapsible body is clipped and
 * aria-hidden when collapsed. The transition is disabled under
 * `prefers-reduced-motion` (design doc §5).
 *
 * Icons are lucide line SVGs (Menu / Search / Plus) — house style, no emoji.
 */

"use client";

import * as React from "react";
import { Menu, Plus, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ThreadState } from "@/lib/wire/agent_protocol";
import { ThreadSidebar } from "./ThreadSidebar";
import { SidebarTabBar } from "./SidebarTabBar";
import type { SidebarTab } from "./use_sidebar_chrome";

export function SidebarPanel(props: {
  /** Threads to list — already filtered by the active search query upstream. */
  threads: ReadonlyArray<ThreadState>;
  activeThreadId?: string;
  now?: number; // injectable for deterministic grouping in tests
  // chrome state
  collapsed: boolean;
  searchOpen: boolean;
  searchQuery: string;
  activeTab: SidebarTab;
  // chrome callbacks
  onToggleCollapsed: () => void;
  onToggleSearch: () => void;
  onSearchQueryChange: (q: string) => void;
  onCloseSearch: () => void;
  onSelectTab: (tab: SidebarTab) => void;
  onNewChat: () => void;
  // thread callbacks (forwarded to ThreadSidebar)
  onSelectThread?: (id: string) => void;
  onRenameThread?: (id: string, title: string) => void;
  onDeleteThread?: (id: string) => void;
}): React.JSX.Element {
  const isFiltered = props.searchQuery.trim().length > 0;

  return (
    <div
      data-testid="sidebar-panel"
      className={cn(
        "h-full overflow-hidden bg-bg",
        "transition-[width] duration-200 ease-out motion-reduce:transition-none",
        props.collapsed ? "w-12" : "w-64",
      )}
    >
      {/* Row 1: collapse toggle + tab bar */}
      <div className="flex items-center gap-2 p-2">
        <button
          type="button"
          data-testid="sidebar-toggle"
          aria-label={props.collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!props.collapsed}
          aria-controls="sidebar-body"
          onClick={props.onToggleCollapsed}
          className="text-fg bg-transparent border-0 cursor-pointer leading-none px-1 hover:text-accent flex items-center"
        >
          <Menu className="size-5" aria-hidden="true" />
        </button>
        {!props.collapsed ? (
          <SidebarTabBar
            activeTab={props.activeTab}
            onSelect={props.onSelectTab}
          />
        ) : null}
      </div>

      {/* Collapsible body: hidden from the a11y tree + clipped when collapsed. */}
      <div
        id="sidebar-body"
        data-testid="sidebar-body"
        aria-hidden={props.collapsed}
        className={cn(
          "grid gap-2 transition-opacity duration-150 ease-out motion-reduce:transition-none",
          props.collapsed
            ? "opacity-0 pointer-events-none"
            : "opacity-100",
        )}
      >
        {/* Row 2: New chat */}
        <div className="px-2">
          <button
            type="button"
            data-testid="new-thread"
            onClick={props.onNewChat}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-sm text-sm text-fg bg-surface border border-border cursor-pointer hover:border-accent"
          >
            <Plus className="size-4 text-accent" aria-hidden="true" />
            New chat
          </button>
        </div>

        {/* Row 3: Search toggle + (when open) the filter input */}
        <div className="px-2 grid gap-1">
          <button
            type="button"
            data-testid="sidebar-search-toggle"
            aria-expanded={props.searchOpen}
            aria-controls="sidebar-search"
            onClick={props.onToggleSearch}
            className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-sm text-muted bg-transparent border-0 cursor-pointer hover:text-fg"
          >
            <Search className="size-4" aria-hidden="true" />
            Search
          </button>
          {props.searchOpen ? (
            <input
              id="sidebar-search"
              data-testid="sidebar-search-input"
              type="text"
              aria-label="Search conversations"
              placeholder="Search conversations…"
              value={props.searchQuery}
              onChange={(e) => props.onSearchQueryChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") props.onCloseSearch();
              }}
              className="w-full px-3 py-2 rounded-md text-sm text-fg bg-surface border border-border focus:outline-none focus:border-accent"
            />
          ) : null}
        </div>

        {/* Etched groove closing the action group, before the thread list
           (design .separator-etched). */}
        <div className="separator-etched mx-2" aria-hidden="true" />

        {/* Row 4: the existing thread list (Recents). */}
        <ThreadSidebar
          threads={props.threads}
          isFiltered={isFiltered}
          {...(props.activeThreadId
            ? { activeThreadId: props.activeThreadId }
            : {})}
          {...(props.now !== undefined ? { now: props.now } : {})}
          {...(props.onSelectThread ? { onSelect: props.onSelectThread } : {})}
          {...(props.onRenameThread ? { onRename: props.onRenameThread } : {})}
          {...(props.onDeleteThread ? { onDelete: props.onDeleteThread } : {})}
        />
      </div>
    </div>
  );
}
