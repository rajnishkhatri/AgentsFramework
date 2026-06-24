# P5 — Desktop sign-in bounces back to the sign-in screen

> Status: **OPEN** (deferred in favor of Phase 6). The server-side redirect chain
> is curl-verified correct end-to-end; the residual failure is on the webview /
> cookie side and could not be observed under logs because debug builds are
> blocked by a rustc toolchain wall (see §4.4).
>
> Date: 2026-06-24 · Branch: `docs/native-wrap-ui-redesign-plan` · P5 (Tauri 2 macOS shell)
> Related: [`p5_step2_auth_deeplink.design.md`](p5_step2_auth_deeplink.design.md),
> [`p5_tauri_macos_shell.plan.md`](p5_tauri_macos_shell.plan.md)

---

## 1. The issue

In the **bundled macOS app** (`/Applications/AgentsFramework.app`, a Tauri 2
WKWebView shell loading the *remote* GCP Cloud Run BFF origin), the WorkOS
sign-in completes in the system browser, the `agentsframework://auth/callback`
deep link fires and routes back to the app — **but the app then lands back on
the sign-in screen instead of an authenticated session.**

- This is **not** the earlier "redirect goes to a web browser window at `…/`"
  symptom — that was the Launch Services duplicate-handler bug, now fixed
  (exactly one `agentsframework://` owner: `/Applications/AgentsFramework.app`).
- The same flow **works on `localhost:3000`**; it only fails against the
  GCP-hosted origin in the bundle.
- Symptom, verbatim from testing: *"coming back to sign in screen only."*

### What's confirmed working
- Click on the in-app "Sign in" link is intercepted (capture-phase delegation in
  `SIGN_IN_CLICK_SCRIPT`, [lib.rs:47](../../frontend/src-tauri/src/lib.rs)) and
  turned into a top-level navigation, caught by `on_navigation` →
  `begin_desktop_sign_in`.
- The system browser opens the correct WorkOS authorize URL.
  **curl-verified redirect chain** (against the `desktop`-tagged no-traffic rev):
  `GET /api/auth/sign-in?client=desktop&code_challenge=…&state=…`
  → `307` → `api.workos.com/…/authorize?redirect_uri=agentsframework://auth/callback&code_challenge_method=S256&code_challenge=…`
  → `302` AuthKit bootstrap → `307` AuthKit login → `200`.
- The deep link returns to the app (Launch Services now routes it to the single
  registered bundle), `handle_deep_link` finds the in-flight PKCE session, and
  navigates the webview to the HTTPS desktop-callback.

### What fails (one of two, not yet pinned)
Either:
- **(a)** `/api/auth/desktop-callback` returns **401** — the WorkOS code
  exchange failed. A plausible cause: the single-use in-flight `AuthState`
  (`Mutex<Option<PkceSession>>`, [lib.rs:108](../../frontend/src-tauri/src/lib.rs))
  was overwritten by a second `begin_desktop_sign_in` (double-tap / a stray
  re-intercept), so the verifier handed to the callback no longer matches the
  `code_challenge` WorkOS issued the code against → `authenticateWithCode` throws
  → route maps to 401. **OR**
- **(b)** the callback returns **307 with `Set-Cookie`**, but the sealed
  HttpOnly/Secure session cookie **does not persist** in the WKWebView for the
  subsequent `/` navigation → `/` sees no session → middleware bounces to
  sign-in. (Cross-context cookie persistence between the deep-link-triggered
  navigation and the landing page is the suspect.)

---

## 2. Intended solution (per research)

The design is the standard **RFC 8252 (OAuth for native apps) + PKCE** flow,
with the **verifier held in the shell** and the **session cookie sealed by the
BFF**:

1. **PKCE in the shell.** On sign-in, the Rust shell generates a fresh PKCE
   session (verifier + S256 challenge + CSRF `state` nonce),
   [auth.rs `new_pkce_session`](../../frontend/src-tauri/src/auth.rs). The
   verifier never leaves the shell process.
