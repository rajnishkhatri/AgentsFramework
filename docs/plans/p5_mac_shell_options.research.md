---
title: P5 macOS shell — options research & trade-offs (Tauri vs Capacitor+Electron vs Mac Catalyst)
status: decision-pending
created: 2026-06-23
owner: Rajnish Khatri
parent: native_wrap_ui_redesign.plan.md
---

# macOS shell: the three options, researched (June 2026)

Context: the user wants an **Xcode-centric workflow for Mac + iOS** and prefers **one ecosystem**
(not Tauri + Capacitor side by side). iOS (P6) will be Capacitor regardless — Capacitor IS the
iOS path. The open question is the **Mac** shell. Three options, with current trade-offs.

> **Shared constraint (all three):** our app is server-dependent (`next.config output:standalone`
> + WorkOS AuthKit middleware + 9 BFF routes incl. SSE + OAuth callback). The shell must load the
> deployed Cloud Run URL (or localhost in dev), not bundled static files. This shapes every option.

---

## Cross-cutting finding that reframes the decision: AUTH

The biggest risk (§9 "#1 thing that breaks wrapped auth") resolves the SAME way regardless of Mac
shell, and it pushes AWAY from in-webview OAuth:

- **Embedded WebView OAuth is discouraged in 2026.** Providers + Apple App Review reject raw
  WebView auth (`disallowed_useragent`); WKWebView also won't hand custom-scheme redirects back to
  the app without special handling. Best practice: **system browser (SFSafariViewController / ASWebAuthenticationSession via Capacitor's Browser plugin) + PKCE + a Universal Link / custom-scheme callback**, never client secrets in the app.
- **Implication:** P6 (iOS) will almost certainly need a **system-browser auth flow**, not the
  current cookie-in-webview flow. That's real work — but it's work we do ONCE and it's mostly
  shared. It also means the "auth survives the webview" risk is handled by *not* doing auth in the
  webview.
- For **Mac**: Tauri (WKWebView) hits the same constraint; Electron (Chromium) is more forgiving
  of in-window OAuth but App-Store-hostile; Mac Catalyst inherits the iOS solution for free.

Sources: [WorkOS Apple auth 2025](https://workos.com/blog/apple-app-store-authentication-sign-in-with-apple-2025),
[Capacitor WKWebView non-http redirects #2055](https://github.com/ionic-team/capacitor/issues/2055),
[OAuth2 in Capacitor (capgo)](https://capgo.app/blog/5-steps-to-implement-oauth2-in-capacitor-apps/),
[AppAuth-iOS](https://github.com/openid/AppAuth-iOS).

---

## Option A — Mac Catalyst (run the iOS Capacitor app on Mac)

**What it is:** build the iOS Capacitor app, then tick "Mac (Catalyst)" on the iOS target in
Xcode. One Xcode project, one Capacitor config, WKWebView on both. No Electron, no Tauri, no Rust.

- **Ecosystem:** ✅✅ truly ONE ecosystem + one Xcode project for both platforms — exactly the
  user's stated goal. Auth solved once (system-browser flow) works on both.
- **Native-Mac feel:** 🔶 "iPad-app-on-Mac." Window controls + menu bar come free, but it's not a
  hand-tuned Mac app (no custom titlebar tuning beyond what Catalyst gives). Acceptable-to-good;
  not Cursor-level chrome.
- **Capacitor support:** ⚠️ **NOT official** — Catalyst is an [open Capacitor feature request
  (#5855)](https://github.com/ionic-team/capacitor/issues/5855); official native targets are iOS +
  Android only. BUT enabling Catalyst is an [Xcode target checkbox](https://developer.apple.com/tutorials/mac-catalyst/turning-on-mac-catalyst)
  on the iOS app — it doesn't need Capacitor to "support" it; Capacitor uses WKWebView (Catalyst-
  compatible). Risk: some Capacitor *plugins* may not compile for Catalyst → exclude/replace them.
- **Toolchain today:** ✅ Xcode 16 present; no Rust/Tauri/Electron needed.
- **Signing:** Apple Developer enrollment for distribution (deferred per decision); unsigned local
  run works now.
- **Binary/feel cost:** native WKWebView, light. Distribution = Mac App Store OR notarized .app
  (Catalyst apps can go either way).

**Best when:** consistency + one-project simplicity outweigh bespoke Mac chrome. Strongest match
to "one ecosystem, Xcode for both."

---

## Option B — Capacitor + Electron on Mac (`@capacitor-community/electron`)

**What it is:** Capacitor's community desktop platform — ships a **Chromium + Node Electron** app.

- **Ecosystem:** 🔶 "one config" in name, but a SECOND runtime (Electron/Chromium/Node) distinct
  from the iOS WKWebView. Community-maintained, not core Ionic. So it's not really the single clean
  ecosystem the user wants — it's Capacitor-config-over-Electron.
- **Native-Mac feel:** ❌ heaviest, least native. Bundled Chromium ≈ **80–150MB**, idles **200–300MB
  RAM**. Reverses the redesign's thin-webview / native-Mac §4b goals.
- **Remote URL:** ⚠️ loading our Cloud Run URL is a [hard-coded `loadURL` workaround, not first-
  class `server.url`](https://github.com/capacitor-community/electron/issues/120) (open since 2021).
- **Toolchain today:** ✅ Node already here; no Rust. Fastest builds.
- **App Review:** Electron is App-Store-hostile (not how the user wants to ship per §8 anyway).

**Best when:** you need Windows/Linux desktop too and want web-tech parity there. For Mac-only +
native feel, it's the weakest of the three.

Sources: [capacitor-community/electron](https://github.com/capacitor-community/electron),
[server.url request #120](https://github.com/capacitor-community/electron/issues/120),
[Tauri vs Electron 2026 size/RAM](https://www.pkgpulse.com/guides/electron-vs-tauri-2026).

---

## Option C — Tauri 2 for Mac (the original plan), Capacitor for iOS

**What it is:** Tauri (Rust + WKWebView) shell for Mac; Capacitor for iOS. The original P5 draft.

- **Ecosystem:** ❌ TWO ecosystems (Rust/Tauri + Capacitor) — exactly what the user wants to avoid.
- **Native-Mac feel:** ✅✅ best. WKWebView, **<10MB** bundle, **30–40MB** RAM, ~4× faster start,
  first-class custom titlebar / `data-tauri-drag-region` / Sparkle. Matches §4b/§8 as written.
- **Remote URL:** ✅ clean (`devUrl` / config) — first-class.
- **Toolchain today:** ✅ Rust 1.87 present; needs `cargo install tauri-cli`.
- **Auth:** same system-browser recommendation as the others.

**Best when:** native-Mac quality is the priority and a second toolchain is acceptable.

Sources: [Tauri vs Electron 2026](https://tech-insider.org/tauri-vs-electron-2026/),
[gethopp trade-offs](https://www.gethopp.app/blog/tauri-vs-electron).

---

## Side-by-side

| Axis | A: Mac Catalyst | B: Capacitor+Electron | C: Tauri |
|---|---|---|---|
| One ecosystem / Xcode-for-both (user's goal) | ✅✅ best | 🔶 config-only | ❌ two stacks |
| Native-Mac feel | 🔶 iPad-on-Mac | ❌ Chromium | ✅✅ best |
| Bundle / RAM | ✅ light (WKWebView) | ❌ ~100MB / 200MB+ | ✅ <10MB / ~35MB |
| Remote-URL load (our server-dep app) | ✅ (WKWebView) | ⚠️ workaround | ✅ first-class |
| Capacitor official support | ⚠️ Xcode checkbox, not Cap-official | 🔶 community plugin | n/a |
| New toolchain to add | none | none | Rust + tauri-cli |
| Reuses iOS auth/work | ✅✅ fully | partial | ❌ separate |

## Recommendation (for discussion, user decides)

**Option A (Mac Catalyst)** best fits the stated priorities — one ecosystem, one Xcode project,
auth solved once, no Electron weight, no second (Rust) toolchain. The cost is "iPad-app-on-Mac"
chrome rather than bespoke Mac polish. If hand-tuned native-Mac feel later proves essential, C
(Tauri) is the upgrade path — but it reintroduces a second ecosystem, which the user explicitly
wants to avoid. B (Electron) is the weakest fit here (heaviest, least native, community-only) and
only earns its keep if Windows/Linux desktop becomes a target.

**Decision needed:** A, B, or C → then I write the concrete P5 build plan against it. Sequencing
note: A and B both make P6 (iOS) the natural FIRST build (Catalyst rides on the iOS target);
C lets Mac and iOS proceed independently.
