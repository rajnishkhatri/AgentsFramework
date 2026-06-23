---
title: P5 — Tauri 2 macOS shell (notarized DMG + Sparkle)
status: draft
created: 2026-06-23
owner: Rajnish Khatri
parent: native_wrap_ui_redesign.plan.md
phase: P5 (§4b macOS app-feel, §8 deployment)
---

# P5 — Tauri 2 macOS shell

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

This makes **WorkOS OAuth-in-WKWebView the #1 risk** (§9) — de-risk it FIRST (Step 2), before
any titlebar polish, because if auth can't complete the redirect in the webview, nothing else
matters.

## Scope / steps (build order — de-risk auth before polish)

### Step 1 — Scaffold Tauri 2 alongside the frontend
- `pnpm create tauri-app` (or `tauri init`) → `frontend/src-tauri/` (Rust crate +
  `tauri.conf.json`). Keep it under `frontend/` so it shares the workspace.
- `tauri.conf.json`: set `build.devUrl = http://localhost:3000`, `build.frontendDist` pointed at
  the **remote prod URL** for release (or use a `withGlobalTauri`/config-per-env split). Window:
  reasonable default size, `minWidth/minHeight`.
- Add `pnpm tauri:dev` / `pnpm tauri:build` scripts. Confirm `cargo`/Rust toolchain + Xcode CLT
  present (prereq).

### Step 2 — WorkOS AuthKit in WKWebView (DE-RISK FIRST)
- Launch the shell against the deployed URL; attempt full sign-in. The OAuth redirect
  (`/api/auth/[...workos]` ↔ WorkOS hosted login ↔ callback) must complete inside the webview
  and set the session cookie.
- Known failure modes to check: the redirect leaving the app's origin (WorkOS hosted domain)
  and returning; cookie `SameSite`/`Secure` behavior in `tauri://`/`https://` origins; whether
  WorkOS needs the callback origin allow-listed for the webview origin. Decide redirect strategy
  (in-webview vs system browser + deep-link back) based on what actually works.
- **Gate:** a real authenticated session in the shell + one streamed run. If this can't be made
  to work in-webview, escalate to a system-browser-auth + custom-scheme deep-link flow before
  proceeding.

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

## Files (new — no existing app code changes expected, except §3 web tweaks)
- `frontend/src-tauri/` (new crate: `tauri.conf.json`, `Cargo.toml`, `src/main.rs`, icons)
- `frontend/package.json` (new `tauri:dev` / `tauri:build` scripts)
- `frontend/app/chat-shell.tsx` (§3: add `data-tauri-drag-region` to the header — small, additive)
- CI workflow for sign/notarize/appcast (location TBD — `.github/workflows/`)

## Verification (per-step gates above, end-to-end)
1. `pnpm tauri:dev` → shell opens the localhost app; hot-reload works.
2. Sign in via WorkOS **inside the shell**; session persists; a run streams token-by-token;
   stop/cancel works (the §6 controls).
3. Header drags the window; traffic lights positioned; buttons still clickable; theme follows OS.
4. `tauri build` produces a signed+notarized DMG that installs on a clean Mac.
5. Sparkle: older build updates from the appcast.

## Dependencies / open questions (gate this phase — see parent §10)
- **Apple Developer Program enrollment** (Q4) — REQUIRED for notarization. Confirm before Step 4.
- **Font-per-platform** (Q1) — SF-native already first in the stack (v12), so macOS inherits SF
  for free; no blocker, but confirm whether to drop Geist inside the wrap.
- **Distribution** (Q4) — DMG + Sparkle over Mac App Store for v1 (recommended; MAS sandbox
  fights localhost/backend needs).
- **Which URL the release build loads** — pinned Cloud Run prod URL vs a configurable env. Decide
  before Step 4 packaging.

## Out of scope
- P6 (Capacitor iOS) — separate phase; shares the auth-in-webview learning from Step 2.
- Any change to the BFF/runtime wiring — P5 is presentation/packaging only (§9 guardrail).
