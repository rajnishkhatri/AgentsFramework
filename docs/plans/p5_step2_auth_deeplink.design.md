---
title: P5 Step 2 — desktop auth design (system browser + custom-scheme deep link)
status: implemented (E2E gated on Step 4 bundling)
created: 2026-06-23
updated: 2026-06-23
owner: Rajnish Khatri
parent: p5_tauri_macos_shell.plan.md
related: p5_mac_shell_options.research.md
---

> **2026-06-23 revision:** the original Option 1 (skip PKCE) / Option 2 (carry verifier) framing
> was replaced after external research. RFC 8252 **requires** PKCE for native apps and names
> custom-scheme interception as the exact risk PKCE mitigates — so "skip PKCE" is an anti-pattern.
> The chosen design is the **WorkOS-official Electron-example pattern** (shell holds the verifier)
> combined with `authkit-nextjs`'s exported **`saveSession()`** to mint the webview cookie. See
> "Chosen design" below; the old options are kept at the bottom as rejected-alternatives for the
> record.

# P5 Step 2 — desktop auth: system browser + deep link

## Decision context

- **In-webview sign-in WORKS** (verified by the user's spike against the deployed Cloud Run URL,
  2026-06-23 — signed in with real credentials, landed authenticated; the "old UI" was just the
  stale deployed revision `00066-kqs`, which predates the P0–P4 redesign). So the simple path is
  viable for desktop today.
- **User chose to build the system-browser + deep-link flow anyway** — it's the 2026 best practice,
  App-Store-safer, and the flow P6 (iOS) reuses. This doc designs that flow.
- In-webview auth is retained as the **working interim / fallback** until this lands and is
  verified on a bundled app.

## What's true on disk today (verified)

- Auth = WorkOS AuthKit (`@workos-inc/authkit-nextjs@^2.0.0`). Session = **HttpOnly + Secure +
  SameSite=Strict** cookie set by the callback. JWT never in localStorage.
- `app/api/auth/[...workos]/route.ts` dispatches `sign-in` / `sign-up` / `sign-out` / `callback`.
  `getSignInUrl()` builds the authorize URL; `handleAuth()` runs the callback.
- **`getSignInUrl({ redirectUri })` accepts a per-call `redirectUri` override** (verified in
  `dist/esm/types/auth.d.ts`). So a desktop sign-in can request `redirect_uri =
  agentsframework://auth/callback`.
- **PKCE is in play.** The callback exchange is
  `userManagement.authenticateWithCode({ clientId, code, codeVerifier })` — note **no redirect_uri
  at exchange time** (PKCE binds the code, not redirect_uri match). The `codeVerifier` is read from
  a **PKCE cookie** (`PKCE_COOKIE_NAME`) that `getSignInUrl()` sets at authorize time.
  → **This is the load-bearing gotcha (see §"The PKCE-cookie problem").**
- The React app does NOT import any `@tauri-apps/*` JS today. **Keep it that way** — the same
  Next build ships to the browser; coupling it to Tauri JS would violate the §9 web-untouched
  guardrail. All shell logic stays in **Rust**; the handoff to the webview is by **navigation**.
- macOS hard constraint (Tauri docs): **deep links register only for a BUNDLED app installed in
  `/Applications`** — they do NOT fire under `tauri:dev`. So end-to-end verification of this flow
  waits until we can bundle a `.app` (Step 4 territory). Logic is unit-testable now.

## Target flow (happy path)

```
┌─────────────┐   1. click "Sign in"        ┌──────────────────────┐
│ Tauri shell │ ───(intercept nav)────────▶ │ system browser       │
│  (WKWebView)│    open /api/auth/sign-in    │ (default browser)    │
└─────────────┘    ?client=desktop          └──────────┬───────────┘
       ▲                                                │ 2. BFF: getSignInUrl({
       │                                                │    redirectUri: agentsframework://auth/callback })
       │                                                │    + sets PKCE cookie IN THE BROWSER
       │                                                ▼
       │                                     ┌──────────────────────┐
       │                                     │ WorkOS hosted login   │
       │                                     └──────────┬───────────┘
       │                                                │ 3. redirect to
       │                                                ▼
       │   4. macOS hands deep link        agentsframework://auth/callback?code=…&state=…
       │      to the shell (deep-link plugin, Rust on_open_url)
       │                                                │
       └──── 5. shell navigates WKWebView to ───────────┘
             https://…run.app/api/auth/desktop-callback?code=…&state=…
             → BFF exchanges code, sets session cookie IN THE WEBVIEW → redirect to app (authed)
```

