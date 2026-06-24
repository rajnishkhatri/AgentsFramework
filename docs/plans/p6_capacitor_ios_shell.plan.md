---
title: P6 — Capacitor 7 iOS shell (safe-area, keyboard, TestFlight)
status: steps-1-3-built (Step 4 gated on Apple enrollment)
created: 2026-06-24
updated: 2026-06-24
owner: Rajnish Khatri
parent: native_wrap_ui_redesign.plan.md
phase: P6 (§4a iOS app-feel, §8 deployment)
related: p5_tauri_macos_shell.plan.md, p5_step2_auth_deeplink.design.md, p5_desktop_auth_callback_issue.md
---

# P6 — Capacitor 7 iOS shell

## Decision (inherited from P5, 2026-06-23)

**Tauri 2 for macOS + Capacitor 7 for iOS (Option C).** P6 is the iOS half: a thin
Capacitor WebView shell hosting the *same* server-dependent web app, with iOS-native
feel (safe-area insets, keyboard handling, momentum scroll) and TestFlight
distribution. Mac Catalyst was rejected (would put an iPad UI on the Mac);
Capacitor-Electron was rejected (~100MB Chromium). See
[`p5_mac_shell_options.research.md`](p5_mac_shell_options.research.md).

**Signing posture:** scaffold + build the iOS project UNSIGNED locally now (works
with Xcode 16 + a free personal team for simulator/device runs); signing,
TestFlight upload, and on-device push of a *distribution* build gate on **Apple
Developer Program enrollment** ($99/yr — same gate as P5 Step 4).

## Toolchain state (verified on disk 2026-06-24)

- ✅ **Xcode 16.0** (`xcodebuild -version` → 16A242d) — required for `cap open ios`,
  CocoaPods, simulator, and the eventual archive/upload.
- ✅ **Node 22.14 / pnpm 10.33** — Capacitor 7 CLI + plugins install into the existing
  `frontend/` pnpm workspace.
- ⚠️ **CocoaPods** — Capacitor iOS uses CocoaPods for the native dep graph. Verify
  `pod --version` before `cap add ios`; install via `brew install cocoapods` if absent
  (does NOT touch the pinned `python@3.13` — unlike the brew-rust issue P5 hit).
- ❌ **0 codesigning identities / no Apple team** (`security find-identity` empty per
  P5) → confirms TestFlight + distribution signing are blocked on enrollment. A free
  *personal* Apple ID team still allows simulator runs and 7-day device installs.

## Context

P0–P4 shipped the redesigned web app; P4 already landed the **pre-wrap-safe** iOS
CSS (`env(safe-area-inset-*)` padding, `overscroll-behavior: contain`, momentum
scroll, `-webkit-touch-callout: none` with message-text selection preserved, 44pt
touch targets, `@media (hover: hover)` gating, system-font-first stack). P6 wraps
that web app as a native iOS app via **Capacitor 7** so it installs from TestFlight
and feels native — without a SwiftUI rewrite.

**Intended outcome:** a TestFlight build that installs on a device, authenticates
through WorkOS via the **system browser (ASWebAuthenticationSession) → custom-scheme
/ Universal-Link deep-link return**, streams a run token-by-token over SSE, and
handles the iOS keyboard + safe areas correctly.

## The load-bearing architecture decision (verified on disk — same as P5)

**The app is server-dependent — a static export is impossible.** Verified:
- [`frontend/next.config.ts:4`](../../frontend/next.config.ts) → `output: "standalone"`
  (Node server build, **not** `output: "export"`).
- [`frontend/middleware.ts`](../../frontend/middleware.ts) runs **WorkOS AuthKit** edge
  middleware (session cookies + CSP nonce) on every page + route handler.
- BFF API routes under `app/api/` incl. `run/stream` (SSE), `auth/[...workos]`,
  `desktop-callback`, `threads*`, `memory*` — all require the Node runtime.

→ **Capacitor must load the running web app over HTTPS via `server.url`, NOT bundle a
static `webDir`.** This is the iOS analogue of P5's Tauri remote-URL decision.

- **Production:** `server.url` = deployed **Cloud Run BFF** (same origin the web app +
  Mac shell use). The IPA is a thin client; web updates ship via Cloud Run (the shell
  re-ships to TestFlight only on native changes).
