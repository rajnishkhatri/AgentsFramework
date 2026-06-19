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

function render(active: "chat" = "chat"): Document {
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

  it("renders the Chat tab with role=tab and its testid", () => {
    const d = render();
    const tab = d.querySelector('[data-testid="sidebar-tab-chat"]');
    expect(tab).toBeTruthy();
    expect(tab?.getAttribute("role")).toBe("tab");
    expect(tab?.textContent).toContain("Chat");
  });

  it("marks the active tab with aria-selected=true", () => {
    const d = render("chat");
    const tab = d.querySelector('[data-testid="sidebar-tab-chat"]');
    expect(tab?.getAttribute("aria-selected")).toBe("true");
  });

  it("renders exactly one tab for now (Chat only)", () => {
    const d = render();
    expect(d.querySelectorAll('[role="tab"]').length).toBe(1);
  });
});
