/**
 * Server-only WorkOS desktop-auth adapter (P5 Step 2).
 *
 * SDK isolation (F-R2 / A1): like `workos_server_sdk.ts`, this confines the
 * `@workos-inc/*` SDK surface for the desktop deep-link flow to
 * `lib/adapters/auth/`. The Route Handlers call these two functions and never
 * name the SDK.
 *
 * The Tauri shell owns the PKCE verifier (RFC 8252 — never dropped). These
 * helpers (a) build the authorize URL using the shell-supplied `code_challenge`
 * — bypassing authkit's cookie-PKCE entirely — and (b) exchange the returned
 * `code` + shell-supplied `code_verifier`, then seal the SAME HttpOnly session
 * cookie the web callback uses via `saveSession`, so the webview is
 * authenticated for the existing BFF routes.
 *
 * Design + rationale (incl. the WorkOS Electron-example pattern this mirrors):
 * docs/plans/p5_step2_auth_deeplink.design.md
 */

import "server-only";
import { getWorkOS, saveSession } from "@workos-inc/authkit-nextjs";
import type { NextRequest } from "next/server";
import {
  DESKTOP_REDIRECT_URI,
  type DesktopSignInParams,
  type DesktopCallbackParams,
} from "./desktop_auth_state";

/**
 * Build the WorkOS hosted-login URL for the desktop client, carrying the
 * shell's PKCE `code_challenge` (S256) and CSRF `state`, redirecting to the
 * custom-scheme deep link. No PKCE cookie is set (the verifier lives in the
 * shell), so this is independent of the web flow's `WORKOS_ENABLE_PKCE`.
 */
export function buildDesktopAuthorizationUrl(
  params: DesktopSignInParams,
): string {
  const clientId = process.env.WORKOS_CLIENT_ID ?? "";
  return getWorkOS().userManagement.getAuthorizationUrl({
    provider: "authkit",
    clientId,
    redirectUri: DESKTOP_REDIRECT_URI,
    state: params.state,
    codeChallenge: params.codeChallenge,
    codeChallengeMethod: "S256",
  });
}

/**
 * Exchange the desktop authorization `code` + shell `code_verifier`, then seal
 * the session cookie onto the response for `request` (the HTTPS desktop-callback
 * navigation). Throws on a failed exchange — the caller maps that to a 4xx.
 */
export async function completeDesktopAuth(
  params: DesktopCallbackParams,
  request: NextRequest,
): Promise<void> {
  const clientId = process.env.WORKOS_CLIENT_ID ?? "";
  const authResponse = await getWorkOS().userManagement.authenticateWithCode({
    clientId,
    code: params.code,
    codeVerifier: params.codeVerifier,
  });
  await saveSession(authResponse, request);
}
