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
  onSend: (body: string) => void | Promise<void>;
  busy?: boolean;
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
    isComposing: !!opts.isComposing,
    bubbles: true,
    cancelable: true,
  });
  ta.dispatchEvent(ev);
}

describe("Composer keyboard contract [FD2.U_KBD / U_IME]", () => {
  it("does NOT submit on Meta+Enter while IME is composing (regression guard)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "konnichiwa"));
    act(() => dispatchEnter(ta, { metaKey: true, isComposing: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit on Ctrl+Enter while IME is composing (regression guard)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "annyeonghaseyo"));
    act(() => dispatchEnter(ta, { ctrlKey: true, isComposing: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("submits trimmed body once on Meta+Enter (no IME)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "  hello  "));
    act(() => dispatchEnter(ta, { metaKey: true }));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("hello");
  });

  it("submits trimmed body once on Ctrl+Enter (no IME)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "hello"));
    act(() => dispatchEnter(ta, { ctrlKey: true }));
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("hello");
  });

  it("does NOT submit when the textarea is whitespace-only on Meta+Enter", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "    "));
    act(() => dispatchEnter(ta, { metaKey: true }));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit on plain Enter without Meta or Ctrl (Shift+Enter inserts newline path)", () => {
    const onSend = vi.fn();
    const ta = render({ onSend });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does NOT submit while busy=true even on Meta+Enter", () => {
    const onSend = vi.fn();
    const ta = render({ onSend, busy: true });
    act(() => setControlledValue(ta, "hi"));
    act(() => dispatchEnter(ta, { metaKey: true }));
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
});

describe("Composer label contract [FD2.U_LBL]", () => {
  it("textarea exposes an aria-label so jsx-a11y/label-has-associated-control passes", () => {
    const ta = render({ onSend: () => {} });
    expect(ta.getAttribute("aria-label")).toBe("Compose message");
  });
});
