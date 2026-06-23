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
- ✅ **Rust 1.87** (`cargo`/`rustc` via Homebrew) — Tauri's build backend is ready.
- ❌ **Tauri CLI** absent → `cargo install tauri-cli` (or npm `@tauri-apps/cli`) in Step 1.
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

### Step 1 — Scaffold Tauri 2 alongside the frontend
- `cargo install tauri-cli` (CLI is absent today), then `cargo tauri init` → `frontend/src-tauri/`
  (Rust crate + `tauri.conf.json`). Keep it under `frontend/` so it shares the workspace.
- `tauri.conf.json`: `build.devUrl = http://localhost:3000`; for release, point the window at the
  **remote Cloud Run prod URL** (config-per-env). Window: sensible default size + `minWidth/minHeight`.
- Add `tauri:dev` / `tauri:build` scripts to `frontend/package.json`. Rust 1.87 + Xcode 16 already
  present (verified) — no toolchain install beyond the CLI.
- **Gate:** `tauri:dev` opens a window showing the localhost app; hot-reload works.

### Step 2 — WorkOS auth via the system browser (DE-RISK FIRST)
- **Default to a system-browser flow** (per research): a sign-in action opens WorkOS hosted login
  in the user's default browser via the Tauri opener/shell API; WorkOS redirects to a registered
  **custom-scheme deep link** (e.g. `agentsframework://auth/callback`) that Tauri's deep-link
  plugin captures and hands to the app; the app completes the session (PKCE; no secret in the
  shell). This is the same shape P6 (iOS) will need — design it to be reusable.
- Server-side: register the desktop callback (custom scheme / Universal Link) in WorkOS; confirm
  `/api/auth/[...workos]` + the AuthKit middleware accept the deep-link return. May need a small
  BFF tweak to emit a deep-link redirect for the desktop client.
- Quick spike first: try plain sign-in directly in the WKWebView against the deployed URL — if the
  whole redirect happens to complete in-window (cookie set), great, keep it simple. Otherwise the
  system-browser flow above is the plan.
- **Gate:** a real authenticated session in the shell + one streamed run (token-by-token) + cancel.

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
