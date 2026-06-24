/**
 * SidebarPanel — the left-rail CHROME wrapper (UI refresh Phase 1-4 + native-wrap
 * redesign Phase 5).
 *
 * Pure presentational leaf (F-R1): all state (collapsed / search / activeTab)
 * is owned by `useSidebarChrome` at the shell level and passed in as props;
 * thread/memory DATA is owned by `useChatSidebars`. This component only lays out
 * the affordances — brand row + panel-toggle, tab bar, New chat, Search — above
 * the `ThreadSidebar` list (Chats tab) or `MemoryPanel` (Memory tab), and
 * forwards every interaction via callbacks.
 *
 * Full-hide (plan §2b): "collapsed" no longer animates to a w-12 stub — the
 * shell gates the rail column render on `!collapsed`, so when collapsed this
 * panel does not mount at all and the chat takes the full width. The header
 * panel-toggle (chat-shell) is the canonical restore affordance; the in-panel
 * toggle on the brand row also hides it. The panel is a fixed wider width
 * (w-72, plan §2b) — no width animation.
 *
 * Icons are lucide line SVGs (PanelLeftClose / Search / Plus) — house style.
 */

"use client";

import * as React from "react";
import { PanelLeftClose, Plus, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  MemoryItem,
  MemoryType,
  ThreadState,
} from "@/lib/wire/agent_protocol";
import { ThreadSidebar } from "./ThreadSidebar";
import { SidebarTabBar } from "./SidebarTabBar";
import { MemoryPanel } from "@/components/memory/MemoryPanel";
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
  // memory data + callbacks (forwarded to MemoryPanel on the Memory tab)
  memories?: ReadonlyArray<MemoryItem>;
  memoryEnabled?: boolean;
  onAddMemory?: (content: string, type: MemoryType) => void;
  onDeleteMemory?: (key: string) => void;
  onToggleMemoryEnabled?: (enabled: boolean) => void;
}): React.JSX.Element {
  const isFiltered = props.searchQuery.trim().length > 0;
  const onMemoryTab = props.activeTab === "memory";

  return (
    <div
      data-testid="sidebar-panel"
      className={cn("h-full overflow-hidden bg-bg w-72")}
    >
      {/* Row 0: brand row — terracotta dot + "Threads" wordmark + panel-toggle
         (design .brand / .brand-dot, see All Surfaces.html). */}
      <div className="flex items-center justify-between gap-2 px-3 pt-3 pb-1">
        <div className="brand flex items-center gap-2">
          <span
            aria-hidden="true"
            data-testid="sidebar-brand-dot"
            className="brand-dot inline-block size-2.5 rounded-full bg-accent"
          />
          <span className="text-sm font-semibold text-fg">Threads</span>
        </div>
        <button
          type="button"
          data-testid="sidebar-toggle"
          aria-label="Hide sidebar"
          aria-expanded={!props.collapsed}
          aria-controls="sidebar-body"
          onClick={props.onToggleCollapsed}
          className="text-muted bg-transparent border-0 cursor-pointer leading-none px-1 hover:text-fg flex items-center"
        >
          <PanelLeftClose className="size-5" aria-hidden="true" />
        </button>
      </div>

      {/* Row 1: tab bar (Chats / Memory) */}
      <div className="flex items-center gap-2 px-2 pb-1">
        <SidebarTabBar
          activeTab={props.activeTab}
          onSelect={props.onSelectTab}
        />
      </div>

      {/* Body. */}
      <div
        id="sidebar-body"
        data-testid="sidebar-body"
        className="grid gap-2"
      >
        {onMemoryTab ? (
          // Memory tab: mount the existing MemoryPanel fed by useChatSidebars'
          // memory half (plan §2c). New chat / Search are chat-only affordances.
          <MemoryPanel
            items={props.memories ?? []}
            enabled={props.memoryEnabled ?? false}
            {...(props.onAddMemory ? { onAdd: props.onAddMemory } : {})}
            {...(props.onDeleteMemory ? { onDelete: props.onDeleteMemory } : {})}
            {...(props.onToggleMemoryEnabled
              ? { onToggleEnabled: props.onToggleMemoryEnabled }
              : {})}
          />
        ) : (
          <>
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
              {...(props.onSelectThread
                ? { onSelect: props.onSelectThread }
                : {})}
              {...(props.onRenameThread
                ? { onRename: props.onRenameThread }
                : {})}
              {...(props.onDeleteThread
                ? { onDelete: props.onDeleteThread }
                : {})}
            />
          </>
        )}
      </div>
    </div>
  );
}
