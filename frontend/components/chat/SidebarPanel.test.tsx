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

describe("SidebarPanel — collapse state (a11y)", () => {
  it("toggle reports aria-expanded=true when expanded", () => {
    const d = render({ collapsed: false });
    expect(
      d.querySelector('[data-testid="sidebar-toggle"]')?.getAttribute(
        "aria-expanded",
      ),
    ).toBe("true");
  });

  it("toggle reports aria-expanded=false when collapsed", () => {
    const d = render({ collapsed: true });
    expect(
      d.querySelector('[data-testid="sidebar-toggle"]')?.getAttribute(
        "aria-expanded",
      ),
    ).toBe("false");
  });

  it("hides the collapsible body from a11y tree when collapsed", () => {
    const d = render({ collapsed: true });
    const body = d.querySelector('[data-testid="sidebar-body"]');
    expect(body?.getAttribute("aria-hidden")).toBe("true");
  });

  it("narrows the panel width when collapsed (w-12 vs w-64)", () => {
    const expanded = render({ collapsed: false }).querySelector(
      '[data-testid="sidebar-panel"]',
    );
    const collapsed = render({ collapsed: true }).querySelector(
      '[data-testid="sidebar-panel"]',
    );
    expect(expanded?.className).toContain("w-64");
    expect(collapsed?.className).toContain("w-12");
  });

  it("keeps the width transition for animation but respects reduced motion", () => {
    const panel = render().querySelector('[data-testid="sidebar-panel"]');
    expect(panel?.className).toContain("transition-[width]");
    expect(panel?.className).toContain("motion-reduce:transition-none");
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
