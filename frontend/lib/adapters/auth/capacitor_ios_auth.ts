/**
 * Capacitor iOS auth adapter (P6 Step 2) — the `@capacitor/*` SDK boundary.
 *
 * Architecture (F-R2 / A1): this is the ONLY iOS-auth file that may import the
 * Capacitor SDK. All flow LOGIC (PKCE generation, sign-in URL, deep-link
 * validation + CSRF guard + callback rewrite) is delegated to the pure
 * `ios_deep_link_auth` helper. This file only WIRES the system browser + the
 * deep-link event + the WebView navigation — the TS analogue of the macOS
 * shell's `src-tauri/src/lib.rs`.
 *
 * Testability: the controller takes its three native capabilities via the tiny
 * `IosAuthBridge` port, so unit tests inject a real in-memory fake (no SDK,
 * anti-Mock-Addiction). `createCapacitorBridge()` builds the production bridge
 * from the actual @capacitor plugins; it is the only SDK-touching code.
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md
 */

import {
  newPkceSession,
  buildIosSignInUrl,
  isAuthDeepLink,
  buildCallbackUrl,
  type PkceSession,
} from "./ios_deep_link_auth";

/**
 * The three native capabilities the auth flow needs, abstracted so the
 * controller is SDK-free and unit-testable. The production implementation is
 * `createCapacitorBridge()`.
 */
export interface IosAuthBridge {
  /** Open `url` in the system browser (ASWebAuthenticationSession / Safari). */
  openSystemBrowser(url: string): Promise<void>;
  /** Register a handler for incoming custom-scheme deep links. */
  onDeepLink(handler: (url: string) => void): void;
  /** Navigate the app WebView to `url` (the HTTPS desktop-callback). */
  navigateWebView(url: string): void;
}

export interface IosAuthControllerOptions {
  /** The BFF origin the WebView + auth routes live on (Cloud Run / dev LAN). */
  readonly origin: string;
  readonly bridge: IosAuthBridge;
}

export interface IosAuthController {
  /** Start sign-in: mint a PKCE session, open WorkOS in the system browser. */
  signIn(): Promise<void>;
}

/**
 * Create the iOS auth controller. Registers the deep-link listener immediately
 * (so a return can be handled), and exposes `signIn()` to kick off the flow.
 * One in-flight session at a time; the verifier is single-use (cleared after a
 * successful hand-off to the BFF).
 */
export function createIosAuthController(
  options: IosAuthControllerOptions,
): IosAuthController {
  const { origin, bridge } = options;
  // In-flight PKCE session (held in the shell; verifier never leaves until the
  // matching deep-link return rewrites it into the desktop-callback URL).
  let session: PkceSession | null = null;

  bridge.onDeepLink((url) => {
    if (!session) return; // no sign-in in flight → ignore
    if (!isAuthDeepLink(url)) return; // foreign / non-auth link → ignore
    const callbackUrl = buildCallbackUrl(origin, url, session);
    if (!callbackUrl) return; // state mismatch / malformed → ignore (CSRF guard)
    // Hand the verifier-injected callback to the WebView, then consume the
    // session (single-use — a replay must not navigate again).
    bridge.navigateWebView(callbackUrl);
    session = null;
  });

  return {
    async signIn() {
      session = await newPkceSession();
      const signInUrl = buildIosSignInUrl(origin, session);
      await bridge.openSystemBrowser(signInUrl);
    },
  };
}

/**
 * Build the production `IosAuthBridge` from the real Capacitor plugins. This is
 * the SDK-touching code (F-R2). Called only from the iOS shell composition /
 * bootstrap; never imported by the controller's unit tests.
 *
 * - System browser: `@capacitor/browser` opens the URL in the in-app system
 *   browser (backed by SFSafariViewController / ASWebAuthenticationSession),
 *   which shares the Safari session and is accepted by WorkOS + App Review
 *   (embedded WKWebView auth is rejected as `disallowed_useragent`).
 * - Deep link: `@capacitor/app` `appUrlOpen` fires when iOS routes the
 *   custom-scheme return into the app.
 * - WebView navigation: a plain top-level `window.location.assign`, caught by
 *   the WebView, lands on the HTTPS desktop-callback that seals the cookie.
 */
export async function createCapacitorBridge(): Promise<IosAuthBridge> {
  const { Browser } = await import("@capacitor/browser");
  const { App } = await import("@capacitor/app");
  return {
    openSystemBrowser: async (url) => {
      await Browser.open({ url });
    },
    onDeepLink: (handler) => {
      void App.addListener("appUrlOpen", (event) => {
        // Close the system browser tab once the callback returns.
        void Browser.close().catch(() => {});
        handler(event.url);
      });
    },
    navigateWebView: (url) => {
      window.location.assign(url);
    },
  };
}
