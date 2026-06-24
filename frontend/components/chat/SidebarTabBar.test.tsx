/**
 * SidebarTabBar tests (UI refresh Phase 2).
 *
 * SSR (renderToStaticMarkup) + JSDOM structural assertions, matching the
 * chat-shell test idiom. A11y first (FD4): the bar must expose the WAI-ARIA
 * tablist/tab roles and mark the active tab with aria-selected, so screen
 * readers announce it as a tab group, not a row of buttons.
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SidebarTabBar } from "./SidebarTabBar";

function render(active: "chat" | "memory" = "chat"): Document {
  const html = renderToStaticMarkup(
    React.createElement(SidebarTabBar, { activeTab: active }),
  );
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

describe("SidebarTabBar", () => {
  it("renders a tablist container", () => {
    const d = render();
    expect(d.querySelector('[role="tablist"]')).toBeTruthy();
  });

  it("renders the Chats tab with role=tab and its testid", () => {
    const d = render();
    const tab = d.querySelector('[data-testid="sidebar-tab-chat"]');
    expect(tab).toBeTruthy();
    expect(tab?.getAttribute("role")).toBe("tab");
    expect(tab?.textContent).toContain("Chats");
  });

  it("renders the Memory tab (plan §2c)", () => {
    const d = render();
    const tab = d.querySelector('[data-testid="sidebar-tab-memory"]');
    expect(tab).toBeTruthy();
    expect(tab?.getAttribute("role")).toBe("tab");
    expect(tab?.textContent).toContain("Memory");
  });

  it("marks the active tab with aria-selected=true", () => {
    const d = render("memory");
    const chat = d.querySelector('[data-testid="sidebar-tab-chat"]');
    const memory = d.querySelector('[data-testid="sidebar-tab-memory"]');
    expect(memory?.getAttribute("aria-selected")).toBe("true");
    expect(chat?.getAttribute("aria-selected")).toBe("false");
  });

  it("renders the two tabs (Chats + Memory)", () => {
    const d = render();
    expect(d.querySelectorAll('[role="tab"]').length).toBe(2);
  });
});
