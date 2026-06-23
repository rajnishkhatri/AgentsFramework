/**
 * MessageActions.test.tsx — copy / regenerate behavior + the long-press
 * detector (§6, P4). Failure/guard paths first: a long-press must NOT fire for
 * a mouse pointer (that's the hover toolbar's job), and must be cancelled by
 * pointer movement past the tolerance.
 *
 * Raw react-dom/client + act (the repo's non-RTL convention, see Composer.test).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MessageActions, useLongPress, LONG_PRESS_MS } from "./MessageActions";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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
  vi.restoreAllMocks();
  vi.useRealTimers();
});

function renderActions(props: {
  text: string;
  onRegenerate?: () => void;
  menuOpen?: boolean;
}): void {
  act(() => {
    root.render(
      React.createElement(MessageActions, {
        text: props.text,
        menuOpen: props.menuOpen ?? false,
        onMenuOpenChange: () => {},
        ...(props.onRegenerate ? { onRegenerate: props.onRegenerate } : {}),
      }),
    );
  });
}

describe("MessageActions — copy", () => {
  it("copies the answer text to the clipboard and flips to the copied glyph", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    renderActions({ text: "the answer prose" });
    const btn = container.querySelector<HTMLButtonElement>('[data-testid="copy-message"]');
    expect(btn).not.toBeNull();
    expect(btn?.getAttribute("aria-label")).toBe("Copy message");

    await act(async () => {
      btn!.click();
      await Promise.resolve();
    });

    expect(writeText).toHaveBeenCalledWith("the answer prose");
    expect(btn?.getAttribute("aria-label")).toBe("Copied");
  });

  it("fails silently when the clipboard write rejects (insecure context)", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("blocked"));
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    renderActions({ text: "x" });
    const btn = container.querySelector<HTMLButtonElement>('[data-testid="copy-message"]');
    await act(async () => {
      btn!.click();
      await Promise.resolve();
    });
    // No throw; label stays at "Copy message" (never reached the success flip).
    expect(btn?.getAttribute("aria-label")).toBe("Copy message");
  });
});

describe("MessageActions — regenerate", () => {
  it("fires onRegenerate when present", () => {
    const onRegenerate = vi.fn();
    renderActions({ text: "x", onRegenerate });
    const btn = container.querySelector<HTMLButtonElement>('[data-testid="regenerate-message"]');
    expect(btn).not.toBeNull();
    act(() => btn!.click());
    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it("omits the regenerate control when no callback is given (run live)", () => {
    renderActions({ text: "x" });
    expect(container.querySelector('[data-testid="regenerate-message"]')).toBeNull();
  });
});

describe("useLongPress", () => {
  function harness(onLongPress: () => void) {
    function Probe(): React.JSX.Element {
      const h = useLongPress(onLongPress);
      return React.createElement("div", { "data-testid": "press", ...h });
    }
    act(() => root.render(React.createElement(Probe)));
    return container.querySelector<HTMLDivElement>('[data-testid="press"]')!;
  }

  // jsdom has no PointerEvent ctor carrying pointerType — build a bare Event
  // of the right type and graft on the fields the handler reads.
  function pointerEvent(
    type: "pointerdown" | "pointermove",
    pointerType: string,
    x = 0,
    y = 0,
  ): Event {
    const e = new Event(type, { bubbles: true });
    Object.assign(e, { pointerType, clientX: x, clientY: y });
    return e;
  }

  it("fires after the hold duration for a touch pointer", () => {
    vi.useFakeTimers();
    const onLongPress = vi.fn();
    const el = harness(onLongPress);

    act(() => el.dispatchEvent(pointerEvent("pointerdown", "touch", 5, 5)));
    expect(onLongPress).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(LONG_PRESS_MS));
    expect(onLongPress).toHaveBeenCalledOnce();
  });

  it("does NOT fire for a mouse pointer (hover toolbar handles desktop)", () => {
    vi.useFakeTimers();
    const onLongPress = vi.fn();
    const el = harness(onLongPress);
    act(() => el.dispatchEvent(pointerEvent("pointerdown", "mouse", 5, 5)));
    act(() => vi.advanceTimersByTime(LONG_PRESS_MS * 2));
    expect(onLongPress).not.toHaveBeenCalled();
  });

  it("is cancelled by movement past the tolerance", () => {
    vi.useFakeTimers();
    const onLongPress = vi.fn();
    const el = harness(onLongPress);
    act(() => el.dispatchEvent(pointerEvent("pointerdown", "touch", 0, 0)));
    act(() => el.dispatchEvent(pointerEvent("pointermove", "touch", 50, 50)));
    act(() => vi.advanceTimersByTime(LONG_PRESS_MS));
    expect(onLongPress).not.toHaveBeenCalled();
  });
});
