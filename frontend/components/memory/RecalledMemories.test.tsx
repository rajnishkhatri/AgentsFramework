/**
 * RecalledMemories (Phase B B2) — presentational eval/reject disclosure.
 * Failure paths first (FD6): no items → renders nothing; the Reject button
 * fires onReject with the item's key.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { createRoot, type Root } from "react-dom/client";
import { RecalledMemories } from "./RecalledMemories";
import type { MemoryItem } from "@/lib/wire/agent_protocol";

function item(key: string, content: string, type: MemoryItem["type"] = "semantic"): MemoryItem {
  return { key, type, content, salience: null };
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  root.unmount();
  container.remove();
});

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

async function render(
  items: ReadonlyArray<MemoryItem>,
  onReject: (key: string) => void,
): Promise<void> {
  root.render(
    React.createElement(RecalledMemories, { items, onReject }),
  );
  await flush();
}

function byTestId(id: string): HTMLElement | null {
  return container.querySelector(`[data-testid='${id}']`);
}

describe("RecalledMemories", () => {
  it("renders nothing when there are no recalled items (failure path first)", async () => {
    await render([], vi.fn());
    expect(byTestId("recalled-memories")).toBeNull();
    expect(container.textContent).toBe("");
  });

  it("lists each recalled item with its content and a stable testid", async () => {
    await render(
      [item("k1", "prefers metric units"), item("k2", "lives in Berlin")],
      vi.fn(),
    );
    expect(byTestId("recalled-memories")).toBeTruthy();
    expect(byTestId("recalled-memory-k1")?.textContent).toContain(
      "prefers metric units",
    );
    expect(byTestId("recalled-memory-k2")?.textContent).toContain(
      "lives in Berlin",
    );
  });

  it("summarizes the count (singular vs plural)", async () => {
    await render([item("k1", "one")], vi.fn());
    expect(byTestId("recalled-memories")?.textContent).toContain(
      "1 memory recalled here",
    );
    root.unmount();
    root = createRoot(container);
    await render([item("k1", "one"), item("k2", "two")], vi.fn());
    expect(byTestId("recalled-memories")?.textContent).toContain(
      "2 memories recalled here",
    );
  });

  it("Reject fires onReject with the item key (soft-suppress)", async () => {
    const onReject = vi.fn();
    await render([item("k1", "prefers metric units")], onReject);
    (byTestId("reject-memory-k1") as HTMLElement).dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
    );
    expect(onReject).toHaveBeenCalledExactlyOnceWith("k1");
  });
});