- **Dev:** `server.url` = `http://<mac-LAN-ip>:3000` with `server.cleartext: true`
  (a device/simulator can't reach `localhost`; iOS ATS blocks plain HTTP unless
  `cleartext` is set). `pnpm --dir frontend dev` on the Mac.

**Consequence:** the Capacitor `webDir` still needs a non-empty placeholder to satisfy
the CLI, but it is never the loaded surface when `server.url` is set.

## ⚠️ Hard prerequisite — the P5 auth bounce-back

P6 auth **reuses P5's system-browser deep-link flow** (PKCE in the shell, BFF seals
the cookie via `/api/auth/desktop-callback`). That flow currently has an **open
defect on macOS**: after a correct sign-in the bundled app bounces back to the
sign-in screen (cookie-not-persisting vs 401 exchange — undiagnosed, blocked by a
toolchain wall). See
[`p5_desktop_auth_callback_issue.md`](p5_desktop_auth_callback_issue.md) (the
P5/desktop flow that P6 inherits).

**Implication for P6:** do not assume auth works end-to-end on iOS just because the
URL chain is correct. Step 2 below must validate the *cookie-persists-in-WKWebView*
leg on iOS independently — WKWebView cookie-store scoping differs from macOS, and iOS
adds **ASWebAuthenticationSession** (the App-Store-blessed system-browser API) which
shares cookies with Safari differently again. Resolving the macOS bounce-back first
(or in parallel) de-risks P6 auth materially.

## Scope / steps (build order — de-risk auth before polish, mirrors P5)

### Step 1 — Scaffold Capacitor 7 alongside the frontend — (this session, unsigned)
- Install Capacitor 7 into the `frontend/` workspace: `@capacitor/core`, `@capacitor/cli`,
  `@capacitor/ios`, plus the iOS-feel plugins: `@capacitor/keyboard`,
  `@capacitor/status-bar`, `@capacitor/app` (deep-link `appUrlOpen` events), and
  `@capacitor-community/safe-area@^7` (P4 §4a already named this for the keyboard-resize
  bug). Optionally `@capacitor/browser` for the auth tab (or use the native
  ASWebAuthenticationSession via a plugin — see Step 2).
