# P5 — Desktop Auth Callback Root Cause Analysis

## The Problem

There were two separate issues combining to cause the confusing behavior where the desktop app either bounced back to the sign-in screen or stayed in the browser:

### 1. The "lands back on the sign-in screen" bug
When the desktop app successfully completed sign-in in the browser, the deep link navigated the WKWebView to the Cloud Run `desktop-callback` route. That route sealed the session cookie successfully, but its final redirect step was broken behind the Cloud Run proxy:

**Before (Broken on Cloud Run):**
```typescript
return NextResponse.redirect(new URL(DESKTOP_POST_AUTH_PATH, request.nextUrl.origin));
```
`request.nextUrl.origin` incorrectly resolved to the internal Node.js binding (`https://0.0.0.0:3000/`) because Next.js on Cloud Run doesn't natively rewrite origins from proxy headers without specific config.
- The WKWebView received a `307 Redirect` to `https://0.0.0.0:3000/`.
- It attempted to load `0.0.0.0:3000` and immediately failed with `ERR_CONNECTION_REFUSED` / `ERR_SSL_PROTOCOL_ERROR`.
- Because the navigation aborted, WKWebView stayed on the current document (which was the "Sign In" screen that originally triggered the flow).
- Thus, the app appeared to "bounce back" to the sign-in screen despite the cookie being correctly sealed.

### 2. The "stays in browser" bug
To fix an earlier CORS error, the `PROD_URL` in `src-tauri/src/lib.rs` was mistakenly changed to the main traffic revision (`https://agent-frontend-w65nrxwkiq-uc.a.run.app`). That old revision didn't have the desktop auth logic, so it instructed WorkOS to redirect back to the web callback (`.../api/auth/callback`) instead of the deep link (`agentsframework://`). This caused the system browser to complete the flow internally, ignoring the desktop app entirely.

---

## The Fixes

1. **Fixed Origin Construction (`frontend/app/api/auth/desktop-callback/route.ts`)**:
   Constructed the redirect origin directly from the `x-forwarded-host` and `x-forwarded-proto` headers:
   ```typescript
   const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host") ?? request.nextUrl.host;
   const proto = request.headers.get("x-forwarded-proto") ?? "https";
   const origin = `${proto}://${host}`;
   return NextResponse.redirect(new URL(DESKTOP_POST_AUTH_PATH, origin));
   ```

2. **Restored `PROD_URL` (`frontend/src-tauri/src/lib.rs`)**:
   Pointed back to the correct Cloud Run revision serving the new auth logic:
   ```rust
   const PROD_URL: &str = "https://desktop---agent-frontend-w65nrxwkiq-uc.a.run.app";
   ```

---

## Next Steps / Verification

1. Deploy the current frontend code (with the `desktop-callback` fix) to the `desktop` tag on Cloud Run (`agent-prod-gcp-dev`).
2. Run `pnpm tauri:build` (or `cargo tauri dev`) to build/launch the desktop app with the restored `PROD_URL`.
3. Complete the sign-in flow. The system browser should successfully redirect to `agentsframework://`, and the WKWebView should properly redirect back to the authenticated app root (`/`).

## Status — 2026-06-24

**Code fixes confirmed on disk + debug instrumentation removed.** Both fixes from
"The Fixes" are present (origin-from-`x-forwarded-*` in
`frontend/app/api/auth/desktop-callback/route.ts`; `PROD_URL` →
`desktop---agent-frontend-…` in `frontend/src-tauri/src/lib.rs`). The throwaway
`#region agent log` probes (POSTing to `127.0.0.1:7649/7767` and the Rust
`append_debug_log` → local file) were stripped from all three auth files
(`[...workos]/route.ts`, `desktop-callback/route.ts`, `lib.rs`), incl. the now-dead
`OpenOptions`/`Write`/`SystemTime`/`UNIX_EPOCH` imports.

**Verified:** `tsc --noEmit` clean · `cargo check` clean (no unused-import warnings) ·
60/60 frontend auth vitest · 10/10 Rust `auth::tests`.

**Deployed for validation (out-of-band, prod untouched):** built the frontend image
from the working tree (node:20 in-container build passed), pushed
`agent-frontend@sha256:f80e2a30…`, and pointed the **`desktop` tag** at new revision
`agent-frontend-00077-fup` with `--no-traffic`. Prod stays 100% on `00066-kqs`.

**Serve-side probes (desktop tag URL):** `GET /` → 200; `GET /api/auth/desktop-callback`
(no params) → 400 `{"error":{"message":"Invalid desktop callback parameters"}}` — the
refactored route is live and the parse-guard fires.

**Remaining (interactive, owner):** rebuild the Tauri app (`pnpm tauri:build`) against
the restored `PROD_URL` and complete the real sign-in click-through to confirm the
WKWebView lands on `/` (authenticated) instead of bouncing to the sign-in screen.

> Release-blocking follow-ups still open (separate from this fix): revert the temporary
> Tauri `devtools` feature + unconditional `open_devtools()` (`Cargo.toml` / `lib.rs`),
> and tear down the `desktop` Cloud Run tag once validated.