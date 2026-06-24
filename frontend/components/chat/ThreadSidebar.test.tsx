/**
 * ThreadSidebar tests (Phase 3 chat history). Empty/structure first (FD6).
 *
 * The sidebar is presentational (F-R1): it renders the grouped threads (via
 * the pure groupThreadsByTime helper, clock injected) by TITLE and calls the
 * passed select/rename/delete callbacks. We assert title rendering (not raw
 * id), grouping headers, active state, and the callbacks.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { ThreadSidebar } from "./ThreadSidebar";
import type { ThreadState } from "@/lib/wire/agent_protocol";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

const NOW = Date.parse("2026-06-17T12:00:00Z");
const DAY = 24 * 60 * 60 * 1000;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function render(props: React.ComponentProps<typeof ThreadSidebar>): void {
  act(() => {
    root.render(React.createElement(ThreadSidebar, props));
  });
}

function q<T extends Element = HTMLElement>(testid: string): T | null {
  return container.querySelector(`[data-testid="${testid}"]`);
}

function thread(id: string, title: string, msAgo: number): ThreadState {
  const iso = new Date(NOW - msAgo).toISOString();
  return {
    thread_id: id,
    user_id: "u",
    title,
    messages: [],
    created_at: iso,
    updated_at: iso,
    archived_at: null,
  };
}

describe("ThreadSidebar — empty/structure first", () => {
  it("renders the empty state with no threads", () => {
    render({ threads: [], now: NOW });
    expect(q("thread-empty")).not.toBeNull();
  });

  it("renders the TITLE, not the raw thread_id", () => {
    render({ threads: [thread("abc123", "Plan my trip", 1000)], now: NOW });
    const row = q("thread-row-abc123")!;
    expect(row.textContent).toContain("Plan my trip");
    expect(row.textContent).not.toContain("abc123");
  });

  it("renders time-group headers", () => {
    render({
      threads: [
        thread("t", "today", 1000),
        thread("o", "old", 30 * DAY),
      ],
      now: NOW,
    });
    expect(q("thread-group-today")).not.toBeNull();
    expect(q("thread-group-older")).not.toBeNull();
  });

  it("marks the active thread with aria-current", () => {
    render({
      threads: [thread("a", "A", 1000), thread("b", "B", 2000)],
      activeThreadId: "a",
      now: NOW,
    });
    expect(q("thread-row-a")?.getAttribute("aria-current")).toBe("page");
    expect(q("thread-row-b")?.getAttribute("aria-current")).toBeNull();
  });
});

describe("ThreadSidebar — Phase A preview subtitle (plan §2d)", () => {
  function threadWithFirstMessage(
    id: string,
    title: string,
    firstMessage: string,
  ): ThreadState {
    const iso = new Date(NOW - 1000).toISOString();
    return {
      thread_id: id,
      user_id: "u",
      title,
      messages: [{ role: "user", content: firstMessage }],
      created_at: iso,
      updated_at: iso,
      archived_at: null,
    };
  }

  it("renders the first-message snippet as a muted subtitle line", () => {
    render({
      threads: [
        threadWithFirstMessage(
          "t1",
          "Trip plan",
          "Plan a 5-day trip to Kyoto in spring",
        ),
      ],
      now: NOW,
    });
    const sub = q("thread-subtitle-t1");
    expect(sub).not.toBeNull();
    expect(sub?.textContent).toContain("Plan a 5-day trip to Kyoto");
  });

  it("renders title-only (no subtitle line) when there is no first message", () => {
    // thread() builds a row with messages: [] (the BFF list default).
    render({ threads: [thread("t2", "Empty thread", 1000)], now: NOW });
    expect(q("thread-row-t2")).not.toBeNull();
    expect(q("thread-subtitle-t2")).toBeNull();
  });

  it("suppresses a subtitle that just echoes the title (no doubled row)", () => {
    render({
      threads: [threadWithFirstMessage("t3", "Same text", "Same text")],
      now: NOW,
    });
    expect(q("thread-subtitle-t3")).toBeNull();
  });
});

describe("ThreadSidebar — callbacks", () => {
  it("calls onSelect with the thread id on click", () => {
    const onSelect = vi.fn();
    render({ threads: [thread("a", "A", 1000)], now: NOW, onSelect });
    act(() =>
      q("thread-row-a")!.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      ),
    );
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("calls onDelete with the thread id", () => {
    const onDelete = vi.fn();
    render({ threads: [thread("a", "A", 1000)], now: NOW, onDelete });
    act(() =>
      q("thread-delete-a")!.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      ),
    );
    expect(onDelete).toHaveBeenCalledWith("a");
  });

  it("calls onRename with the new title from the prompt", () => {
    const onRename = vi.fn();
    vi.spyOn(window, "prompt").mockReturnValue("Renamed");
    render({ threads: [thread("a", "A", 1000)], now: NOW, onRename });
    act(() =>
      q("thread-rename-a")!.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      ),
    );
    expect(onRename).toHaveBeenCalledWith("a", "Renamed");
    vi.restoreAllMocks();
  });

  it("does not call onRename when the prompt is cancelled", () => {
    const onRename = vi.fn();
    vi.spyOn(window, "prompt").mockReturnValue(null);
    render({ threads: [thread("a", "A", 1000)], now: NOW, onRename });
    act(() =>
      q("thread-rename-a")!.dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      ),
    );
    expect(onRename).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
