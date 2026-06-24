/**
 * Edge middleware -- AuthKit session + strict CSP nonce + security headers (S3.7.2).
 *
 * Composes WorkOS AuthKit via the composable `authkit()` + `handleAuthkitHeaders()`
 * pattern so `x-workos-*` session headers reach Route Handlers (withAuth in
 * `/api/run/stream`), then layers CSP + hardening headers on the response.
 *
 * Per FRONTEND_STYLE_GUIDE §19 and the auto-reject anti-patterns
 * (FE-AP-19, FE-AP-12, FE-AP-4, FE-AP-7), this middleware:
 *
 *   - Calls `authkit()` for session cookie management and internal headers.
 *   - Returns via `handleAuthkitHeaders()` so AuthKit request headers are forwarded.
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
import { authkit, handleAuthkitHeaders } from "@workos-inc/authkit-nextjs";
function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const isDev = process.env.NODE_ENV !== "production";

/**
 * Marker token in the Tauri shell's custom User-Agent (see
 * `src-tauri/src/lib.rs` SHELL_USER_AGENT). When present we relax `connect-src`
 * to allow the macOS Tauri IPC custom-protocol origin, so `invoke()` reaches the
 * shell. Without this the strict CSP blocks the IPC fetch and desktop sign-in is
 * dead. Browser requests never carry this token, so the web CSP is unchanged.
 */
const SHELL_UA_MARKER = "AgentsFrameworkShell";

/**
 * Tauri IPC + asset origins the macOS WKWebview uses for `invoke()` and
 * `convertFileSrc`. Added to `connect-src` ONLY for the shell. `ipc:` covers the
 * IPC custom protocol; the `*.localhost` https/http forms cover wry's asset +
 * fallback hosts across platforms.
 */
const SHELL_IPC_SOURCES =
  "ipc: http://ipc.localhost https://ipc.localhost http://tauri.localhost https://tauri.localhost tauri:";

function buildStrictCSP(nonce: string, isShell: boolean): string {
  const connectSrc = isShell
    ? `connect-src 'self' https://*.workos.com ${SHELL_IPC_SOURCES}`
    : `connect-src 'self' https://*.workos.com`;
  return [
    `default-src 'self'`,
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src 'self' 'nonce-${nonce}'`,
    `img-src 'self' data: blob:`,
    `font-src 'self'`,
    connectSrc,
    `frame-src 'self'`,
    `frame-ancestors 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
    `object-src 'none'`,
  ].join("; ");
}

function buildDevCSP(nonce: string, isShell: boolean): string {
  const shellSrc = isShell ? ` ${SHELL_IPC_SOURCES}` : "";
  return [
    `default-src 'self'`,
    `script-src 'self' 'unsafe-eval' 'nonce-${nonce}'`,
    `style-src 'self' 'unsafe-inline'`,
    `img-src 'self' data: blob:`,
    `font-src 'self'`,
    `connect-src 'self' https://*.workos.com ws://localhost:*${shellSrc}`,
    `frame-src 'self'`,
    `frame-ancestors 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
    `object-src 'none'`,
  ].join("; ");
}

function buildCSP(nonce: string, isShell: boolean): string {
  return isDev ? buildDevCSP(nonce, isShell) : buildStrictCSP(nonce, isShell);
}

export async function middleware(req: NextRequest) {
  const nonce = generateNonce();
  const isShell = (req.headers.get("user-agent") ?? "").includes(SHELL_UA_MARKER);
  const csp = buildCSP(nonce, isShell);

  req.headers.set("x-nonce", nonce);

  const { headers: authHeaders } = await authkit(req);
  authHeaders.set("x-nonce", nonce);

  const res = handleAuthkitHeaders(req, authHeaders);

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
