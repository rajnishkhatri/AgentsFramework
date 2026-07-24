/**
 * Chat shell smoke + a11y tests (S3.8.1).
 *
 * Uses SSR (renderToStaticMarkup) + JSDOM for structural assertions.
 * The ChatShell is a "use client" component but we can still SSR its
 * initial render to verify the empty state, header, composer presence,
 * and ARIA landmarks. Failure paths first (FD6).
 */

import { describe, expect, it, vi } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChatShell } from "./chat-shell";
import type { ChatSidebarsState } from "@/components/chat/use_chat_sidebars";
import type { MemoryItem, ThreadState } from "@/lib/wire/agent_protocol";

function dom(html: string): Document {
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

function render(email = "test@example.com"): Document {
  const html = renderToStaticMarkup(
    React.createElement(ChatShell, { userEmail: email }),
  );
  return dom(html);
}

function fakeThread(id: string, title: string): ThreadState {
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

function fakeMemory(key: string, content: string): MemoryItem {
  return { key, type: "semantic", content, salience: 0.5 };
}

function fakeSidebars(
  overrides: Partial<ChatSidebarsState> = {},
): ChatSidebarsState {
  return {
    threads: [],
    memories: [],
    memoryEnabled: false,
    error: null,
    reloadThreads: vi.fn(async () => undefined),
    reloadMemories: vi.fn(async () => undefined),
    renameThread: vi.fn(async () => undefined),
    deleteThread: vi.fn(async () => undefined),
    addMemory: vi.fn(async () => undefined),
    deleteMemory: vi.fn(async () => undefined),
    suppressMemory: vi.fn(async () => undefined),
    setMemoryEnabled: vi.fn(),
    loadThreadTurns: vi.fn(async () => []),
    createThread: vi.fn(async () => undefined),
    persistTurn: vi.fn(async () => undefined),
    ...overrides,
  };
}

function renderWithSidebars(sidebars: ChatSidebarsState): Document {
  const html = renderToStaticMarkup(
    React.createElement(ChatShell, {
      userEmail: "test@example.com",
      sidebars,
    }),
  );
  return dom(html);
}

describe("ChatShell — failure / edge-case paths first", () => {
  it("renders empty-state prompt when no messages exist", () => {
    const d = render();
    const text = d.body.textContent ?? "";
    expect(text).toContain("What can I help you with?");
  });

  it("does NOT render any message bubbles in initial state", () => {
    const d = render();
    const articles = d.querySelectorAll("article");
    expect(articles.length).toBe(0);
  });
});

describe("ChatShell — header rendering", () => {
  it("displays the user email in the header", () => {
    const d = render("rajnish@test.com");
    const header = d.querySelector("header");
    expect(header?.textContent).toContain("rajnish@test.com");
  });

  it("displays the app name in the header", () => {
    const d = render();
    const header = d.querySelector("header");
    expect(header?.textContent).toContain("ReAct Agent");
  });

  it("includes a sign-out link", () => {
    const d = render();
    const signOutLink = d.querySelector('[data-testid="sign-out"]');
    expect(signOutLink).toBeTruthy();
    expect(signOutLink?.getAttribute("href")).toContain("/api/auth/sign-out");
    expect(signOutLink?.textContent).toContain("Sign out");
  });

  // D2 (FR-9): exactly one visible, labelled control navigating to /learn, so
  // an authenticated user can reach the coach without typing the URL.
  it("renders exactly one labelled /learn entry link in the authed header (FR-9)", () => {
    const d = render();
    const learnLinks = d.querySelectorAll('a[href="/learn"]');
    expect(learnLinks.length).toBe(1);
    const link = learnLinks[0];
    // Labelled: has visible text (or an aria-label) a user can act on.
    const label = link?.textContent?.trim() || link?.getAttribute("aria-label");
    expect(label).toBeTruthy();
    // It lives in the header action cluster, next to sign-out.
    expect(d.querySelector("header")?.querySelector('a[href="/learn"]')).toBeTruthy();
  });
});

describe("ChatShell — initialModel seed (A/B `?model=` pin)", () => {
  it("defaults the model chip to Auto when no initialModel is given", () => {
    const d = render();
    // The composer model-picker trigger shows the current selection.
    const trigger = d.querySelector("[data-testid='model-picker-trigger']");
    expect(trigger?.textContent).toContain("Auto");
  });

  it("seeds the model chip from initialModel (URL `?model=` pin)", () => {
    const html = renderToStaticMarkup(
      React.createElement(ChatShell, {
        userEmail: "test@example.com",
        initialModel: "claude-opus-4-8",
      }),
    );
    const d = dom(html);
    const trigger = d.querySelector("[data-testid='model-picker-trigger']");
    expect(trigger?.textContent).toContain("claude-opus-4-8");
    expect(trigger?.textContent).not.toContain("Auto");
  });

  it("falls back to Auto when initialModel is null", () => {
    const html = renderToStaticMarkup(
      React.createElement(ChatShell, {
        userEmail: "test@example.com",
        initialModel: null,
      }),
    );
    const d = dom(html);
    const trigger = d.querySelector("[data-testid='model-picker-trigger']");
    expect(trigger?.textContent).toContain("Auto");
  });
});

describe("ChatShell — composer presence", () => {
  it("renders the composer form", () => {
    const d = render();
    const form = d.querySelector("form");
    expect(form).toBeTruthy();
  });

  it("renders a textarea with 'Compose message' aria-label", () => {
    const d = render();
    const ta = d.querySelector('textarea[aria-label="Compose message"]');
    expect(ta).toBeTruthy();
  });

  it("renders a Send button that is initially disabled", () => {
    const d = render();
    const btn = d.querySelector('button[aria-label="Send"]');
    expect(btn).toBeTruthy();
    expect(btn?.hasAttribute("disabled")).toBe(true);
  });
});

describe("ChatShell — layout structure", () => {
  it("uses a grid layout with header, main, and composer", () => {
    const d = render();
    const root = d.querySelector("div");
    expect(root?.className).toContain("grid");
    expect(root?.className).toContain("grid-rows");
  });

  it("has a <main> element for the messages area", () => {
    const main = render().querySelector("main");
    expect(main).toBeTruthy();
  });
});

describe("ChatShell — Phase 3 thread sidebar mounted", () => {
  it("mounts the thread sidebar and renders a thread title (not the raw id)", () => {
    const d = renderWithSidebars(
      fakeSidebars({ threads: [fakeThread("t-abc", "Plan my trip")] }),
    );
    const sidebar = d.querySelector('[data-testid="thread-sidebar"]');
    expect(sidebar).toBeTruthy();
    const row = d.querySelector('[data-testid="thread-row-t-abc"]');
    expect(row?.textContent).toContain("Plan my trip");
    expect(row?.textContent).not.toContain("t-abc");
  });

  it("shows the sidebar empty state when there are no threads", () => {
    const d = renderWithSidebars(fakeSidebars());
    expect(d.querySelector('[data-testid="thread-empty"]')).toBeTruthy();
  });

  it("still renders the composer with the sidebar mounted", () => {
    const d = renderWithSidebars(
      fakeSidebars({ threads: [fakeThread("t1", "x")] }),
    );
    expect(
      d.querySelector('textarea[aria-label="Compose message"]'),
    ).toBeTruthy();
  });
});

// UI refresh: the left rail is now a navigation panel (SidebarPanel) with a
// collapse toggle, tab bar, New chat, and Search above the Recents list.
describe("ChatShell — left navigation panel chrome", () => {
  it("mounts the SidebarPanel wrapper", () => {
    const d = renderWithSidebars(fakeSidebars());
    expect(d.querySelector('[data-testid="sidebar-panel"]')).toBeTruthy();
  });

  it("renders the New chat button (data-testid=new-thread)", () => {
    const d = renderWithSidebars(fakeSidebars());
    const btn = d.querySelector('[data-testid="new-thread"]');
    expect(btn).toBeTruthy();
    expect(btn?.textContent).toContain("New chat");
  });

  it("renders the Chat tab and the collapse toggle", () => {
    const d = renderWithSidebars(fakeSidebars());
    expect(d.querySelector('[data-testid="sidebar-tab-chat"]')).toBeTruthy();
    expect(d.querySelector('[data-testid="sidebar-toggle"]')).toBeTruthy();
  });

  it("renders the search toggle", () => {
    const d = renderWithSidebars(fakeSidebars());
    expect(
      d.querySelector('[data-testid="sidebar-search-toggle"]'),
    ).toBeTruthy();
  });

  it("starts expanded (toggle aria-expanded=true) on first render", () => {
    const d = renderWithSidebars(fakeSidebars());
    expect(
      d.querySelector('[data-testid="sidebar-toggle"]')?.getAttribute(
        "aria-expanded",
      ),
    ).toBe("true");
  });
});

// Phase 0 (UI refresh): the right "What I remember" column was removed from
// the chat layout. MemoryPanel.tsx and the memory half of useChatSidebars are
// retained (reversible, backend untouched) but must NOT render in the shell.
describe("ChatShell — right memory panel removed from layout", () => {
  it("does NOT mount the memory panel even when the hook has memories", () => {
    const d = renderWithSidebars(
      fakeSidebars({ memories: [fakeMemory("k1", "prefers metric units")] }),
    );
    expect(d.querySelector('[data-testid="memory-panel"]')).toBeNull();
    expect(d.body.textContent ?? "").not.toContain("prefers metric units");
  });

  it("does NOT render the memory-enabled toggle in the shell", () => {
    const d = renderWithSidebars(fakeSidebars({ memoryEnabled: true }));
    expect(
      d.querySelector('[data-testid="memory-enabled-toggle"]'),
    ).toBeNull();
  });

  it("uses a two-column body grid (no third memory column)", () => {
    const d = renderWithSidebars(fakeSidebars());
    // Two CONTENT columns (rail + chat) with a 2px etched groove between them;
    // the removed memory panel would have been a third content column.
    const hasTwoCol = Array.from(d.querySelectorAll("div")).some((el) =>
      el.className.includes("lg:grid-cols-[auto_2px_1fr]"),
    );
    expect(hasTwoCol).toBe(true);
  });
});
