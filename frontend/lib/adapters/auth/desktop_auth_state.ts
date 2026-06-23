/**
 * Desktop-auth pure helpers (NO SDK, NO server-only) — unit-testable in
 * isolation. Used by the desktop sign-in / desktop-callback Route Handlers and
 * the WorkOS desktop adapter.
 *
 * P5 Step 2 (system-browser + custom-scheme deep link). The Tauri shell owns the
 * PKCE verifier; these helpers cover the BFF-side request shaping + validation
 * that doesn't need the WorkOS SDK.
 *
 * Design: docs/plans/p5_step2_auth_deeplink.design.md
 */

/**
 * Custom-scheme redirect the Tauri shell registers and WorkOS redirects to.
 * Overridable via env so a different scheme/host stays a one-line change, but
 * MUST byte-match the Tauri `deep-link` scheme AND the WorkOS dashboard entry.
 */
export const DESKTOP_REDIRECT_URI =
  process.env.WORKOS_DESKTOP_REDIRECT_URI ?? "agentsframework://auth/callback";

/** Marker that routes desktop requests away from the cookie-PKCE web flow. */
export const DESKTOP_CLIENT = "desktop";

/** True when the request is the desktop client (gates all desktop behavior). */
export function isDesktopClient(searchParams: URLSearchParams): boolean {
  return searchParams.get("client") === DESKTOP_CLIENT;
}

/**
 * Validated inputs for the desktop sign-in leg. The shell supplies the PKCE
 * `code_challenge` (it keeps the verifier) and a `state` nonce for CSRF.
 */
export interface DesktopSignInParams {
  readonly codeChallenge: string;
  readonly state: string;
}

/** A PKCE S256 challenge is base64url; reject anything else (defense-in-depth). */
const BASE64URL = /^[A-Za-z0-9_-]+$/;

/**
 * Extract + validate the desktop sign-in params. Returns `null` (caller →
 * 400) when the shell didn't supply a well-formed challenge/state, so a
 * malformed desktop request can never fall through to a weaker flow.
 */
export function parseDesktopSignIn(
  searchParams: URLSearchParams,
): DesktopSignInParams | null {
  const codeChallenge = searchParams.get("code_challenge");
  const state = searchParams.get("state");
  if (!codeChallenge || !state) return null;
  // S256 challenge is 43 chars base64url; allow a band rather than pin exactly.
  if (codeChallenge.length < 43 || codeChallenge.length > 128) return null;
  if (!BASE64URL.test(codeChallenge)) return null;
  if (state.length < 8 || state.length > 256) return null;
  return { codeChallenge, state };
}

/** Validated inputs for the desktop callback (code exchange) leg. */
export interface DesktopCallbackParams {
  readonly code: string;
  readonly codeVerifier: string;
  readonly state: string;
}

/**
 * Extract + validate the desktop callback params handed back via the deep link
 * (the shell rewrites the custom-scheme return into this HTTPS navigation).
 * Returns `null` (caller → 400) on anything malformed.
 */
export function parseDesktopCallback(
  searchParams: URLSearchParams,
): DesktopCallbackParams | null {
  const code = searchParams.get("code");
  const codeVerifier = searchParams.get("code_verifier");
  const state = searchParams.get("state");
  if (!code || !codeVerifier || !state) return null;
  // Verifier is 43–128 chars base64url per RFC 7636.
  if (codeVerifier.length < 43 || codeVerifier.length > 128) return null;
  if (!BASE64URL.test(codeVerifier)) return null;
  return { code, codeVerifier, state };
}

/**
 * Where to send the webview after a successful desktop exchange. Kept tiny +
 * same-origin-relative so it can never be an open redirect.
 */
export const DESKTOP_POST_AUTH_PATH = "/";
