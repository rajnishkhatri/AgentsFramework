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

export const dynamic = "force-dynamic";

const callbackHandler = handleAuth();

export async function GET(request: NextRequest, { params }: { params: Promise<{ workos: string[] }> }) {
  const segments = (await params).workos;
  const action = segments[0];

  if (action === "sign-in") {
    const url = await getSignInUrl();
    return NextResponse.redirect(url);
  }

  if (action === "sign-up") {
    const url = await getSignUpUrl();
    return NextResponse.redirect(url);
  }

  if (action === "sign-out") {
    return await signOut();
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
