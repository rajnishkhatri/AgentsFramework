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
    setMemoryEnabled: vi.fn(),
    loadThreadTurns: vi.fn(async () => []),
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
    const signOutLink = d.querySelector('a[href="/api/auth/sign-out"]');
    expect(signOutLink).toBeTruthy();
    expect(signOutLink?.textContent).toContain("Sign out");
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

describe("ChatShell — Phase 3 side panels mounted", () => {
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

  it("mounts the memory panel and renders a stored item", () => {
    const d = renderWithSidebars(
      fakeSidebars({ memories: [fakeMemory("k1", "prefers metric units")] }),
    );
    const panel = d.querySelector('[data-testid="memory-panel"]');
    expect(panel).toBeTruthy();
    expect(panel?.textContent).toContain("prefers metric units");
  });

  it("reflects the memory-enabled toggle state from the hook", () => {
    const d = renderWithSidebars(fakeSidebars({ memoryEnabled: true }));
    const toggle = d.querySelector(
      '[data-testid="memory-enabled-toggle"]',
    ) as HTMLInputElement | null;
    expect(toggle?.hasAttribute("checked")).toBe(true);
  });

  it("shows the sidebar empty state when there are no threads", () => {
    const d = renderWithSidebars(fakeSidebars());
    expect(d.querySelector('[data-testid="thread-empty"]')).toBeTruthy();
  });

  it("still renders the composer with both panels mounted", () => {
    const d = renderWithSidebars(
      fakeSidebars({ threads: [fakeThread("t1", "x")] }),
    );
    expect(
      d.querySelector('textarea[aria-label="Compose message"]'),
    ).toBeTruthy();
  });
});
