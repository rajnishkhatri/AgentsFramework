/**
 * iOS shell composition root (P6 Step 2).
 *
 * The native-shell sibling of `composition_browser.ts`: it may name concrete
 * adapters and assemble the iOS auth controller. Kept separate so the Capacitor
 * SDK + native-shell wiring never leak into the web/server bundles (the layering
 * test lists this file in the composition ring).
 *
 * Activation is guarded: `setupIosShellAuth()` is a no-op unless the code is
 * running INSIDE the Capacitor native shell, so importing it from a shared
 * client component is safe on the plain web build.
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md
 */

import {
  createIosAuthController,
  createCapacitorBridge,
} from "./adapters/auth/capacitor_ios_auth";
import {
  createNativeFeelController,
  createCapacitorNativeFeelBridge,
} from "./adapters/native/capacitor_native_feel";

/** The sign-in link the web app renders (intercepted to drive the system browser). */
const SIGN_IN_SELECTOR = 'a[href*="/api/auth/sign-in"]';

let installed = false;
let nativeFeelInstalled = false;

/**
 * Wire the iOS auth flow when running inside the Capacitor shell:
 *   - build the Capacitor bridge (system browser + deep-link + WebView nav),
 *   - construct the controller (registers the deep-link listener),
 *   - intercept the in-app "Sign in" link → drive the system-browser flow.
 *
 * Returns a cleanup function (removes the click listener). Idempotent + a no-op
 * outside the native shell. `origin` defaults to the current page origin (the
 * Capacitor `server.url` the WebView is loaded from).
 */
export async function setupIosShellAuth(origin?: string): Promise<() => void> {
  if (installed) return () => {};
  if (typeof window === "undefined") return () => {};

  // Only run inside the Capacitor native shell. `@capacitor/core` exposes the
  // platform check; gate on it so the plain web/desktop builds are untouched.
  const { Capacitor } = await import("@capacitor/core");
  if (!Capacitor.isNativePlatform()) return () => {};

  installed = true;
  const resolvedOrigin = origin ?? window.location.origin;
  const bridge = await createCapacitorBridge();
  const controller = createIosAuthController({ origin: resolvedOrigin, bridge });

  const onClick = (e: MouseEvent): void => {
    const target = e.target as Element | null;
    const el = target?.closest?.(SIGN_IN_SELECTOR) as HTMLAnchorElement | null;
    if (!el) return;
    // Our own desktop leg (?client=desktop) is opened in the system browser by
    // the bridge — never re-intercept it.
    if ((el.getAttribute("href") ?? "").includes("client=desktop")) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    void controller.signIn();
  };

  // Capture phase so we run before the Next router handles the click.
  document.addEventListener("click", onClick, true);
  return () => {
    document.removeEventListener("click", onClick, true);
    installed = false;
  };
}

/** Read the resolved theme next-themes wrote onto <html data-theme="…">. */
function currentTheme(): string {
  return document.documentElement.getAttribute("data-theme") ?? "";
}

/**
 * Wire the iOS native-feel (P6 Step 3) when running inside the Capacitor shell:
 *   - style the status bar to the current `data-theme` (and on every flip),
 *   - lift the composer above the keyboard via the `--keyboard-offset` var,
 *   - enable the safe-area insets.
 *
 * No-op outside the native shell + idempotent, so it is safe to call from the
 * shared client bootstrap. Returns a cleanup function (detaches the theme
 * observer + the keyboard listeners). `data-theme` is observed with a
 * MutationObserver because next-themes mutates the attribute imperatively (no
 * React prop to subscribe to from outside the tree).
 */
export async function setupIosNativeFeel(): Promise<() => void> {
  if (nativeFeelInstalled) return () => {};
  if (typeof window === "undefined") return () => {};

  const { Capacitor } = await import("@capacitor/core");
  if (!Capacitor.isNativePlatform()) return () => {};

  nativeFeelInstalled = true;
  const bridge = await createCapacitorNativeFeelBridge();
  const controller = createNativeFeelController({
    bridge,
    theme: currentTheme(),
  });

  // next-themes mutates <html data-theme> directly → observe it to re-style.
  const observer = new MutationObserver(() => controller.applyTheme(currentTheme()));
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });

  return () => {
    observer.disconnect();
    controller.teardown();
    nativeFeelInstalled = false;
  };
}