## The PKCE-cookie problem (the crux)

The standard web authorize step sets a **PKCE verifier cookie in whatever browser opened it** —
for a system-browser flow, that's the **system browser**. The code exchange
(`authenticateWithCode`) needs that `codeVerifier`. The deep link returns the `code` to the
**shell/webview**, which does NOT have the system browser's PKCE cookie. So a naive "navigate the
webview to `/api/auth/callback?code=…`" **fails** — no verifier.

## Chosen design (research-backed, PKCE-preserved)

External research (2026-06-23) settled the resolution:
- **RFC 8252 requires PKCE for native apps** regardless of redirect method, and names custom-scheme
  interception as the exact attack PKCE mitigates → **dropping PKCE is not an option.**
  ([RFC 8252](https://www.rfc-editor.org/rfc/rfc8252.html), [oauth.net/native-apps](https://oauth.net/2/native-apps/))
- **WorkOS ships an official Electron AuthKit example** doing this exact flow: the **desktop process
  generates and holds the `code_verifier`**, opens the browser, captures the deep-link `code`, then
  exchanges `code + verifier` itself — the verifier **never enters the browser**, so the PKCE-cookie
  problem simply doesn't arise. ([workos/electron-authkit-example](https://github.com/workos/electron-authkit-example))
- **`authkit-nextjs` exports `saveSession(authResponse, request)`** (confirmed in our installed
  version, `dist/esm/types/session.d.ts:52`) — it mints the **same sealed HttpOnly cookie** the web
  callback uses, from an `AuthenticationResponse`. This bridges "shell did the exchange" → "webview
  has the cookie our 9 BFF routes require." ([authkit-nextjs](https://github.com/workos/authkit-nextjs),
  [WorkOS Sessions](https://workos.com/docs/authkit/sessions))

**Verifier lifetime:** generated in the Rust shell, held in memory only for the duration of one
sign-in, sent exactly once to the BFF over the TLS `https://…run.app` desktop-callback navigation,
never logged, never persisted. (Same wire exposure as the WorkOS Electron example.)

## BFF surface (gated behind a client check; web flow untouched)

All new behavior keys off an explicit `?client=desktop` so the existing web sign-in/callback are
byte-for-byte unchanged (§9 guardrail).

1. **`/api/auth/sign-in?client=desktop&code_challenge=<challenge>&state=<nonce+returnTo>`**
   - `getSignInUrl({ redirectUri: DESKTOP_REDIRECT_URI, state })` — and pass the **shell-supplied
     `code_challenge`** through to the authorize request (PKCE preserved; the shell, not the BFF,
     owns the verifier). Impl note: if `getSignInUrl` won't forward an externally-generated
     challenge, drop to `getWorkOS().userManagement.getAuthorizationUrl({ codeChallenge,
     codeChallengeMethod: 'S256', redirectUri, state, clientId, provider: 'authkit' })` directly for
     the desktop leg — verify which during impl.
   - `DESKTOP_REDIRECT_URI = "agentsframework://auth/callback"` (env-config; **registered in the
     WorkOS dashboard 2026-06-23** ✅; must byte-match the Tauri scheme).
2. **`/api/auth/desktop-callback?code=…&code_verifier=…&state=…`** — new handler:
   - validate `state` nonce (CSRF),
   - `authResponse = getWorkOS().userManagement.authenticateWithCode({ clientId, code, codeVerifier })`,
   - `await saveSession(authResponse, request)` → sets the sealed HttpOnly+Secure+SameSite cookie
     **in the webview**,
   - redirect to the app root (now authenticated). Reuse the existing Cloud-Run host-fix for
     0.0.0.0/localhost redirects.
3. No change to `/api/auth/callback`, `/sign-out`, middleware, or the React app.

**Impl spike (cheap, do first):** confirm (a) the desktop sign-in can inject an external
`code_challenge` (via `getSignInUrl` or `getAuthorizationUrl`), and (b) `saveSession` + a manual
`authenticateWithCode` round-trips to a `withAuth`-readable session. Both are unit-testable with the
SDK mocked, mirroring `auth-route.test.ts`.

## Shell (Tauri / Rust) surface

Plugins (versions verified on crates.io 2026-06-23):
- `tauri-plugin-deep-link = "2.4.9"` — register scheme `agentsframework`, `on_open_url` handler.
- `tauri-plugin-opener = "2.5.4"` — open the system browser for the sign-in URL.
- `tauri-plugin-single-instance = "2.4.2"` (feature `deep-link`) — so a deep link focuses the
  existing window instead of spawning a second instance (required for the app-already-open case).

`tauri.conf.json`:
```json
"plugins": {
  "deep-link": { "desktop": { "schemes": ["agentsframework"] } }
}
```

Also needed in Rust: a PKCE pair generator (`code_verifier` 43–128 chars, `code_challenge` =
base64url(SHA256(verifier))). Crates: `sha2` + `base64` + `rand` (or a small `pkce` crate — pick in
impl). The verifier is held in app state keyed by the `state` nonce for the in-flight sign-in.

`src-tauri/src/lib.rs`:
- register the three plugins,
- `single_instance` handler: on second launch, focus `main` + forward the deep link,
- **Sign-in interception:** when the webview tries to navigate to `/api/auth/sign-in` (the existing
  app sign-in affordance), intercept via an `on_navigation` guard, generate a PKCE pair + state
  nonce, stash the verifier, and `opener` the system browser at
  `<ORIGIN>/api/auth/sign-in?client=desktop&code_challenge=<challenge>&state=<nonce>`. Prefer the
  navigation guard (no JS injection into the shared web build).
- `deep_link().on_open_url(...)`: parse `agentsframework://auth/callback?code=…&state=…`, look up
  the stashed verifier by `state`, build
  `<ORIGIN>/api/auth/desktop-callback?code=…&code_verifier=…&state=…` (ORIGIN = the resolved shell
  URL from Step 1's `target_url()`), and `window.navigate()` the main webview there. Clear the
  verifier after use.

Capabilities: add `deep-link:default`, `opener:default` to `capabilities/default.json`.

## Testing strategy (given the bundled-app constraint)

- **Now (dev, no bundle):**
  - BFF: unit-test `/api/auth/sign-in?client=desktop` (asserts the authorize URL is built with the
    desktop `redirectUri` + the shell-supplied `code_challenge` + `state`) and
    `/api/auth/desktop-callback` (mocked `authenticateWithCode` + `saveSession`; asserts the
    verifier is passed, the session cookie is set, and it redirects), mirroring
    `auth-route.test.ts`'s mock style.
  - Rust: unit-test (a) PKCE pair generation (challenge = base64url(SHA256(verifier)), lengths) and
    (b) the deep-link URL → desktop-callback URL rewrite (pure function).
- **Later (bundled .app in /Applications, Step 4 area):**
  - real end-to-end: click sign-in → system browser → WorkOS → deep link → authed webview + one
    streamed run.
  - This is the ONLY way to exercise macOS scheme registration; it is a **Step-4-gated** gate.

## Dependencies / status

- ✅ **WorkOS dashboard:** redirect URI `agentsframework://auth/callback` added (2026-06-23).
- ✅ **PKCE decision:** preserved end-to-end (verifier in the shell) — RFC 8252 compliant, per the
  WorkOS Electron example. (Old "skip PKCE" option rejected; see below.)
- **Scheme name** `agentsframework` (matches bundle id `com.agentsframework.app`) — change here +
  in `tauri.conf.json` + the WorkOS dashboard together if ever altered.

## Rejected alternatives (for the record)
- **Skip PKCE on the desktop legs** (the original "Option 1") — REJECTED: RFC 8252 requires PKCE for
  native apps and names custom-scheme interception as the exact risk it mitigates.
- **In-webview-only, deep link as focus-helper** (original "Option 3") — REJECTED: doesn't deliver
  the system-browser benefit the user asked for (kept only as the working interim until this lands).

## Out of scope
- Signing/notarization/bundling (Step 4) — but note this flow can't be E2E-verified until then.
- Any change to the web auth flow or React app.
