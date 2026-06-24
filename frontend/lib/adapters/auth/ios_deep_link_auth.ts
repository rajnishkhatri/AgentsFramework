/**
 * iOS deep-link auth pure helpers (P6 Step 2 — Capacitor iOS shell).
 *
 * NO Capacitor SDK, NO network, NO `server-only`: pure, unit-testable functions
 * that the Capacitor adapter (`capacitor_ios_auth.ts`) wires up. This is the TS
 * analogue of the proven Rust `src-tauri/src/auth.rs` for the macOS shell — the
 * same RFC 8252 + PKCE system-browser flow, with iOS mechanics:
 *
 *   1. The shell owns the PKCE verifier (RFC 8252 — never dropped). It opens
 *      WorkOS hosted login in the SYSTEM browser carrying only the S256
 *      `code_challenge` + a CSRF `state` nonce.
 *   2. WorkOS returns via the custom-scheme deep link
 *      (`DESKTOP_REDIRECT_URI`), which iOS routes to the app.
 *   3. The shell validates `state` (CSRF) and rewrites the deep link into the
 *      HTTPS `/api/auth/desktop-callback` navigation, injecting the verifier so
 *      the BFF can complete the code exchange and seal the session cookie.
 *
 * The BFF desktop legs (`?client=desktop` sign-in + `desktop-callback`) are
 * client-agnostic and shared with the macOS shell — see `desktop_auth_state.ts`
 * + `workos_desktop_auth.ts`. iOS reuses them unchanged.
 *
 * Architecture: this lives under `lib/adapters/auth/` (auth domain) and is pure;
 * the `@capacitor/*` SDK surface stays in the sibling adapter (F-R2 / A1).
 *
 * Plan: docs/plans/p6_capacitor_ios_shell.plan.md
 */

import { DESKTOP_CLIENT, DESKTOP_REDIRECT_URI } from "./desktop_auth_state";

/** One in-flight sign-in: the verifier we keep + the state nonce we expect back. */
export interface PkceSession {
  readonly verifier: string;
  readonly challenge: string;
  readonly state: string;
}

/** base64url (no padding) encode of raw bytes. */
function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  // btoa is available in browser + node 18+; the adapter runs in the WebView.
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Random base64url string from `byteLength` cryptographically-random bytes. */
function randomBase64Url(byteLength: number): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

/**
 * S256 PKCE challenge for a verifier: base64url(SHA-256(verifier_ascii)).
 * Async because Web Crypto's digest is async. Matches the Rust `challenge_for`.
 */
export async function challengeForVerifier(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(digest));
}

/**
 * Generate a fresh PKCE session. Verifier = 32 random bytes → base64url
 * (43 chars, within RFC 7636's 43–128). State = 16 random bytes → base64url.
 */
export async function newPkceSession(): Promise<PkceSession> {
  const verifier = randomBase64Url(32);
  const state = randomBase64Url(16);
  const challenge = await challengeForVerifier(verifier);
  return { verifier, challenge, state };
}

/**
 * Build the system-browser sign-in URL against `origin`, carrying the desktop
 * client marker, the S256 `code_challenge`, and the `state` nonce. The verifier
 * is deliberately omitted — it stays in the shell.
 */
export function buildIosSignInUrl(origin: string, session: PkceSession): string {
  const url = new URL("/api/auth/sign-in", origin);
  url.searchParams.set("client", DESKTOP_CLIENT);
  url.searchParams.set("code_challenge", session.challenge);
  url.searchParams.set("state", session.state);
  return url.toString();
}

/** Scheme + host the deep link must match, derived from the shared redirect URI. */
const REDIRECT_URL = (() => {
  try {
    return new URL(DESKTOP_REDIRECT_URI);
  } catch {
    return null;
  }
})();

/**
 * True when `url` is our auth callback deep link (matches the scheme + host of
 * `DESKTOP_REDIRECT_URI`, e.g. `agentsframework://auth/callback…`). Anything
 * else (other paths, the HTTPS web callback, junk) is rejected.
 */
export function isAuthDeepLink(url: string): boolean {
  if (!REDIRECT_URL) return false;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return parsed.protocol === REDIRECT_URL.protocol && parsed.host === REDIRECT_URL.host;
}

/**
 * Rewrite the deep-link return into the HTTPS desktop-callback navigation,
 * injecting the stashed `verifier`. Returns `null` if the deep link lacks the
 * expected `code`/`state`, or if `state` doesn't match the in-flight session
 * (CSRF guard — the verifier is only ever attached to a matching state). Mirrors
 * the Rust `callback_url`.
 */
export function buildCallbackUrl(
  origin: string,
  deepLink: string,
  session: PkceSession,
): string | null {
  let incoming: URL;
  try {
    incoming = new URL(deepLink);
  } catch {
    return null;
  }
  const code = incoming.searchParams.get("code");
  const state = incoming.searchParams.get("state");
  if (!code || !state) return null;
  if (state !== session.state) return null; // CSRF: reject mismatched state

  const out = new URL("/api/auth/desktop-callback", origin);
  out.searchParams.set("code", code);
  out.searchParams.set("code_verifier", session.verifier);
  out.searchParams.set("state", state);
  return out.toString();
}
