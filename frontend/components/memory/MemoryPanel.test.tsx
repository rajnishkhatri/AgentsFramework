/**
 * MemoryPanel + RecallIndicator tests. Failure/empty paths first (FD6).
 *
 * The panel is presentational (F-R1): it renders the passed items and calls
 * the passed callbacks. We assert grouping, the empty state, the toggle, and
 * the add/delete callbacks fire with the right payload.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryPanel } from "./MemoryPanel";
import { RecallIndicator } from "./RecallIndicator";
import type { MemoryItem } from "@/lib/wire/agent_protocol";

// React 19 act() flag (same as Composer.test.tsx).
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

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

function renderPanel(props: React.ComponentProps<typeof MemoryPanel>): void {
  act(() => {
    root.render(React.createElement(MemoryPanel, props));
  });
}

function q<T extends Element = HTMLElement>(testid: string): T | null {
  return container.querySelector(`[data-testid="${testid}"]`);
}

const ITEMS: MemoryItem[] = [
  { key: "s1", type: "semantic", content: "prefers metric units", salience: 0.9 },
  { key: "e1", type: "episodic", content: "debugged auth: expired token", salience: 0.6 },
  { key: "u1", type: null, content: "untyped note", salience: null },
];

describe("MemoryPanel — empty/structure first", () => {
  it("shows the empty state when there are no items", () => {
    renderPanel({ items: [], enabled: true });
    expect(q("memory-empty")).not.toBeNull();
    expect(q("memory-group-semantic")).toBeNull();
  });

  it("groups items by type and files untyped under semantic", () => {
    renderPanel({ items: ITEMS, enabled: true });
    expect(q("memory-group-semantic")).not.toBeNull();
    expect(q("memory-group-episodic")).not.toBeNull();
    // untyped 'u1' rendered (under semantic), never silently dropped.
    expect(q("memory-item-u1")).not.toBeNull();
  });

  it("reflects the enabled toggle state", () => {
    renderPanel({ items: ITEMS, enabled: false });
    const toggle = q<HTMLInputElement>("memory-enabled-toggle");
    expect(toggle?.checked).toBe(false);
  });
});

describe("MemoryPanel — callbacks", () => {
  it("calls onToggleEnabled when the toggle changes", () => {
    const onToggleEnabled = vi.fn();
    renderPanel({ items: ITEMS, enabled: true, onToggleEnabled });
    const toggle = q<HTMLInputElement>("memory-enabled-toggle")!;
    // React tracks the controlled value via its own setter; mutate through the
    // prototype setter so React's delegated onChange fires (same technique the
    // Composer test uses for textarea value).
    const setChecked = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "checked",
    )!.set!;
    act(() => {
      setChecked.call(toggle, false);
      toggle.dispatchEvent(new Event("click", { bubbles: true }));
    });
    expect(onToggleEnabled).toHaveBeenCalledWith(false);
  });

  it("calls onDelete with the item key", () => {
    const onDelete = vi.fn();
    renderPanel({ items: ITEMS, enabled: true, onDelete });
    const btn = q<HTMLButtonElement>("memory-delete-s1")!;
    act(() => btn.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onDelete).toHaveBeenCalledWith("s1");
  });

  it("add stays disabled for empty input and fires onAdd for non-empty", () => {
    const onAdd = vi.fn();
    renderPanel({ items: [], enabled: true, onAdd });
    const submit = q<HTMLButtonElement>("memory-add-submit")!;
    expect(submit.disabled).toBe(true);

    const input = q<HTMLInputElement>("memory-add-input")!;
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value",
    )!.set!;
    act(() => {
      setter.call(input, "likes dark mode");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(submit.disabled).toBe(false);
    act(() => submit.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onAdd).toHaveBeenCalledWith("likes dark mode", "semantic");
  });
});

describe("RecallIndicator", () => {
  it("renders nothing for a zero count (no recall happened)", () => {
    act(() => root.render(React.createElement(RecallIndicator, { count: 0 })));
    expect(q("recall-indicator")).toBeNull();
  });

  it("renders singular and plural labels", () => {
    act(() => root.render(React.createElement(RecallIndicator, { count: 1 })));
    expect(q("recall-indicator")?.textContent).toContain("1 memory");
    act(() => root.render(React.createElement(RecallIndicator, { count: 3 })));
    expect(q("recall-indicator")?.textContent).toContain("3 memories");
  });
});
