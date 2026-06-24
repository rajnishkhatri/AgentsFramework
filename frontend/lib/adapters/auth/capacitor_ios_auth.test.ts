/**
 * capacitor_ios_auth adapter tests (P6 Step 2 — Capacitor iOS shell).
 *
 * L2 (Reproducible Reality): the adapter is the `@capacitor/*` SDK boundary
 * (F-R2). All AUTH LOGIC is delegated to the pure `ios_deep_link_auth` helper
 * (already tested); these tests verify only the WIRING contract:
 *   - opens the system browser at the PKCE sign-in URL (verifier never leaks);
 *   - on the auth deep-link return with a MATCHING state, navigates the WebView
 *     to the verifier-injected HTTPS desktop-callback;
 *   - on a MISMATCHED/foreign/malformed deep link, does NOTHING (no navigation,
 *     no verifier hand-off) — failure path FIRST (anti-AP-6).
 *
 * Anti-Mock-Addiction (AP-2): we do NOT mock the Capacitor SDK with 4+ stubs.
 * The adapter takes its browser/app/navigate capabilities via a tiny injected
 * `IosAuthBridge` port, and the tests pass REAL in-memory fakes that record
 * calls. The production composition passes the actual @capacitor plugins.
 */

import { describe, expect, it, beforeEach } from "vitest";
import { webcrypto } from "node:crypto";
import { createIosAuthController, type IosAuthBridge } from "./capacitor_ios_auth";
import { isAuthDeepLink } from "./ios_deep_link_auth";

if (typeof globalThis.crypto === "undefined") {
  // @ts-expect-error -- polyfill for the test runtime only.
  globalThis.crypto = webcrypto;
}

const ORIGIN = "https://app.example.com";

/** A real in-memory bridge that records what the adapter asked it to do, and
 *  lets a test simulate an incoming deep link. No SDK, no mocks-of-mocks. */
function makeFakeBridge() {
  const opened: string[] = [];
  const navigated: string[] = [];
  let handler: ((url: string) => void) | null = null;

  const bridge: IosAuthBridge = {
    openSystemBrowser: async (url) => {
      opened.push(url);
    },
    onDeepLink: (cb) => {
      handler = cb;
    },
    navigateWebView: (url) => {
      navigated.push(url);
    },
  };

  return {
    bridge,
    opened,
    navigated,
    /** Simulate iOS routing a custom-scheme deep link into the app. */
    emitDeepLink: (url: string) => handler?.(url),
    hasHandler: () => handler !== null,
  };
}

describe("createIosAuthController", () => {
  let fake: ReturnType<typeof makeFakeBridge>;

  beforeEach(() => {
    fake = makeFakeBridge();
  });

  it("registers a deep-link listener on construction", () => {
    createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    expect(fake.hasHandler()).toBe(true);
  });

  it("signIn() opens the system browser at the PKCE sign-in URL (verifier never leaks)", async () => {
    const controller = createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    await controller.signIn();

    expect(fake.opened).toHaveLength(1);
    const url = fake.opened[0]!;
    expect(url.startsWith(`${ORIGIN}/api/auth/sign-in?`)).toBe(true);
    expect(url).toContain("client=desktop");
    expect(url).toContain("code_challenge=");
    expect(url).toContain("state=");
    // The opened URL is a real auth sign-in, not the deep-link return.
    expect(isAuthDeepLink(url)).toBe(false);
  });

  // ── Failure paths FIRST (anti-AP-6) ──────────────────────────────────────

  it("ignores a foreign / non-auth deep link (no navigation)", async () => {
    const controller = createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    await controller.signIn();
    fake.emitDeepLink("https://evil.example.com/auth/callback?code=x&state=y");
    fake.emitDeepLink("agentsframework://other/path?code=x&state=y");
    expect(fake.navigated).toEqual([]);
  });

  it("ignores an auth deep link whose state does NOT match the in-flight session", async () => {
    const controller = createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    await controller.signIn();
    // Attacker-supplied state that was never issued by this session.
    fake.emitDeepLink("agentsframework://auth/callback?code=stolen&state=ATTACKER");
    expect(fake.navigated).toEqual([]);
  });

  it("ignores a deep link that arrives with NO in-flight session (no prior signIn)", () => {
    createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    fake.emitDeepLink("agentsframework://auth/callback?code=abc&state=whatever");
    expect(fake.navigated).toEqual([]);
  });

  // ── Accept path ──────────────────────────────────────────────────────────

  it("on a matching deep link: navigates the WebView to the verifier-injected callback", async () => {
    const controller = createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    await controller.signIn();

    // Recover the real state the controller generated from the opened URL.
    const signInUrl = new URL(fake.opened[0]!);
    const state = signInUrl.searchParams.get("state")!;
    expect(state).toBeTruthy();

    fake.emitDeepLink(`agentsframework://auth/callback?code=realcode&state=${state}`);

    expect(fake.navigated).toHaveLength(1);
    const cb = new URL(fake.navigated[0]!);
    expect(cb.origin + cb.pathname).toBe(`${ORIGIN}/api/auth/desktop-callback`);
    expect(cb.searchParams.get("code")).toBe("realcode");
    expect(cb.searchParams.get("state")).toBe(state);
    // The verifier IS handed to the BFF here (it was never in the browser URL).
    expect(cb.searchParams.get("code_verifier")).toBeTruthy();
  });

  it("clears the session after a successful hand-off (single-use verifier)", async () => {
    const controller = createIosAuthController({ origin: ORIGIN, bridge: fake.bridge });
    await controller.signIn();
    const state = new URL(fake.opened[0]!).searchParams.get("state")!;

    fake.emitDeepLink(`agentsframework://auth/callback?code=c1&state=${state}`);
    expect(fake.navigated).toHaveLength(1);

    // A replay of the SAME deep link must not navigate again (session consumed).
    fake.emitDeepLink(`agentsframework://auth/callback?code=c1&state=${state}`);
    expect(fake.navigated).toHaveLength(1);
  });
});
