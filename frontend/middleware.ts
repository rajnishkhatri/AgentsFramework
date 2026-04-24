/**
 * Edge middleware -- AuthKit session + strict CSP nonce + security headers (S3.7.2).
 *
 * Composes WorkOS AuthKit middleware (session management) with the existing
 * CSP nonce and security-header pipeline. AuthKit runs first so `withAuth()`
 * can read the session in RSC / Route Handlers; then we layer on CSP + the
 * hardening headers.
 *
 * Per FRONTEND_STYLE_GUIDE §19 and the auto-reject anti-patterns
 * (FE-AP-19, FE-AP-12, FE-AP-4, FE-AP-7), this middleware:
 *
 *   - Delegates to `authkitMiddleware` for session cookie management.
 *   - Generates a per-request CSP nonce (16 bytes -> base64url).
 *   - Builds a CSP that allows the nonce on `script-src` ONLY (no
 *     'unsafe-inline', no 'unsafe-eval').
 *   - Sets HSTS (2y + preload), X-Content-Type-Options nosniff, X-Frame-Options DENY,
 *     Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy
 *     locking down camera/microphone/geolocation.
 *   - Forwards the nonce through the `x-nonce` request header so RSC layouts
 *     can read it via `await headers()` and inject it on inline scripts.
 *
 * The matcher excludes static assets / Next internals so the middleware
 * runs on every page + Route Handler request.
 */

import { type NextRequest } from "next/server";
import { authkitMiddleware } from "@workos-inc/authkit-nextjs";

function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const isDev = process.env.NODE_ENV !== "production";

function buildStrictCSP(nonce: string): string {
  return [
    `default-src 'self'`,
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src 'self' 'nonce-${nonce}'`,
    `img-src 'self' data: blob:`,
    `font-src 'self'`,
    `connect-src 'self' https://*.workos.com`,
    `frame-src 'self'`,
    `frame-ancestors 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
    `object-src 'none'`,
  ].join("; ");
}

function buildDevCSP(nonce: string): string {
  return [
    `default-src 'self'`,
    `script-src 'self' 'unsafe-eval' 'nonce-${nonce}'`,
    `style-src 'self' 'unsafe-inline'`,
    `img-src 'self' data: blob:`,
    `font-src 'self'`,
    `connect-src 'self' https://*.workos.com ws://localhost:*`,
    `frame-src 'self'`,
    `frame-ancestors 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
    `object-src 'none'`,
  ].join("; ");
}

function buildCSP(nonce: string): string {
  return isDev ? buildDevCSP(nonce) : buildStrictCSP(nonce);
}

const workosMiddleware = authkitMiddleware();

export async function middleware(req: NextRequest) {
  const nonce = generateNonce();
  const csp = buildCSP(nonce);

  req.headers.set("x-nonce", nonce);

  const res = await workosMiddleware(req);

  res.headers.set("content-security-policy", csp);
  res.headers.set("strict-transport-security", "max-age=63072000; includeSubDomains; preload");
  res.headers.set("x-content-type-options", "nosniff");
  res.headers.set("x-frame-options", "DENY");
  res.headers.set("referrer-policy", "strict-origin-when-cross-origin");
  res.headers.set(
    "permissions-policy",
    "camera=(), microphone=(), geolocation=(), payment=()",
  );
  return res;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