2. **System-browser authorization (not an embedded webview).** Per RFC 8252
   §8.12, the authorization request goes to the user's **system browser** via
   `opener().open_url(...)`, carrying `client=desktop`, the `code_challenge`
   (S256), and `state`. WorkOS is configured with
   `redirect_uri = agentsframework://auth/callback`.
3. **Custom-scheme deep-link return.** WorkOS redirects to
   `agentsframework://auth/callback?code=…&state=…`. macOS Launch Services routes
   the custom scheme to the registered `.app`; the deep-link plugin re-emits it
   into `handle_deep_link`.
4. **State validation + verifier reattachment.** `callback_url` validates the
   returned `state` against the in-flight session (CSRF guard) and rewrites the
   deep link into the **HTTPS** `/api/auth/desktop-callback?code=…&code_verifier=…`
   URL, then the shell navigates the *main webview* there.
5. **BFF seals the session cookie.**
   [`desktop-callback/route.ts`](../../frontend/app/api/auth/desktop-callback/route.ts)
   → `completeDesktopAuth` → `authenticateWithCode({clientId, code, codeVerifier})`
   then `saveSession(authResponse, request)` (WorkOS seals the HttpOnly Secure
   cookie) →
   `307` redirect to `/` (`DESKTOP_POST_AUTH_PATH`).
6. **Authenticated landing.** The webview lands on `/` **carrying the freshly
   sealed cookie**; middleware sees the session and renders the app.

The break is between steps 5 and 6: either the exchange in step 5 throws (cause
a), or the cookie set in step 5 isn't presented on the step-6 request (cause b).

### Research-backed fixes to try (in order)
- **Pin cause first with logs.** The blocker is the toolchain wall (§4.4); once a
  debug build is possible, `handle_deep_link` / `desktop_sign_in` /
  `begin_desktop_sign_in` already `log::info!/warn!`. Add a one-line log of the
  desktop-callback HTTP status + whether `Set-Cookie` came back, and whether the
  follow-up `/` carries `Cookie:`.
- **If cause (a) — verifier overwrite:** make `AuthState` reject a second
  `begin_desktop_sign_in` while one is in flight (or key sessions by `state` in a
  map instead of a single `Option`), so a double-tap can't clobber the verifier
  the issued `code` was bound to.
- **If cause (b) — cookie not persisting:** WKWebView cookie store scoping.
  Confirm the cookie's `Domain`/`SameSite`/`Secure` attributes are accepted for
  the deployed origin in the webview's `WKHTTPCookieStore`, and that the
  deep-link-driven `window.navigate(...)` and the landing `/` share the same data
  store / process pool. RFC 8252 + WorkOS expect the cookie to be a normal
  first-party cookie on the BFF origin; a `SameSite` or partitioned-cookie
  mismatch in WKWebView is the usual culprit for "set but not sent."

---

## 3. Architecture recap (where each piece lives)

| Concern | Location |
| --- | --- |
| PKCE pair + state, URL builders, deep-link rewrite (pure) | `frontend/src-tauri/src/auth.rs` |
| Shell wiring: nav intercept, IPC command, deep-link handler, window build | `frontend/src-tauri/src/lib.rs` |
| Sign-in click → top-level nav (CSP-proof, injected via `eval`) | `SIGN_IN_CLICK_SCRIPT`, `lib.rs:47` |
| ACL permission grant for `desktop_sign_in` | `frontend/src-tauri/permissions/desktop-auth.toml` |
| Capability (window+webview scoped) | `frontend/src-tauri/capabilities/default.json` |
| BFF desktop-callback (code exchange + cookie seal) | `frontend/app/api/auth/desktop-callback/route.ts` |
| WorkOS adapter (`authenticateWithCode` + `saveSession`) | `frontend/lib/adapters/auth/workos_desktop_auth.ts` |
| Shell URL override | `AF_SHELL_URL` env var (`lib.rs` `shell_origin()` / `target_url()`) |

---

## 4. What's been tried (and resolved)

