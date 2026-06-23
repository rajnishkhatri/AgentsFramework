/**
 * useSidebarChrome — owns the left-panel CHROME state (UI refresh plan §D6):
 * collapsed (persisted), search open/query, and the active nav tab. Thread
 * DATA stays in `useChatSidebars`; per F-R1 the panel leaf renders these as
 * props and never owns lifecycle.
 *
 * Persistence is a cosmetic preference, not data, so it fails SAFE: a throwing
 * or absent storage (SSR, Safari private mode) degrades to "expanded" and the
 * write is a silent no-op — losing the preference must never crash a render or
 * surface an error. The read/write helpers are exported pure + storage-injected
 * so they are node-testable without a DOM (mirrors use_chat_sidebars).
 *
 * SSR-safety: the initial render is always "expanded" (deterministic); the
 * persisted value is read in an effect after mount (mirrors ThemeToggle's
 * `mounted` guard), so there is no hydration mismatch.
 */

"use client";

import * as React from "react";

export const COLLAPSED_STORAGE_KEY = "sidebar:collapsed";

/** Minimal storage surface we depend on (so tests can inject a fake). */
type ChromeStorage = Pick<Storage, "getItem" | "setItem">;

/** Read the persisted collapsed flag; absent/throwing storage → false. */
export function readCollapsed(storage: ChromeStorage | null): boolean {
  if (!storage) return false;
  try {
    return storage.getItem(COLLAPSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Persist the collapsed flag; absent/throwing storage → silent no-op. */
export function writeCollapsed(
  storage: ChromeStorage | null,
  collapsed: boolean,
): void {
  if (!storage) return;
  try {
    storage.setItem(COLLAPSED_STORAGE_KEY, collapsed ? "1" : "0");
  } catch {
    /* preference loss is non-fatal */
  }
}

/** The nav tabs. Chat only for now; future tabs are an additive data change. */
export type SidebarTab = "chat";

export interface SidebarChromeState {
  readonly collapsed: boolean;
  readonly searchOpen: boolean;
  readonly searchQuery: string;
  readonly activeTab: SidebarTab;
  /**
   * Mobile drawer open/closed (P3 §5). Distinct from `collapsed`: that is the
   * desktop inline-rail width toggle (persisted); this is the ephemeral <lg
   * overlay Sheet. Always starts closed (never persisted) so a phone reload
   * never opens over the chat.
   */
  readonly drawerOpen: boolean;
  toggleCollapsed(): void;
  toggleSearch(): void;
  setSearchQuery(q: string): void;
  /** Close + clear search (the Escape / search-toggle-off path). */
  closeSearch(): void;
  setActiveTab(tab: SidebarTab): void;
  /** Open/close the mobile drawer (hamburger + overlay dismiss + auto-close). */
  setDrawerOpen(open: boolean): void;
}

function browserStorage(): ChromeStorage | null {
  return typeof window !== "undefined" ? window.localStorage : null;
}

export function useSidebarChrome(): SidebarChromeState {
  // Always start expanded so SSR and the first client render agree; the
  // persisted value is applied in the post-mount effect below.
  const [collapsed, setCollapsed] = React.useState(false);
  const [searchOpen, setSearchOpen] = React.useState(false);
  const [searchQuery, setSearchQueryState] = React.useState("");
  const [activeTab, setActiveTab] = React.useState<SidebarTab>("chat");
  // Ephemeral: the mobile drawer is never persisted (always closed on mount).
  const [drawerOpen, setDrawerOpenState] = React.useState(false);

  React.useEffect(() => {
    setCollapsed(readCollapsed(browserStorage()));
  }, []);

  const toggleCollapsed = React.useCallback((): void => {
    setCollapsed((prev) => {
      const next = !prev;
      writeCollapsed(browserStorage(), next);
      return next;
    });
  }, []);

  const toggleSearch = React.useCallback((): void => {
    setSearchOpen((prev) => {
      const next = !prev;
      if (!next) setSearchQueryState(""); // closing clears the filter
      return next;
    });
  }, []);

  const closeSearch = React.useCallback((): void => {
    setSearchOpen(false);
    setSearchQueryState("");
  }, []);

  const setSearchQuery = React.useCallback((q: string): void => {
    setSearchQueryState(q);
  }, []);

  const setDrawerOpen = React.useCallback((open: boolean): void => {
    setDrawerOpenState(open);
  }, []);

  return {
    collapsed,
    searchOpen,
    searchQuery,
    activeTab,
    drawerOpen,
    toggleCollapsed,
    toggleSearch,
    setSearchQuery,
    closeSearch,
    setActiveTab,
    setDrawerOpen,
  };
}
