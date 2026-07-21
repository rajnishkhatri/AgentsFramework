/**
 * Composer.test.tsx — keyboard, IME, and autosize unit tests for
 * `Composer.tsx` (S3.8.5 / FD2.U_KBD / U_IME / U_AUTOSIZE / U_LBL).
 *
 * Failure paths first (FD6.UI / TAP-4): the IME-composing case is the
 * regression guard — kana / hangul / pinyin candidate-confirmation
 * Enter must NOT double-fire onSend. We assert that BEFORE the
 * happy-path Meta+Enter / Ctrl+Enter assertions.
 *
 * The autosize check is a static className probe (`field-sizing`).
 * JSDOM does not implement layout, so the actual pixel-height growth
 * has to be covered by Playwright (e2e); the className check is the
 * unit-test-friendly proxy that the U_AUTOSIZE contract is in place.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { Composer } from "./Composer";

// React 19 requires this flag to suppress the "current testing environment
// is not configured to support act(...)" warning emitted by createRoot.
// (https://github.com/reactwg/react-18/discussions/102 — the flag survived
// to React 19's act API.) Setting it on globalThis is the documented
// non-RTL pattern.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

/**
 * Render a Composer into the test container and return its textarea.
 * Wraps render in `act()` so React 19's concurrent commit flushes
 * before the test inspects the DOM.
 */
function render(props: {
  onSend: (body: string, selectedModel?: string) => void | Promise<void>;
  busy?: boolean;
  models?: ReadonlyArray<{ name: string; tier: string }>;
  selectedModel?: string;
  onSelectModel?: (model: string) => void;
}): HTMLTextAreaElement {
  act(() => {
    root.render(React.createElement(Composer, props));
  });
  const ta = container.querySelector("textarea");
  if (!ta) throw new Error("Composer did not render a <textarea>");
  return ta;
}

/**
 * Set a controlled textarea's value the way React Testing Library does:
 * call the prototype setter so React's onChange listener picks up the
 * change, then dispatch a bubbling input event.
 */
function setControlledValue(ta: HTMLTextAreaElement, value: string): void {
  const proto = window.HTMLTextAreaElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (!setter) throw new Error("HTMLTextAreaElement.value setter unavailable");
  setter.call(ta, value);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
}

interface EnterOpts {
  metaKey?: boolean;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  isComposing?: boolean;
}

/**
 * Dispatch a real KeyboardEvent("keydown", { key: "Enter", … }) on the
 * textarea. Bubbles so React's delegated listener at the root captures
 * it. The `isComposing` constructor field is what
 * `e.nativeEvent.isComposing` reads inside Composer.
 */
function dispatchEnter(ta: HTMLTextAreaElement, opts: EnterOpts = {}): void {
  const ev = new window.KeyboardEvent("keydown", {
    key: "Enter",
    metaKey: !!opts.metaKey,
    ctrlKey: !!opts.ctrlKey,
    shiftKey: !!opts.shiftKey,
    altKey: !!opts.altKey,
    isComposing: !!opts.isComposing,
    bubbles: true,
    cancelable: true,
  });
  ta.dispatchEvent(ev);
}

describe("Composer keyboard contract [FD2.U_KBD / U_IME]", () => {
  it("does NOT submit on Enter while IME is composing (regression guard)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "konnichiwa"));
    act(() => dispatchEnter(ta, { isComposing: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("submits trimmed body once on plain Enter (no IME, no modifier)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "  hello  "));
    act(() => dispatchEnter(ta));
    expect(onSend).toHaveBeenCalledTimes(1);
    // Default selection is the Auto sentinel (no pin) — passed as the 2nd arg.
    expect(onSend).toHaveBeenCalledWith("hello", "Auto");
  });

  it("does NOT submit when the textarea is whitespace-only on Enter", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "    "));
    act(() => dispatchEnter(ta));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit on Meta+Enter (newline modifier)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta, { metaKey: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit on Ctrl+Enter (newline modifier)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta, { ctrlKey: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit on Shift+Enter (newline modifier)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta, { shiftKey: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit while busy=true even on Enter", () => {
    const onSend = vi.fn();
    const ta = render({ onSend, busy: true });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta));
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe("Composer autosize CSS contract [FD2.U_AUTOSIZE]", () => {
  it("textarea className includes the field-sizing autosize hint", () => {
    const ta = render({ onSend: () => {} });
    expect(ta.className).toContain("field-sizing");
  });

  it("textarea className includes a documented max-height bracket (6-row cap)", () => {
    const ta = render({ onSend: () => {} });
    expect(ta.className).toMatch(/max-h-\[/);
    expect(ta.className).toMatch(/min-h-\[/);
  });

  it("FR-15: coach composer input min-height is at least 58px (3.6rem)", () => {
    const ta = render({ onSend: () => {} });
    // 2 × 1.125rem × 1.6 ≈ 3.6rem = 57.6px → locked as 58px / min-h-[3.6rem]
    expect(ta.className).toMatch(/min-h-\[3\.6rem\]/);
  });
});

describe("Composer label contract [FD2.U_LBL]", () => {
  it("textarea exposes an aria-label so jsx-a11y/label-has-associated-control passes", () => {
    const ta = render({ onSend: () => {} });
    expect(ta.getAttribute("aria-label")).toBe("Compose message");
  });
});

describe("Composer model picker [Task #4]", () => {
  it("defaults the chip to Auto (no selection passed)", () => {
    render({ onSend: () => {} });
    const trigger = container.querySelector('[aria-label="Choose model"]');
    expect(trigger).not.toBeNull();
    expect(trigger?.getAttribute("title")).toBe("Model: Auto");
  });

  it("shows the pinned model name on the chip when one is selected", () => {
    render({ onSend: () => {}, selectedModel: "claude-sonnet-4-6" });
    const trigger = container.querySelector('[aria-label="Choose model"]');
    expect(trigger?.getAttribute("title")).toBe("Model: claude-sonnet-4-6");
    expect(trigger?.textContent).toContain("claude-sonnet-4-6");
  });

  it("forwards the selected model as the 2nd arg of onSend on submit", () => {
    const onSend = vi.fn();
    const ta = render({ onSend, selectedModel: "gpt-4o" });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta));
    expect(onSend).toHaveBeenCalledWith("hi", "gpt-4o");
  });

  it("renders without a models list (fail-safe: Auto-only, never blocks)", () => {
    // No `models` prop — the picker must still render its trigger.
    const trigger = (() => {
      render({ onSend: () => {} });
      return container.querySelector('[aria-label="Choose model"]');
    })();
    expect(trigger).not.toBeNull();
  });
});