### 4.1 ACL: `Command desktop_sign_in not allowed by ACL` — RESOLVED
Tauri 2 does **not** auto-generate `allow-*` permissions for app-defined
commands (only for plugins). Created
[`permissions/desktop-auth.toml`](../../frontend/src-tauri/permissions/desktop-auth.toml)
with `identifier = "allow-desktop-sign-in"` and referenced it **bare** (not
set-prefixed) in the capability. **Root cause of the persistent ACL error:** the
window is `"create": false` (built at runtime via `WebviewWindowBuilder::from_config`),
so the capability must scope **both** `"windows": ["main"]` **and**
`"webviews": ["main"]` for the grant to reach the runtime-created webview.

### 4.2 IPC mixed-content block — RESOLVED (and IPC abandoned)
On the remote HTTPS page, `invoke('desktop_sign_in')` falls back to
`fetch('ipc://localhost/...')`, which WKWebView blocks as insecure mixed content
(`[blocked] … not allowed to display insecure content from ipc://localhost/…`).
`useHttpsScheme` is Windows/Android only. **Fix:** dropped IPC entirely; the
sign-in click now does a **top-level `window.location.assign(href)`** caught by
the Rust `on_navigation` handler (`is_web_sign_in_nav`). No IPC, no ACL, no
relaxed CSP needed on that path. (The ACL grant from §4.1 remains for the
now-secondary `desktop_sign_in` command.)

### 4.3 Launch Services duplicate handlers — RESOLVED
The deep link initially opened a **web browser** at `…/` instead of the app.
Root cause: **4 on-disk `.app` copies** all claiming `agentsframework://`
(`/Applications`, `~/.Trash`, `target/release/bundle/macos`, a mounted
`/Volumes/dmg.*` DMG) → ambiguous routing. Cleaned: ejected the DMG, emptied the
trash copy, unregistered the build bundle, `lsregister -kill -r` to rebuild, then
re-copied the release `.app` to `/Applications` and `lsregister -f`'d it as the
**sole** owner. (One scare: `lsregister -kill -r` briefly evaporated the
`/Applications` copy alongside a Spotlight `-43` scan error; fixed by re-copying
+ `-f` registering, **not** another `-kill`.) Verified: signing out first
("clean session") did **not** change the outcome — confirming the residual issue
isn't a stale session.

### 4.4 Debug/logging build — BLOCKED (rustc toolchain wall)
`cargo build` (debug) fails: deps (`darling`, `plist`, `serde_with`, `time`)
require **rustc 1.88.0** but the active toolchain is **1.87.0**. Release builds
succeed only because they reuse already-compiled cached deps. **Consequence:** a
logging build is currently impossible, so the §1 (a)-vs-(b) ambiguity could not
be resolved from Rust logs. Diagnosis was attempted via the Web Inspector
Network tab instead (the `tauri` crate's `devtools` feature is temporarily
enabled + `open_devtools()` is called unconditionally in `setup` — **revert
before any real release**, [lib.rs:289-295](../../frontend/src-tauri/src/lib.rs)).
**Unblock options:** `rustup update` / pin a 1.88+ toolchain, or downgrade the
offending deps.

### 4.5 Server-side chain — VERIFIED CORRECT (curl)
The full `/api/auth/sign-in?client=desktop…` → WorkOS authorize → AuthKit chain
is correct end-to-end (see §1 "confirmed working"), so the defect is **not** in
URL construction, the S256 challenge, or the redirect_uri config.

---

## 5. Next step to actually close it (when resumed)

1. **Unblock the debug build** (rustc 1.88+), rebuild with logging.
2. Add a single diagnostic log in the desktop-callback path (status + `Set-Cookie`
   present?) and on the follow-up `/` (does it carry `Cookie:`?).
3. That one observation disambiguates **(a)** 401 exchange failure vs **(b)**
   cookie-not-persisting, then apply the matching fix from §2.
4. Redeploy a **current-UI** `desktop`-tagged GCP revision (the tagged rev shows
   old UI), re-test in the bundle.

### Known release-blocking follow-ups (tracked, not part of this bug)
- Revert the temporary `tauri` `devtools` feature + unconditional
  `open_devtools()` ([lib.rs:289-295](../../frontend/src-tauri/src/lib.rs)).
- Delete the throwaway `frontend/app/mockchat/`.
- Tear down the GCP `desktop` tag when done.
- Real signing/notarization (Step 4); Sparkle auto-update (Step 5).
