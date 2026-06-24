/**
 * SidebarPanel tests (UI refresh Phase 1-4).
 *
 * SSR (renderToStaticMarkup) + JSDOM, matching the chat-shell idiom. The panel
 * is a pure presentational leaf (F-R1): it takes chrome state + callbacks as
 * props and owns no lifecycle, so every state combination is rendered by
 * passing props — no hook-rendering harness (no @testing-library dep).
 *
 * Asserts the data-testid contract the Playwright suite depends on
 * (design doc §9) and the collapse a11y wiring (aria-expanded).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SidebarPanel } from "./SidebarPanel";
import type { ThreadState } from "@/lib/wire/agent_protocol";

function thread(id: string, title: string): ThreadState {
  return {
    thread_id: id,
    user_id: "u",
    title,
    messages: [],
    created_at: "2026-06-17T00:00:00Z",
    updated_at: "2026-06-17T00:00:00Z",
    archived_at: null,
  };
}

function render(
  props: Partial<React.ComponentProps<typeof SidebarPanel>> = {},
): Document {
  const html = renderToStaticMarkup(
    React.createElement(SidebarPanel, {
      threads: [],
      collapsed: false,
      searchOpen: false,
      searchQuery: "",
      activeTab: "chat",
      onToggleCollapsed: () => {},
      onToggleSearch: () => {},
      onSearchQueryChange: () => {},
      onCloseSearch: () => {},
      onSelectTab: () => {},
      onNewChat: () => {},
      ...props,
    }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("SidebarPanel — chrome affordances present", () => {
  it("renders the panel root with its testid", () => {
    expect(render().querySelector('[data-testid="sidebar-panel"]')).toBeTruthy();
  });

  it("renders the collapse toggle and the tab bar", () => {
    const d = render();
    expect(d.querySelector('[data-testid="sidebar-toggle"]')).toBeTruthy();
    expect(d.querySelector('[data-testid="sidebar-tab-chat"]')).toBeTruthy();
  });

  it("renders the New chat button with the new-thread testid", () => {
    const d = render();
    const btn = d.querySelector('[data-testid="new-thread"]');
    expect(btn).toBeTruthy();
    expect(btn?.textContent).toContain("New chat");
  });

  it("renders the search toggle", () => {
    expect(
      render().querySelector('[data-testid="sidebar-search-toggle"]'),
    ).toBeTruthy();
  });

  it("embeds the thread list (ThreadSidebar) for the passed threads", () => {
    const d = render({ threads: [thread("t-1", "Plan a trip")] });
    expect(d.querySelector('[data-testid="thread-sidebar"]')).toBeTruthy();
    const row = d.querySelector('[data-testid="thread-row-t-1"]');
    expect(row?.textContent).toContain("Plan a trip");
  });
});

describe("SidebarPanel — toggle + full-hide model (plan §2b)", () => {
  // The redesign replaced the w-12 stub with a full-hide: the SHELL unmounts the
  // rail when collapsed (so the chat takes full width), and the panel itself is
  // a fixed wider width (w-72) with no width animation. The in-panel brand-row
  // toggle still reports aria-expanded so the header rail-toggle stays in sync.
  it("toggle reports aria-expanded=true when expanded", () => {
    const d = render({ collapsed: false });
    expect(
      d.querySelector('[data-testid="sidebar-toggle"]')?.getAttribute(
        "aria-expanded",
      ),
    ).toBe("true");
  });

  it("the panel is the fixed wider width (w-72), no w-12 stub", () => {
    const panel = render().querySelector('[data-testid="sidebar-panel"]');
    expect(panel?.className).toContain("w-72");
    expect(panel?.className).not.toContain("w-12");
  });

  it("renders the brand row (dot + Threads wordmark)", () => {
    const d = render();
    expect(d.querySelector('[data-testid="sidebar-brand-dot"]')).toBeTruthy();
    expect(
      d.querySelector('[data-testid="sidebar-panel"]')?.textContent,
    ).toContain("Threads");
  });

  it("the toggle uses the panel-close affordance label", () => {
    const d = render();
    expect(
      d.querySelector('[data-testid="sidebar-toggle"]')?.getAttribute(
        "aria-label",
      ),
    ).toBe("Hide sidebar");
  });
});

describe("SidebarPanel — Memory tab (plan §2c)", () => {
  it("mounts MemoryPanel (not the thread list) when activeTab=memory", () => {
    const d = render({ activeTab: "memory", memories: [], memoryEnabled: false });
    expect(d.querySelector('[data-testid="memory-panel"]')).toBeTruthy();
    // Chat-only affordances are not shown on the Memory tab.
    expect(d.querySelector('[data-testid="thread-sidebar"]')).toBeNull();
    expect(d.querySelector('[data-testid="new-thread"]')).toBeNull();
  });

  it("shows the thread list (not MemoryPanel) on the Chats tab", () => {
    const d = render({ activeTab: "chat" });
    expect(d.querySelector('[data-testid="thread-sidebar"]')).toBeTruthy();
    expect(d.querySelector('[data-testid="memory-panel"]')).toBeNull();
  });
});

describe("SidebarPanel — search affordance", () => {
  it("does NOT render the search input until search is open", () => {
    expect(
      render({ searchOpen: false }).querySelector(
        '[data-testid="sidebar-search-input"]',
      ),
    ).toBeNull();
  });

  it("renders the search input (with aria-label) when search is open", () => {
    const d = render({ searchOpen: true });
    const input = d.querySelector('[data-testid="sidebar-search-input"]');
    expect(input).toBeTruthy();
    expect(input?.getAttribute("aria-label")).toBe("Search conversations");
  });

  it("reflects the current searchQuery as the input value", () => {
    const d = render({ searchOpen: true, searchQuery: "trip" });
    const input = d.querySelector(
      '[data-testid="sidebar-search-input"]',
    ) as HTMLInputElement | null;
    expect(input?.getAttribute("value")).toBe("trip");
  });

  it("shows the search-empty variant when a non-empty query matches nothing", () => {
    const d = render({ searchOpen: true, searchQuery: "zzz", threads: [] });
    expect(
      d.querySelector('[data-testid="thread-search-empty"]'),
    ).toBeTruthy();
  });

  it("shows the cold empty state (not search-empty) when no query is active", () => {
    const d = render({ searchOpen: false, searchQuery: "", threads: [] });
    expect(d.querySelector('[data-testid="thread-empty"]')).toBeTruthy();
    expect(d.querySelector('[data-testid="thread-search-empty"]')).toBeNull();
  });
});