- `capacitor.config.ts`:
  - `appId: "com.agentsframework.app"` (match the Mac shell identifier),
    `appName: "AgentsFramework"`, `webDir: "out"` (placeholder — created below).
  - `server.url` switching: read an env/build flag → Cloud Run prod URL in release,
    LAN dev URL + `cleartext: true` in dev (mirror P5's `AF_SHELL_URL` switch). Keep
    the prod URL pinned to the same Cloud Run origin the Mac shell uses.
  - `ios.scheme` / `server.iosScheme` left default (`capacitor`) unless the BFF CSP
    needs the literal origin allow-listed.
- Add a tiny non-empty `webDir` placeholder (`frontend/capacitor-shell/index.html` or
  reuse a generated `out/`) so the CLI is satisfied; document that it is unused when
  `server.url` is set.
- `cap add ios` → generates `frontend/ios/` (Xcode project + CocoaPods). Add `frontend/ios/`
  build artifacts to `.gitignore` as appropriate (keep the project, ignore `Pods/`,
  `DerivedData`, `App/build`).
- Add `pnpm` scripts: `cap:sync` (`cap sync ios`), `cap:open` (`cap open ios`),
  `cap:run` (`cap run ios`). Mirror the P5 `tauri:*` script convention.
- **Gate (this session):** `cap sync ios` succeeds; `frontend/ios/` Xcode project opens;
  the project builds for the simulator (unsigned, personal team or no-team build) and the
  WebView loads the configured `server.url`. (Device install + TestFlight are Step 4.)

### Step 2 — WorkOS auth on iOS (system browser → deep-link return)

> **Auth-flow logic: ✅ BUILT (TDD, 2026-06-24).** The iOS-side flow logic is
> implemented and unit-tested following @research/tdd_agentic_systems_prompt.md
> (L2 / Reproducible Reality, failure-paths-first). The device round-trip (the
> deep-link return + cookie-persist leg) remains gated on a bundled signed app
> (Step 4) and the inherited P5 bounce-back (⚠️ prereq).
>
> - **Pure helper** [`lib/adapters/auth/ios_deep_link_auth.ts`](../../frontend/lib/adapters/auth/ios_deep_link_auth.ts)
>   — no SDK: PKCE S256 via Web Crypto, the `client=desktop` sign-in URL, deep-link
>   scheme/host validation, and the CSRF-state-guarded rewrite to the HTTPS
>   desktop-callback (verifier injected only on a state match). TS analogue of the
>   proven Rust `src-tauri/src/auth.rs`. **13 tests** incl. the RFC 7636 Appendix B
>   vector; rejection tests (state mismatch / missing params / malformed) written
>   FIRST (anti-Gap-Blindness).
> - **Capacitor adapter** [`lib/adapters/auth/capacitor_ios_auth.ts`](../../frontend/lib/adapters/auth/capacitor_ios_auth.ts)
>   — the `@capacitor/{browser,app}` SDK boundary (F-R2). A DI-friendly controller
>   (`createIosAuthController`) holds the flow; `createCapacitorBridge()` is the only
>   SDK-touching code. **7 tests** via a real in-memory bridge fake (anti-Mock-Addiction),
>   all failure paths (foreign link / state mismatch / no session / single-use replay) first.
> - **Architecture compliance:** `@capacitor/*` added to `SDK_PACKAGES` in the layering
>   guard ([test_frontend_layering.test.ts](../../frontend/tests/architecture/test_frontend_layering.test.ts))
>   so the SDK is confined to `lib/adapters/**`; both new files documented as
>   intentional non-PAIR omissions in the adapter-conformance suite. Typecheck clean;
>   architecture suite + auth suite green (no regressions; the only failing tests in the
>   full run are 4 pre-existing, unrelated env/a11y-stub cases).
> - **Bootstrap wired ✅ (2026-06-24):** [`lib/composition_ios.ts`](../../frontend/lib/composition_ios.ts)
>   (iOS composition root — builds the bridge + controller, intercepts the in-app
>   sign-in link; native-gated via `Capacitor.isNativePlatform()` so the web/Tauri
>   builds are inert) is mounted by the client component
>   [`app/ios-shell-bootstrap.tsx`](../../frontend/app/ios-shell-bootstrap.tsx) in the
>   root layout. The custom URL scheme is registered in
>   [`ios/App/App/Info.plist`](../../frontend/ios/App/App/Info.plist) (`CFBundleURLTypes`
>   → `agentsframework`). `composition_ios.ts` added to the layering guard's composition
>   ring. `cap sync` + simulator build SUCCEEDED; typecheck + arch + auth suites green.
> - **Remaining for Step 2:** run the device/simulator auth round-trip (Step-4-gated:
>   needs a signed/bundled app for the live deep-link return) and validate the
>   cookie-persist leg (⚠️ — the same defect tracked in the P5 issue doc).

- **Reuse the BFF desktop legs** (`?client=desktop` sign-in + `/api/auth/desktop-callback`)
  — they are client-agnostic; no BFF change needed beyond confirming the redirect URI.
- **iOS deep-link mechanics (the new work vs P5):**
  - Register the return either as a **custom URL scheme** (`agentsframework://auth/callback`,
    fastest — add to `Info.plist` `CFBundleURLTypes`) or a **Universal Link**
    (`https://<domain>/auth/callback` + `apple-app-site-association` on the BFF origin —
    App-Store-preferred, no scheme-hijack risk, but needs the AASA file + entitlement).
    Start with the custom scheme (matches the Mac shell + the WorkOS dashboard entry
    already registered), upgrade to a Universal Link before public release if desired.
  - Open WorkOS hosted login via **ASWebAuthenticationSession** (the App-Review-blessed
    system-browser API — shares the Safari session, returns the callback to the app, and
    avoids the `disallowed_useragent` rejection embedded WebViews get). Use a Capacitor
    plugin that wraps it, or `@capacitor/browser` as an interim; PKCE verifier stays in
    JS/native shell, never in a URL.
  - Handle the return via `@capacitor/app` `appUrlOpen` → navigate the WebView to the
    HTTPS `desktop-callback` URL with the verifier (same handoff shape as the Mac shell's
    `handle_deep_link`).
- **Validate the cookie-persist leg explicitly** (see the ⚠️ prereq) — confirm the
  WorkOS session cookie sealed by `desktop-callback` is presented on the subsequent `/`
  request inside the iOS WKWebView. This is the leg the macOS flow is currently failing.
- **Gate:** a real authenticated WorkOS session inside the iOS app (simulator + a device
  if a personal team allows), one streamed run, stop/cancel.

### Step 3 — iOS native-feel (§4a)

> **✅ BUILT (TDD, 2026-06-24).** The native-feel wiring is implemented + unit-tested
> following the same pattern as Step 2 (pure helper + SDK adapter + native-gated
> composition; failure-paths-first; real in-memory bridge fake, no SDK in the
> controller tests). The on-device *feel* verification (real keyboard ride, notch
> clearance on hardware) remains Step-4-gated (signed bundle on a device).
>
> - **Pure helper** [`lib/adapters/native/ios_native_feel.ts`](../../frontend/lib/adapters/native/ios_native_feel.ts)
>   — no SDK: theme→status-bar-style map (case-insensitive, safe `Default`
>   fallback) + keyboard-height→clamped-px-offset (NaN/negative→0) + the
>   `--keyboard-offset` CSS-var name. **9 tests** (unknown/missing theme, garbage
>   height first).
> - **Capacitor adapter** [`lib/adapters/native/capacitor_native_feel.ts`](../../frontend/lib/adapters/native/capacitor_native_feel.ts)
>   — the `@capacitor/{status-bar,keyboard}` SDK boundary (F-R2). DI controller
>   `createNativeFeelController` styles the bar from theme + writes/clears the
>   keyboard offset var; `createCapacitorNativeFeelBridge()` is the only
>   SDK-touching code (uses `keyboardWillShow/Hide` for in-sync lift).
>   **9 tests** via a real in-memory bridge fake (teardown-stops-effects first).
> - **Status bar:** styled to the live `data-theme` and re-styled on every flip —
>   the composition root observes `<html data-theme>` with a `MutationObserver`
>   (next-themes mutates the attribute imperatively).
> - **Keyboard lift:** the composer container at
>   [`app/chat-shell.tsx:703`](../../frontend/app/chat-shell.tsx) now pads
>   `calc(max(0.5rem,var(--safe-bottom)) + var(--keyboard-offset))` with a 200ms
>   transition; the var defaults to `0px` in `:root` (globals.css) so it is inert
>   off-device and the shell overwrites it on keyboard show/hide.
> - **Safe areas:** `viewport-fit=cover` added via the layout `viewport` export so
>   `env(safe-area-inset-*)` resolve to real insets in the WebView (the existing
>   `--safe-*` vars + composer bottom pad then clear the notch / home indicator);
>   `@capacitor-community/safe-area@7` injects the insets natively (config-driven,
>   no runtime `enable()` in v7).
> - **Touch behaviors:** long-press actions + `overscroll-behavior: contain` +
>   momentum scroll are already in the web build (P4, pre-wrap) — no Step-3 code
>   needed; on-device confirmation is part of the Step-4 device pass.
> - **Architecture compliance:** the new SDK adapter is confined to
>   `lib/adapters/native/**` (the `@capacitor/*` packages are already in the
>   layering guard's `SDK_PACKAGES`); both new files documented as intentional
>   non-PAIR omissions in the adapter-conformance suite.
> - **Verified 2026-06-24:** 18 new unit tests green; arch (layering +
>   conformance) + chat-shell + composition + auth suites green; `tsc --noEmit`
>   clean; `cap sync ios` integrated all 5 plugins; iOS simulator
>   **BUILD SUCCEEDED** (unsigned). *(CocoaPods + the brew Ruby-4 upgrade needs
>   `LANG/LC_ALL=en_US.UTF-8` on `cap sync` / `pod install` to dodge an
>   `Encoding::CompatibilityError` — unrelated to app code.)*
> - **Remaining for Step 3:** the on-hardware feel pass (composer actually rides
>   the live keyboard, notch/Dynamic-Island clearance on a device, no whole-page
>   rubber-band) — Step-4-gated (needs a signed bundle on a device).

- **Safe areas:** confirm the P4 `env(safe-area-inset-*)` padding renders correctly under
  the notch / Dynamic Island / home indicator inside the Capacitor WebView; wire
  `@capacitor-community/safe-area` for the cases CSS env() misses (esp. keyboard).
- **Keyboard:** `@capacitor/keyboard` — pin the composer above the keyboard
  (the P4 "keyboard-pinned composer" item, explicitly P6-coupled in the parent plan
  §7/P4); set `resize` mode to avoid the known Capacitor WebView keyboard-resize bug;
  scroll-to-bottom on keyboard show.
- **Status bar:** `@capacitor/status-bar` — style to match `[data-theme]` (light/dark),
  overlay vs inset per the header layout.
- **Touch behaviors:** the P4 long-press message actions + `overscroll-behavior: contain`
  + momentum scroll are already in the web build (pre-wrap); verify they behave natively
  in the WebView (no rubber-band of the whole page, long-press menu fires).
- **Gate:** the app feels native on a device — composer rides the keyboard, no website
  rubber-banding, safe areas clear, theme follows the status bar.

### Step 4 — Signing + TestFlight (gates on Apple Developer enrollment)
- Requires **Apple Developer Program enrollment** (parent §10 Q4 — confirm before this
  step; 0 signing identities today).
- Xcode: set the team, bundle id `com.agentsframework.app`, automatic signing; archive →
  upload to **App Store Connect** → distribute to **TestFlight**.
- Register the Universal-Link domain / push the AASA file if upgrading from the custom
  scheme (Step 2).
- **Gate:** a TestFlight build installs on a tester device; auth + a streamed run work on
  the physical device (the parent P6 gate).

## Files (new — minimal existing-app changes)
- `frontend/capacitor.config.ts` (new — appId, server.url switch, plugins)
- `frontend/package.json` (new `cap:sync` / `cap:open` / `cap:run` scripts + Capacitor deps)
- `frontend/ios/` (new — generated Xcode project + Pods; commit project, gitignore build/Pods)
- `frontend/capacitor-shell/` or `frontend/out/` placeholder `webDir` (unused with `server.url`)
- `frontend/.gitignore` (ignore `ios/App/Pods`, `ios/App/build`, `ios/DerivedData`)
- Possibly `Info.plist` `CFBundleURLTypes` (custom scheme) — generated, then edited
- BFF: **no change expected** — the `?client=desktop` + `desktop-callback` legs are reused;
  only a possible Universal-Link AASA file if upgrading from the custom scheme (Step 4).

## Verification (per-step gates above, end-to-end)
1. `cap sync ios` clean; `frontend/ios/` opens + builds for simulator; WebView loads
   `server.url`.
2. Sign in via WorkOS through ASWebAuthenticationSession → deep-link return; **session
   cookie persists** in the iOS WebView; a run streams token-by-token; stop/cancel works.
3. Composer pinned above the keyboard; safe areas clear; status bar themed; no website
   rubber-banding; long-press actions fire.
4. TestFlight build installs on a device; auth + stream work on physical hardware.

## Dependencies / open questions (gate this phase — see parent §10)
- **Apple Developer Program enrollment** (Q4) — REQUIRED for TestFlight + distribution
  signing (0 identities today). Steps 1–3 run unsigned (simulator + personal-team device);
  only Step 4 gates on it.
- **P5 auth bounce-back** ([`p5_desktop_auth_callback_issue.md`](p5_desktop_auth_callback_issue.md))
  — the inherited cookie-persist defect (see ⚠️ prereq). Resolve
  on macOS first/in parallel; re-validate the same leg on iOS WKWebView.
- **Deep-link mechanism** — custom scheme now vs Universal Link before release (needs the
  AASA file + entitlement). Confirm the WorkOS dashboard redirect URI covers the chosen
  form.
- **iOS scope** (Q3) — full phone layout (P3 mobile drawer is done) vs iPad-acceptable
  first. P3 already shipped the mobile thread-rail drawer + container queries, so full
  phone is reachable.
- **Font-per-platform** (Q1) — system-font-first stack already in (P4 §4c), so iOS inherits
  SF for free; confirm whether to drop Geist inside the wrap.
- **Cleartext dev URL** — confirm using the Mac LAN IP + `server.cleartext` for dev (vs a
  tunnel) is acceptable; never ship `cleartext` in release.

## Out of scope
- P5 (Tauri macOS) — its own phase; P6 reuses P5's Step-2 auth flow shape.
- Any BFF/runtime change beyond the (already-shipped) desktop auth legs — P6 is
  presentation/packaging only (parent §9 guardrail).
- Push notifications, native share sheets, biometric unlock — post-v1.
