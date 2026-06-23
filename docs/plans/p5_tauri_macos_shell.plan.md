---
title: P5 — Tauri 2 macOS shell (notarized DMG + Sparkle)
status: ready
created: 2026-06-23
updated: 2026-06-23
owner: Rajnish Khatri
parent: native_wrap_ui_redesign.plan.md
phase: P5 (§4b macOS app-feel, §8 deployment)
related: p5_mac_shell_options.research.md
---

# P5 — Tauri 2 macOS shell

## Decision (2026-06-23, after options research)

**Tauri 2 for macOS + Capacitor for iOS (Option C)** — chosen for best-in-class native feel on
each platform (real Mac chrome via Tauri's WKWebView shell, real iOS via Capacitor later in P6),
explicitly NOT Mac Catalyst (rejected: would put an iPad-style UI on the Mac) and NOT
Capacitor+Electron (rejected: ~100MB Chromium, reverses the thin-webview goal). Accepts a second
toolchain (Rust/Tauri alongside Capacitor) as the price of native quality. Full trade-off analysis:
`p5_mac_shell_options.research.md`.

**Signing posture:** build + validate UNSIGNED locally now (works with the current toolchain);
sign/notarize/Sparkle is a final, separate step gated on Apple Developer Program enrollment.

## Toolchain state (verified on disk 2026-06-23)

- ✅ **Xcode 16.0** (full IDE) — used for macOS notarization tooling (`codesign`/`notarytool`)
  and for P6 iOS later.
- ✅ **Rust 1.96** via **rustup** (installed in Step 1) — Tauri's build backend.
  - ⚠️ **Toolchain gotcha (resolved):** Homebrew `rust` was 1.87, but Tauri 2.11's transitive
    deps (`darling`/`plist`/`serde_with`/`time`) now require **rustc ≥ 1.88**, so the build
    failed under brew rust. `brew upgrade rust` is **blocked** — rust depends on `python@3.13`,
    which is intentionally **pinned** in this repo (bumping it would disturb the Python env).
    Fix: installed Rust via **rustup** (`rustup default stable` → 1.96), which sits outside
    brew's dependency graph and leaves brew rust + pinned python untouched. The `tauri:*` npm
    scripts **prepend `$HOME/.cargo/bin` to PATH** so they use the rustup toolchain without
    editing any shell profile.
- ✅ **Tauri CLI 2.11.3** — installed as an npm dev dependency (`@tauri-apps/cli`), NOT the
  cargo global (chosen: scopes the CLI to the pnpm workspace, runs via `pnpm tauri`).
- ❌ **0 codesigning identities** (`security find-identity` empty) → confirms notarization is
  blocked on Apple Developer enrollment ($99/yr). Unsigned local dev is unaffected.

## Context

P0–P4 shipped the redesigned web app (tokens, primitives, chat surface, responsive,
native-feel CSS). P5 wraps it as a native macOS app via **Tauri 2** — a thin Rust shell
hosting a WKWebView — so the app installs as a notarized DMG and self-updates via Sparkle,
without a Swift rewrite (the Path-A "wrap" decision). The goal is a Mac-app feel (custom
titlebar, drag regions, OS theme) over the *same* web codebase that ships to Cloud Run.

**Intended outcome:** a signed, notarized `.dmg` that installs, launches, authenticates
through WorkOS in the WKWebView, streams a run end-to-end, and auto-updates from a Sparkle
appcast — with the macOS chrome (titlebar/traffic-lights/drag) that distinguishes it from a
browser tab.

## The load-bearing architecture decision (verified on disk)

**The app is server-dependent — a static export is impossible.** Verified:
- `frontend/next.config.ts:4` → `output: "standalone"` (Node server build, **not** `export`).
- `frontend/middleware.ts` runs **WorkOS AuthKit** edge middleware (session cookies + CSP nonce)
  on every page + route handler.
- 9 BFF API routes under `app/api/` incl. `run/stream` (SSE), `auth/[...workos]` (OAuth
  callback), `threads*`, `memory*` — all require the Node runtime.

→ **Tauri must load the running web app over HTTP, not bundle static files.** Two URL modes:
- **Production:** point the shell at the deployed **Cloud Run URL** (the same BFF the web app
  uses). The DMG is then a thin client; web updates ship via Cloud Run (shell re-ships only on
  native changes — matches §8).
- **Dev:** point at `http://localhost:3000` (`pnpm --dir frontend dev`).

This makes **WorkOS auth the #1 risk** (§9) — de-risk it FIRST (Step 2), before any titlebar
polish. Research finding (see options doc): **in-webview OAuth is the wrong default in 2026** —
providers + Apple App Review reject embedded-WebView auth (`disallowed_useragent`), and WKWebView
won't hand custom-scheme redirects back to the app cleanly. The correct, P6-shareable pattern is a
**system-browser auth flow** (open WorkOS hosted login in the user's default browser, return via a
custom-scheme deep link / Universal Link, PKCE, no secrets in the app). Plan for that path; only
try plain in-webview if it happens to work for desktop.

## Scope / steps (build order — de-risk auth before polish)

### Step 1 — Scaffold Tauri 2 alongside the frontend — ✅ DONE (2026-06-23)
- ✅ Installed `@tauri-apps/cli` 2.11.3 as a frontend dev dep; `pnpm tauri init --ci` →
  `frontend/src-tauri/` (Rust crate + `tauri.conf.json`). Under `frontend/`, shares the workspace.
- ✅ `tauri.conf.json`: `devUrl`/`frontendDist` = `http://localhost:3000`; identifier
  `com.agentsframework.app`; window 1100×760 + `minWidth 560 / minHeight 480`.
- ✅ **Remote-URL switching wired in `src-tauri/src/lib.rs`:** debug loads the dev `devUrl`;
  release calls `window.navigate(PROD_URL)` to the Cloud Run BFF
  (`https://agent-frontend-590652793393.us-central1.run.app`) on setup — the load-bearing
  "server-dependent app, never bundle static files" decision, now in code.
- ✅ Added `tauri` / `tauri:dev` / `tauri:build` scripts to `frontend/package.json` (each
  prepends `$HOME/.cargo/bin` to PATH → rustup 1.96, see toolchain note above).
- ✅ Installed Rust 1.96 via rustup (brew rust 1.87 too old for Tauri 2.11 deps; brew upgrade
  blocked by pinned python — see toolchain note).
- ✅ **Gate PASSED:** `pnpm tauri:dev` → Next ready on :3000, app crate `Finished` in ~29s,
  `Running target/debug/agentsframework` (native window), WKWebView loaded localhost
  (`GET / 200`) and AuthKit middleware engaged inside the webview (`GET /api/auth/sign-in 307`
  — the in-webview auth redirect, which Step 2 will replace with the system-browser flow).

### Step 2 — WorkOS auth via the system browser — ✅ BUILT 2026-06-23 (E2E gated on Step 4)

**Implemented (verified to the dev limit):**
- BFF (SDK-isolated, web flow untouched): `lib/adapters/auth/desktop_auth_state.ts` (pure
  param/validation helpers) + `lib/adapters/auth/workos_desktop_auth.ts` (server-only:
  `getAuthorizationUrl` with the shell's `code_challenge`; `authenticateWithCode` + `saveSession`);
  `/api/auth/sign-in?client=desktop` branch + new `app/api/auth/desktop-callback/route.ts`.
  **28 unit tests** + adapter-conformance arch test green; typecheck clean.
- Shell (Rust): `src-tauri/src/auth.rs` (PKCE pair + state nonce, sign-in/callback URL building,
  CSRF state guard — **9 unit tests** incl. the RFC 7636 test vector); `lib.rs` wiring of the
  deep-link / opener / single-instance plugins, the `on_navigation` sign-in interceptor, and a
  `create:false` + `from_config` manually-built window. `tauri.conf.json` deep-link scheme +
  capabilities. `cargo test`/`clippy` clean.
- **Runtime-verified in `tauri:dev`:** the interceptor fired on the web sign-in nav, generated a
  real PKCE pair, and opened the system browser at
  `/api/auth/sign-in?client=desktop&code_challenge=…&state=…` → BFF `307` → WorkOS. The verifier
  never appeared in any URL (stays in the shell).
- **Still gated:** the deep-link *return* (`agentsframework://…` → webview) can only be exercised
  from a **bundled `.app` in `/Applications`** (macOS scheme registration) → Step-4 E2E gate.

Original plan notes (now satisfied) below.


- **Spike result (2026-06-23):** in-webview WorkOS sign-in **WORKS** — the user signed in with real
  credentials against the deployed Cloud Run URL and landed authenticated (the "old UI" seen was
  just the stale deployed revision `00066-kqs`, predating the P0–P4 redesign). So the simple
  in-webview path is viable and is kept as the **working interim**.
- **User decision:** build the system-browser + deep-link flow **anyway** (2026 best practice,
  App-Store-safer, reused by P6 iOS).
- **Full design:** `p5_step2_auth_deeplink.design.md` (status: design-for-review). Key findings it
  captures: `getSignInUrl({ redirectUri })` supports a per-call desktop redirect; the callback uses
  **PKCE** (`authenticateWithCode` + a PKCE cookie set in the *browser*) → the load-bearing
  "PKCE-cookie problem" (verifier lives in the system browser, code returns to the shell) →
  resolved via **Option 1**: a desktop sign-in (no PKCE) + a new `/api/auth/desktop-callback`,
  gated behind `?client=desktop` so the web flow is untouched. All shell logic stays in **Rust**
  (web build never imports `@tauri-apps/*`); handoff to the webview is by navigation.
- **macOS constraint:** deep links register only for a **bundled `.app` in `/Applications`** — they
  do NOT fire under `tauri:dev`, so end-to-end verification is **Step-4-gated** (bundling). Logic is
  unit-testable now (BFF route tests + a pure Rust URL-rewrite test).
- **User owns:** add redirect URI `agentsframework://auth/callback` to the WorkOS dashboard; confirm
  Option 1 (no-PKCE desktop legs) is acceptable.
- **Gate:** (unit, now) BFF desktop sign-in/callback + Rust URL rewrite tested; (E2E, Step-4-gated)
  a real authenticated session in the bundled shell + one streamed run + cancel.

### Step 3 — macOS chrome (§4b)
- Custom titlebar: `titleBarStyle: "Overlay"`, `hiddenTitle: true`, set `trafficLightPosition`
  so the stoplights inset cleanly over the app header.
- Draggable regions: add **`data-tauri-drag-region`** to the web header bar (NOT
  `-webkit-app-region` — Tauri attr; must be set per child element). Verify the header drags the
  window and buttons inside it still click.
- OS theme: drive `[data-theme]` from `prefers-color-scheme` (the app already supports both
  themes) so the native window matches system appearance.
- Optional polish: `tauri-plugin-decorum` / rounded-corner inset if the default chrome looks off.

### Step 4 — Signing, notarization, packaging
- Requires **Apple Developer Program enrollment** (§10 Q4 — confirm before this step).
- CI/build pipeline: `tauri build` → `codesign` (Developer ID Application) → `notarytool submit`
  → staple → produce the `.dmg`. Capture the signing identity + notary credentials as secrets.
- **Gate:** the DMG installs on a clean Mac (Gatekeeper passes) and launches.

### Step 5 — Sparkle auto-update
- Tauri updater plugin OR Sparkle: publish an **appcast** (signed `.dmg` + `appcast.xml`), wire
  the updater to its feed URL, sign updates with the EdDSA/Sparkle key.
- **Gate:** an installed older build detects + applies an update from the appcast.

## Files (new — minimal existing app changes: §3 drag-region + maybe a desktop auth redirect)
- `frontend/src-tauri/` (new crate: `tauri.conf.json`, `Cargo.toml`, `src/main.rs`, icons,
  deep-link + opener plugin config for Step 2)
- `frontend/package.json` (new `tauri:dev` / `tauri:build` scripts)
- `frontend/app/chat-shell.tsx` (§3: add `data-tauri-drag-region` to the header — small, additive)
- Possibly a small BFF/auth tweak to emit a custom-scheme deep-link redirect for the desktop
  client (Step 2) — keep behind a client-type check so web is untouched (§9 guardrail).
- CI workflow for sign/notarize/appcast (location TBD — `.github/workflows/`)

## Verification (per-step gates above, end-to-end)
1. `tauri:dev` → shell opens the localhost app; hot-reload works.
2. Sign in via WorkOS through the **system browser → deep-link return**; session persists; a run
   streams token-by-token; stop/cancel works (the §6 controls).
3. Header drags the window; traffic lights positioned; buttons still clickable; theme follows OS.
4. `tauri build` produces a signed+notarized DMG that installs on a clean Mac.
5. Sparkle: older build updates from the appcast.

## Dependencies / open questions (gate this phase — see parent §10)
- **Apple Developer Program enrollment** (Q4) — REQUIRED for notarization (verified: 0 signing
  identities today). Steps 1–3 (scaffold, auth, chrome) run UNSIGNED; only Steps 4–5 gate on it.
- **WorkOS desktop callback** — register the custom-scheme / Universal-Link redirect for the shell;
  confirm AuthKit accepts the deep-link return (Step 2 server-side prerequisite).
- **Font-per-platform** (Q1) — SF-native already first in the stack (v12), so macOS inherits SF
  for free; no blocker, but confirm whether to drop Geist inside the wrap.
- **Distribution** (Q4) — DMG + Sparkle over Mac App Store for v1 (recommended; MAS sandbox
  fights localhost/backend needs).
- **Which URL the release build loads** — pinned Cloud Run prod URL vs a configurable env. Decide
  before Step 4 packaging.

## Out of scope
- P6 (Capacitor iOS) — separate phase; **reuses the Step 2 system-browser auth flow** (same shape).
- Any change to the BFF/runtime wiring beyond the desktop auth redirect — P5 is presentation/
  packaging only (§9 guardrail).
