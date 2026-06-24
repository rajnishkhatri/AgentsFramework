/**
 * ios_deep_link_auth pure-helper tests (P6 Step 2 — Capacitor iOS shell).
 *
 * TDD per @research/tdd_agentic_systems_prompt.md: this is the L2 (Reproducible
 * Reality / contract) layer — deterministic, no SDK, no network. Failure/guard
 * paths are written FIRST (Anti-Pattern 6: Gap Blindness): a malformed or
 * state-mismatched deep link must be REJECTED before we test the accept path,
 * because a callback rewriter that attaches the PKCE verifier to an attacker's
 * `code`/`state` is the dangerous failure.
 *
 * These are the TS analogue of the proven Rust `src-tauri/src/auth.rs` pure
 * helpers (same flow, iOS mechanics): PKCE S256 generation, the desktop sign-in
 * URL the system browser opens, deep-link validation, and the rewrite to the
 * HTTPS desktop-callback that injects the shell-held verifier.
 *
 * Anti-patterns actively avoided:
 *   - Tautological (AP-1): we assert behavioral PROPERTIES + the RFC 7636
 *     Appendix B test vector for the challenge, never re-derive SHA256 inline.
 *   - Determinism Theater (AP-3): no LLM here; everything is exact.
 *   - Mock Addiction (AP-2): zero mocks — pure functions over plain values.
 */

import { describe, expect, it } from "vitest";
import { webcrypto } from "node:crypto";
import {
  newPkceSession,
  challengeForVerifier,
  buildIosSignInUrl,
  isAuthDeepLink,
  buildCallbackUrl,
  type PkceSession,
} from "./ios_deep_link_auth";
import { DESKTOP_REDIRECT_URI } from "./desktop_auth_state";

// jsdom/node: ensure Web Crypto is available for the SHA-256 path.
if (typeof globalThis.crypto === "undefined") {
  // @ts-expect-error -- polyfill for the test runtime only.
  globalThis.crypto = webcrypto;
}

const BASE64URL = /^[A-Za-z0-9_-]+$/;

describe("challengeForVerifier (PKCE S256) [failure + known-vector first]", () => {
  it("matches the RFC 7636 Appendix B test vector (external truth, not re-derived)", async () => {
    // The canonical RFC 7636 verifier→challenge pair. Asserting this proves the
    // S256 transform without reimplementing SHA256 in the test (anti-AP-1).
    const verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
    const expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM";
    expect(await challengeForVerifier(verifier)).toBe(expected);
  });

  it("is deterministic: same verifier → same challenge", async () => {
    const v = "abcdefghijklmnopqrstuvwxyz0123456789-_ABCDEFG";
    expect(await challengeForVerifier(v)).toBe(await challengeForVerifier(v));
  });
});

describe("newPkceSession", () => {
  it("produces an RFC 7636-shaped verifier/challenge/state", async () => {
    const s = await newPkceSession();
    // verifier within RFC 7636 43..=128, base64url.
    expect(s.verifier.length).toBeGreaterThanOrEqual(43);
    expect(s.verifier.length).toBeLessThanOrEqual(128);
    expect(BASE64URL.test(s.verifier)).toBe(true);
    // challenge is the S256 of THIS verifier (binding property, not re-derivation).
    expect(s.challenge).toBe(await challengeForVerifier(s.verifier));
    expect(BASE64URL.test(s.challenge)).toBe(true);
    // state nonce is non-trivial + base64url.
    expect(s.state.length).toBeGreaterThanOrEqual(8);
    expect(BASE64URL.test(s.state)).toBe(true);
  });

  it("is unique per call (fresh verifier + state each time)", async () => {
    const a = await newPkceSession();
    const b = await newPkceSession();
    expect(a.verifier).not.toBe(b.verifier);
    expect(a.state).not.toBe(b.state);
  });
});

describe("buildIosSignInUrl", () => {
  const session: PkceSession = {
    verifier: "v".repeat(43),
    challenge: "c".repeat(43),
    state: "statenonce",
  };

  it("carries client=desktop + the S256 challenge + state", () => {
    const url = buildIosSignInUrl("https://app.example.com", session);
    expect(url.startsWith("https://app.example.com/api/auth/sign-in?")).toBe(true);
    expect(url).toContain("client=desktop");
    expect(url).toContain(`code_challenge=${"c".repeat(43)}`);
    expect(url).toContain("state=statenonce");
  });

  it("NEVER leaks the verifier into the sign-in URL (it stays in the shell)", () => {
    const url = buildIosSignInUrl("https://app.example.com", session);
    expect(url.includes("v".repeat(43))).toBe(false);
  });
});

describe("isAuthDeepLink [reject non-auth links first]", () => {
  it("rejects non-callback schemes/hosts and junk", () => {
    expect(isAuthDeepLink("agentsframework://other/path")).toBe(false);
    expect(isAuthDeepLink("https://app.example.com/api/auth/callback")).toBe(false);
    expect(isAuthDeepLink("not a url")).toBe(false);
    expect(isAuthDeepLink("")).toBe(false);
  });

  it("accepts our registered custom-scheme auth callback", () => {
    expect(
      isAuthDeepLink("agentsframework://auth/callback?code=x&state=y"),
    ).toBe(true);
  });

  it("agrees with the DESKTOP_REDIRECT_URI the BFF/dashboard registered", () => {
    // The deep-link host/scheme MUST match the shared redirect URI constant so
    // iOS, the WorkOS dashboard, and the macOS shell stay byte-aligned.
    expect(isAuthDeepLink(`${DESKTOP_REDIRECT_URI}?code=x&state=y`)).toBe(true);
  });
});

describe("buildCallbackUrl (CSRF state guard) [reject mismatch FIRST]", () => {
  const session: PkceSession = {
    verifier: "theverifier".repeat(4), // 44 chars
    challenge: "c".repeat(43),
    state: "statenonce",
  };

  it("returns null on a state mismatch — verifier is NEVER attached to an attacker code", () => {
    const out = buildCallbackUrl(
      "https://app.example.com",
      "agentsframework://auth/callback?code=abc&state=ATTACKER",
      session,
    );
    expect(out).toBeNull();
  });

  it("returns null when code or state is missing", () => {
    expect(
      buildCallbackUrl(
        "https://app.example.com",
        "agentsframework://auth/callback?state=statenonce",
        session,
      ),
    ).toBeNull();
    expect(
      buildCallbackUrl(
        "https://app.example.com",
        "agentsframework://auth/callback?code=abc",
        session,
      ),
    ).toBeNull();
  });

  it("returns null on a malformed deep link", () => {
    expect(buildCallbackUrl("https://app.example.com", "not a url", session)).toBeNull();
  });

  it("on state match: rewrites to the HTTPS desktop-callback injecting the verifier", () => {
    const out = buildCallbackUrl(
      "https://app.example.com",
      "agentsframework://auth/callback?code=abc123&state=statenonce",
      session,
    );
    expect(out).not.toBeNull();
    expect(out!.startsWith("https://app.example.com/api/auth/desktop-callback?")).toBe(true);
    expect(out!).toContain("code=abc123");
    expect(out!).toContain(`code_verifier=${"theverifier".repeat(4)}`);
    expect(out!).toContain("state=statenonce");
  });
});
