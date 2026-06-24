/**
 * Capacitor native-feel adapter (P6 Step 3) — the `@capacitor/{status-bar,
 * keyboard}` + safe-area SDK boundary.
 *
 * Architecture (F-R2 / A1): the ONLY iOS native-feel file that may import the
 * Capacitor SDK. All decision LOGIC (theme → status-bar style, keyboard height →
 * clamped offset, the CSS var name) lives in the pure `ios_native_feel` helper;
 * this file WIRES it to the native plugins. Analogue of `capacitor_ios_auth.ts`.
 *
 * Testability: the controller takes its native capabilities through the tiny
 * `IosNativeFeelBridge` port, so unit tests inject a real in-memory fake (no SDK,
 * anti-Mock-Addiction). `createCapacitorNativeFeelBridge()` builds the production
 * bridge from the actual plugins; it is the only SDK-touching code.
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md (Step 3)
 */

import {
  statusBarStyleForTheme,
  keyboardOffsetPx,
  KEYBOARD_OFFSET_VAR,
  type StatusBarStyleName,
} from "./ios_native_feel";

/** Status-bar style passed across the bridge (same names as the helper). */
export type StatusBarStyle = StatusBarStyleName;

/**
 * The native capabilities the native-feel flow needs, abstracted so the
 * controller is SDK-free and unit-testable. Production impl:
 * `createCapacitorNativeFeelBridge()`.
 */
export interface IosNativeFeelBridge {
  /** Style the iOS status bar (light/dark glyphs). */
  setStatusBarStyle(style: StatusBarStyle): void;
  /** Set a custom property on the document root (consumed by globals.css). */
  setRootCssVar(name: string, value: string): void;
  /** Register a keyboard-show handler; `height` is the keyboard height in px. */
  onKeyboardShow(handler: (height: number) => void): void;
  /** Register a keyboard-hide handler. */
  onKeyboardHide(handler: () => void): void;
}

export interface NativeFeelControllerOptions {
  readonly bridge: IosNativeFeelBridge;
  /** The resolved theme at construction ("light" | "dark" | …). */
  readonly theme: string | null | undefined;
}

export interface NativeFeelController {
  /** Re-style the status bar when the app theme changes. */
  applyTheme(theme: string | null | undefined): void;
  /** Detach keyboard listeners (idempotent). */
  teardown(): void;
}

/**
 * Wire the iOS status bar + keyboard lift:
 *   - set the status-bar style from the initial theme (and on `applyTheme`),
 *   - on keyboard show, write the clamped height to `--keyboard-offset`,
 *   - on keyboard hide, reset it to `0px`.
 *
 * Keyboard handlers are gated by a `disposed` flag so `teardown()` stops all
 * further effects even though the underlying plugin listeners can't always be
 * removed synchronously.
 */
export function createNativeFeelController(
  options: NativeFeelControllerOptions,
): NativeFeelController {
  const { bridge } = options;
  let disposed = false;

  bridge.setStatusBarStyle(statusBarStyleForTheme(options.theme));

  bridge.onKeyboardShow((height) => {
    if (disposed) return;
    bridge.setRootCssVar(KEYBOARD_OFFSET_VAR, `${keyboardOffsetPx(height)}px`);
  });
  bridge.onKeyboardHide(() => {
    if (disposed) return;
    bridge.setRootCssVar(KEYBOARD_OFFSET_VAR, "0px");
  });

  return {
    applyTheme(theme) {
      if (disposed) return;
      bridge.setStatusBarStyle(statusBarStyleForTheme(theme));
    },
    teardown() {
      disposed = true;
    },
  };
}

/**
 * Build the production `IosNativeFeelBridge` from the real Capacitor plugins.
 * This is the SDK-touching code (F-R2); called only from the iOS composition
 * root, never from the controller's unit tests.
 *
 * - Status bar: `@capacitor/status-bar` `StatusBar.setStyle`.
 * - Keyboard: `@capacitor/keyboard` `keyboardWillShow`/`keyboardWillHide`
 *   (the *will* variants fire before the animation, so the composer lifts in
 *   sync rather than after a visible jump). `info.keyboardHeight` is the px
 *   height.
 * - Safe area: `@capacitor-community/safe-area@7` injects the
 *   `env(safe-area-inset-*)` values into the WebView automatically once the
 *   plugin is installed + synced (config-driven, no runtime `enable()` call in
 *   v7) — so the notch / Dynamic Island / home-indicator insets the layout
 *   already reads (globals.css `--safe-*`) resolve with no code here.
 * - CSS var writes go to `document.documentElement.style` (the `:root` the
 *   layout's padding reads).
 */
export async function createCapacitorNativeFeelBridge(): Promise<IosNativeFeelBridge> {
  const { StatusBar, Style } = await import("@capacitor/status-bar");
  const { Keyboard } = await import("@capacitor/keyboard");

  const styleFor = (name: StatusBarStyle): (typeof Style)[keyof typeof Style] => {
    switch (name) {
      case "Dark":
        return Style.Dark;
      case "Light":
        return Style.Light;
      default:
        return Style.Default;
    }
  };

  return {
    setStatusBarStyle: (style) => {
      void StatusBar.setStyle({ style: styleFor(style) }).catch(() => {});
    },
    setRootCssVar: (name, value) => {
      document.documentElement.style.setProperty(name, value);
    },
    onKeyboardShow: (handler) => {
      void Keyboard.addListener("keyboardWillShow", (info) => {
        handler(info.keyboardHeight);
      });
    },
    onKeyboardHide: (handler) => {
      void Keyboard.addListener("keyboardWillHide", () => {
        handler();
      });
    },
  };
}
