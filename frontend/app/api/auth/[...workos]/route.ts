/**
 * WorkOS AuthKit Route Handler (S3.7.1).
 *
 * Catch-all route dispatching sign-in, sign-out, and OAuth callback.
 * The callback leg delegates to `handleAuth()` from authkit-nextjs which
 * sets a HttpOnly + Secure + SameSite=Strict session cookie -- the JWT is
 * NEVER stored in localStorage (FE-AP-18 AUTO-REJECT).
 *
 * `dynamic = 'force-dynamic'` because session reads/writes must hit the
 * request layer, not the static cache (B5).
 *
 * Redirect URI: set `NEXT_PUBLIC_WORKOS_REDIRECT_URI` to this app's callback
 * (e.g. `http://localhost:3000/api/auth/callback`) and allowlist the same URL
 * in the WorkOS dashboard. AuthKit does not read `WORKOS_REDIRECT_URI`.
 */

import { type NextRequest, NextResponse } from "next/server";
import { handleAuth, getSignInUrl, getSignUpUrl, signOut } from "@workos-inc/authkit-nextjs";
import { isDesktopClient, parseDesktopSignIn } from "@/lib/adapters/auth/desktop_auth_state";
import { buildDesktopAuthorizationUrl } from "@/lib/adapters/auth/workos_desktop_auth";

export const dynamic = "force-dynamic";

const callbackHandler = handleAuth();

export async function GET(request: NextRequest, { params }: { params: Promise<{ workos: string[] }> }) {
  const segments = (await params).workos;
  const action = segments[0];

  if (action === "sign-in") {
    // Desktop (Tauri) leg: the shell supplies its PKCE code_challenge + state,
    // and we redirect to WorkOS with the custom-scheme deep link. The web flow
    // (no ?client=desktop) is untouched. See p5_step2_auth_deeplink.design.md.
    if (isDesktopClient(request.nextUrl.searchParams)) {
      const desktop = parseDesktopSignIn(request.nextUrl.searchParams);
      if (!desktop) {
        return NextResponse.json(
          { error: { message: "Invalid desktop sign-in parameters" } },
          { status: 400 },
        );
      }
      const url = buildDesktopAuthorizationUrl(desktop);
      // Same redirect shape as the working web sign-in leg below (default 307).
      return NextResponse.redirect(url);
    }
    // Q1 (FR-6): a caller may scope the post-login landing per-CTA with
    // `?returnTo=<path>` (the coach CTA sends `/learn`). This threads AuthKit's
    // native `returnTo` for THIS sign-in only — it does NOT touch the global
    // `returnPathname` default (D1 rejected), so the eval/agent CTAs still land
    // on `/` (FR-7). Web-only by construction: the desktop leg returned above.
    const returnTo = request.nextUrl.searchParams.get("returnTo");
    const url = returnTo
      ? await getSignInUrl({ returnTo })
      : await getSignInUrl();
    return NextResponse.redirect(url);
  }

  if (action === "sign-up") {
    const url = await getSignUpUrl();
    return NextResponse.redirect(url);
  }

  if (action === "sign-out") {
    // Absolute returnTo so WorkOS Logout URI allowlist can match. Defaults to
    // the request origin ("/") — without this, a missing/mismatched dashboard
    // Logout URI leaves sign-out appearing broken (no cookie clear redirect).
    const requested = request.nextUrl.searchParams.get("returnTo");
    const path =
      requested && requested.startsWith("/") && !requested.startsWith("//")
        ? requested
        : "/";
    const returnTo = new URL(path, request.nextUrl.origin).toString();
    return await signOut({ returnTo });
  }

  const res = await callbackHandler(request);

  // Cloud Run standalone: fix redirect from internal 0.0.0.0 to external host
  if (res && res.status >= 300 && res.status < 400) {
    const location = res.headers.get("location");
    if (location && /^https?:\/\/(0\.0\.0\.0|localhost|127\.0\.0\.1)/.test(location)) {
      const host = request.headers.get("x-forwarded-host") || request.headers.get("host");
      const proto = request.headers.get("x-forwarded-proto") || "https";
      const fixedUrl = location.replace(/^https?:\/\/[^/]+/, `${proto}://${host}`);
      return NextResponse.redirect(fixedUrl, res.status as 301 | 302 | 303 | 307 | 308);
    }
  }

  return res;
}
