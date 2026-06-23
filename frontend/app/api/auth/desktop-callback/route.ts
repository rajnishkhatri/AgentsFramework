/**
 * Desktop deep-link callback (P5 Step 2).
 *
 * The Tauri shell captures the custom-scheme return
 * (`agentsframework://auth/callback?code=…&state=…`), looks up the PKCE
 * verifier it stashed at sign-in, and navigates the webview here:
 *   /api/auth/desktop-callback?code=…&code_verifier=…&state=…
 *
 * We exchange the code + verifier and seal the SAME HttpOnly session cookie the
 * web callback sets (via `saveSession`), so the webview is authenticated for the
 * existing BFF routes. This endpoint exists ONLY for the desktop client; the web
 * OAuth callback (`/api/auth/callback`) is untouched.
 *
 * `dynamic = 'force-dynamic'` — session writes hit the request layer (B5).
 *
 * Design: docs/plans/p5_step2_auth_deeplink.design.md
 */

import { type NextRequest, NextResponse } from "next/server";
import {
  parseDesktopCallback,
  DESKTOP_POST_AUTH_PATH,
} from "@/lib/adapters/auth/desktop_auth_state";
import { completeDesktopAuth } from "@/lib/adapters/auth/workos_desktop_auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const params = parseDesktopCallback(request.nextUrl.searchParams);
  if (!params) {
    return NextResponse.json(
      { error: { message: "Invalid desktop callback parameters" } },
      { status: 400 },
    );
  }

  try {
    // Seals the session cookie onto the response for THIS request.
    await completeDesktopAuth(params, request);
  } catch {
    return NextResponse.json(
      { error: { message: "Desktop authentication failed" } },
      { status: 401 },
    );
  }

  // Authenticated: send the webview to the app root (same-origin relative — never
  // an open redirect).
  return NextResponse.redirect(new URL(DESKTOP_POST_AUTH_PATH, request.nextUrl.origin));
}
