/**
 * Tests for the Capacitor native-feel controller (P6 Step 3).
 *
 * L2 / Reproducible Reality. The controller wires the iOS status bar + keyboard
 * to the web app via a tiny `IosNativeFeelBridge` port; tests inject a REAL
 * in-memory bridge fake (no SDK, anti-Mock-Addiction) and assert observable
 * effects: the status-bar style set per theme, and the keyboard-offset CSS var
 * written/cleared on show/hide. Failure / edge paths first (anti-Gap-Blindness):
 * teardown stops further effects, an unknown theme falls back safely.
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md (Step 3)
 */

import { describe, it, expect, beforeEach } from "vitest";
import {
  createNativeFeelController,
  type IosNativeFeelBridge,
  type StatusBarStyle,
} from "./capacitor_native_feel";
import { KEYBOARD_OFFSET_VAR } from "./ios_native_feel";

/** A real in-memory bridge — records effects + lets the test fire native events. */
class FakeBridge implements IosNativeFeelBridge {
  styles: StatusBarStyle[] = [];
  cssVars: Record<string, string> = {};
  private kbShow: ((height: number) => void) | null = null;
  private kbHide: (() => void) | null = null;

  setStatusBarStyle(style: StatusBarStyle): void {
    this.styles.push(style);
  }
  setRootCssVar(name: string, value: string): void {
    this.cssVars[name] = value;
  }
  onKeyboardShow(handler: (height: number) => void): void {
    this.kbShow = handler;
  }
  onKeyboardHide(handler: () => void): void {
    this.kbHide = handler;
  }

  // test drivers
  fireShow(height: number): void {
    this.kbShow?.(height);
  }
  fireHide(): void {
    this.kbHide?.();
  }
  get lastStyle(): StatusBarStyle | undefined {
    return this.styles[this.styles.length - 1];
  }
}

let bridge: FakeBridge;

beforeEach(() => {
  bridge = new FakeBridge();
});

describe("createNativeFeelController — failure / edge paths first", () => {
  it("after teardown, a keyboard event no longer writes the offset var", () => {
    const c = createNativeFeelController({ bridge, theme: "dark" });
    c.teardown();
    bridge.fireShow(300);
    // The handler must have been detached — no offset written post-teardown.
    expect(bridge.cssVars[KEYBOARD_OFFSET_VAR]).toBeUndefined();
  });

  it("an unknown theme falls back to the Default status-bar style (no crash)", () => {
    createNativeFeelController({ bridge, theme: "solarized" });
    expect(bridge.lastStyle).toBe("Default");
  });

  it("a hide before any show keeps the offset at 0 (no negative/stale lift)", () => {
    createNativeFeelController({ bridge, theme: "light" });
    bridge.fireHide();
    expect(bridge.cssVars[KEYBOARD_OFFSET_VAR]).toBe("0px");
  });
});

describe("createNativeFeelController — status bar", () => {
  it("sets the status-bar style from the initial theme", () => {
    createNativeFeelController({ bridge, theme: "dark" });
    expect(bridge.lastStyle).toBe("Dark");
  });

  it("applyTheme() re-styles the status bar when the theme flips", () => {
    const c = createNativeFeelController({ bridge, theme: "light" });
    expect(bridge.lastStyle).toBe("Light");
    c.applyTheme("dark");
    expect(bridge.lastStyle).toBe("Dark");
  });
});

describe("createNativeFeelController — keyboard lift", () => {
  it("writes the keyboard height to the offset var on show", () => {
    createNativeFeelController({ bridge, theme: "light" });
    bridge.fireShow(336);
    expect(bridge.cssVars[KEYBOARD_OFFSET_VAR]).toBe("336px");
  });

  it("resets the offset var to 0px on hide", () => {
    createNativeFeelController({ bridge, theme: "light" });
    bridge.fireShow(336);
    bridge.fireHide();
    expect(bridge.cssVars[KEYBOARD_OFFSET_VAR]).toBe("0px");
  });

  it("clamps a garbage keyboard height to 0px", () => {
    createNativeFeelController({ bridge, theme: "light" });
    bridge.fireShow(Number.NaN);
    expect(bridge.cssVars[KEYBOARD_OFFSET_VAR]).toBe("0px");
  });
});
