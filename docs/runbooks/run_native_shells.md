---
title: Runbook — Run the Tauri 2 macOS app + the Capacitor iOS app (from Xcode / CLI)
status: active
created: 2026-06-24
owner: Rajnish Khatri
related:
  - ../plans/p5_tauri_macos_shell.plan.md
  - ../plans/p6_capacitor_ios_shell.plan.md
  - ../plans/p5_desktop_auth_callback_issue.md
---

# Run the native shells

This runbook gets the two native shells running on your own machine:

- **Tauri 2 — macOS app** (`frontend/src-tauri/`) — a native macOS window wrapping the
  web app. Run with the Tauri CLI (no Xcode).
- **Capacitor 7 — iOS app** (`frontend/ios/`) — an iOS WebView shell. Run from
  **Xcode** (simulator or a physical device) or the Capacitor CLI.

> **Both shells load the *running web app over HTTP(S)*, not a static bundle** — the app
> is `output: "standalone"` (WorkOS middleware + BFF API routes incl. SSE need a Node
> server). So you must have a server reachable at the URL each shell points to:
> - Tauri → `http://localhost:3000` (the Mac dev server).
> - Capacitor → `CAP_SERVER_URL` (a LAN IP for dev) or the Cloud Run prod URL (default).

## 0. One-time prerequisites

| Tool | Check | Install if missing |
|------|-------|--------------------|
| Node 22 / pnpm 10 | `node -v && pnpm -v` | repo standard |
| Rust toolchain | `~/.cargo/bin/rustc --version` | `rustup` (Tauri only) |
| Xcode 16 | `xcodebuild -version` | App Store (iOS only) |
| CocoaPods | `pod --version` | `brew install cocoapods` (iOS only) |
| Apple Developer account | enrolled ✅ | — (you are enrolled) |

> ⚠️ **CocoaPods + brew Ruby 4 bug.** `cap sync` / `pod install` can throw
> `Encoding::CompatibilityError (Unicode Normalization not appropriate for ASCII-8BIT)`.
> **Fix:** always prefix CocoaPods-touching commands with a UTF-8 locale —
> `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 …`. The repo's `cap:sync` script does NOT yet set
> this, so use the explicit form below until it does.

All commands assume you are in `frontend/`:

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent/frontend
```

---

## 1. Tauri 2 — macOS app

### 1a. Dev (hot-reload, recommended for day-to-day)

`tauri dev` starts the Next.js dev server (`pnpm dev` on :3000) **and** opens the native
window pointed at it. One command:

```bash
pnpm tauri:dev
```

- First run compiles the Rust shell (slow, minutes); later runs are fast.
- Edit web code → HMR updates the window. Edit Rust (`src-tauri/src/`) → it rebuilds.
- The window loads `http://localhost:3000` (`devUrl` in
  [`src-tauri/tauri.conf.json`](../../frontend/src-tauri/tauri.conf.json)).

### 1b. Build a bundled `.app`

```bash
pnpm tauri:build
```

Output: `frontend/src-tauri/target/release/bundle/macos/AgentsFramework.app`
(plus a `.dmg`). With no `bundle.macOS.signingIdentity` set, Tauri ad-hoc-signs it —
fine for running locally on this Mac. Gatekeeper-distributable signing/notarization is a
separate task (see §3 note).

> The bundled app still needs a server at `frontendDist` (`http://localhost:3000`). For a
> self-contained prod build, point `frontendDist` at the Cloud Run URL and rebuild —
> **do not commit that change** (dev runs expect localhost).

### 1c. Known issue — auth bounce-back

The desktop WorkOS sign-in currently bounces back to the sign-in screen after a correct
login (cookie-persist vs 401, undiagnosed). Tracked in
[`p5_desktop_auth_callback_issue.md`](../plans/p5_desktop_auth_callback_issue.md). The
shell otherwise runs; expect this on the auth leg until it's resolved.

---

## 2. Capacitor 7 — iOS app

### 2a. Point the shell at a server (pick one)

The shell's `server.url` comes from
[`capacitor.config.ts`](../../frontend/capacitor.config.ts):

- **Prod (default, zero setup):** omit `CAP_SERVER_URL` → loads the Cloud Run BFF
  (`https://agent-frontend-590652793393.us-central1.run.app`). Good for a quick device
  smoke test; no local server needed.
- **Local dev (LAN):** run the dev server bound to all interfaces, then point the shell at
  your Mac's LAN IP (a simulator/device can't reach `localhost`):

  ```bash
  # Terminal A — dev server reachable on the LAN
  pnpm dev -- -H 0.0.0.0          # serves on http://<LAN-IP>:3000

  # Terminal B — sync the shell at the LAN URL (cleartext auto-enabled for http://)
  export CAP_SERVER_URL="http://192.168.86.243:3000"   # this Mac's en0 IP today
  LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 npx cap sync ios
  ```

  > `CAP_SERVER_URL` is read at `cap sync` time (baked into
  > `ios/App/App/capacitor.config.json`). Re-run `cap sync` whenever you change it. The IP
  > can change between networks — re-check with `ipconfig getifaddr en0`. **Never ship a
  > cleartext/LAN URL in a release build.**

### 2b. Sync native deps + open Xcode

```bash
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 npx cap sync ios   # copies web config + pod install
npx cap open ios                                        # opens App.xcworkspace in Xcode
```

> Always open **`App.xcworkspace`** (not `App.xcodeproj`) — the workspace includes the
> CocoaPods. `cap open` does this for you.

### 2c. Signing — set your Apple Team (one-time)

The project uses **automatic** signing but has **no `DEVELOPMENT_TEAM` set yet**, so it
won't sign for a device until you pick your team. Two paths (the GUI path is what actually
pulls your certificate onto this Mac — `security find-identity` shows 0 today):

**GUI (recommended for running from Xcode):**
1. In Xcode, add your Apple ID: **Xcode ▸ Settings ▸ Accounts ▸ +**, sign in.
2. Select the **App** target ▸ **Signing & Capabilities** tab.
3. Check **Automatically manage signing**, pick your **Team** from the dropdown.
4. Xcode downloads the development cert + provisioning profile for
   `com.agentsframework.app`. (`security find-identity -v -p codesigning` should now list
   an *Apple Development* identity.)

> Selecting the Team writes `DEVELOPMENT_TEAM` into `project.pbxproj`. That file is tracked
> — committing it would hardcode your personal Team ID for everyone. **Prefer the `.env`/CLI
> path below for builds, or revert the pbxproj Team change before committing** (treat it as
> a local-only edit, same posture as the temporary Tauri devtools edits).

**`.env`-driven CLI (for scripted / archive builds):**

`xcodebuild` does **not** read `.env` natively, so we pass the Team via an env var. Put
your Team ID in the gitignored `frontend/.env.local` (already gitignored — verified):

```bash
# frontend/.env.local   (NEVER commit — already in .gitignore)
APPLE_TEAM_ID=XXXXXXXXXX        # 10-char Team ID from developer.apple.com ▸ Membership
```

Then build/run from the CLI, sourcing it:

```bash
# load APPLE_TEAM_ID from .env.local into this shell
set -a; . ./.env.local; set +a

# device build (automatic signing uses the passed team; no pbxproj edit needed)
cd ios/App
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 xcodebuild \
  -workspace App.xcworkspace -scheme App \
  -configuration Debug -sdk iphoneos \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" CODE_SIGN_STYLE=Automatic build
```

> Only `APPLE_TEAM_ID` is required for automatic signing — Xcode/`xcodebuild` fetches the
> cert + profile via `-allowProvisioningUpdates`. No raw certificates or passwords go in
> `.env` (manual cert/`.p12` material is out of scope and would be prohibited to handle in
> plaintext anyway).

### 2d. Run

**Simulator (no signing needed):**
- In Xcode, pick an **iPhone 16** simulator in the toolbar ▸ **▶ Run** (`⌘R`).
- Or CLI:
  ```bash
  LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 npx cap run ios   # prompts for a target
  ```
  Auth note: the **system-browser sign-in (ASWebAuthenticationSession) + custom-scheme
  deep-link return** works best on a real device. The simulator is fine for layout,
  keyboard lift, safe areas, and status-bar theming.

**Physical device (needs §2c signing):**
1. Plug in the iPhone, trust the Mac, select it in the Xcode toolbar.
2. **▶ Run**. First install: on the phone, **Settings ▸ General ▸ VPN & Device
   Management** ▸ trust your developer profile.
3. The app opens, loads `server.url`, and the custom URL scheme `agentsframework://`
   (registered in [`Info.plist`](../../frontend/ios/App/App/Info.plist)) routes
   the WorkOS callback back into the app.

### 2e. What to verify (P6 Step 3 native-feel)

- Composer rides up with the on-screen keyboard (the `--keyboard-offset` lift).
- Status bar glyphs flip with the light/dark theme toggle.
- Content clears the notch / Dynamic Island / home indicator (safe-area insets).
- No whole-page rubber-band; long-press on a message shows actions; answer text selectable.

### 2f. Known issue — auth (same as Tauri)

iOS auth reuses the P5 desktop flow, so it inherits the **cookie-persist/401 bounce-back**
(plus WKWebView cookie-scoping differs on iOS). Validate the cookie-persists-after-callback
leg explicitly on device. See `p5_desktop_auth_callback_issue.md`.

---

## 3. Quick reference

| Goal | Command |
|------|---------|
| Tauri dev window | `pnpm tauri:dev` |
| Tauri bundled .app | `pnpm tauri:build` → `src-tauri/target/release/bundle/macos/` |
| Cap sync (prod URL) | `LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 npx cap sync ios` |
| Cap sync (LAN dev) | `CAP_SERVER_URL=http://<LAN-IP>:3000 LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 npx cap sync ios` |
| Open iOS in Xcode | `npx cap open ios` (opens `App.xcworkspace`) |
| iOS simulator build (CLI) | `cd ios/App && xcodebuild -workspace App.xcworkspace -scheme App -sdk iphonesimulator -configuration Debug build CODE_SIGNING_ALLOWED=NO` |
| iOS device build (CLI) | see §2c `.env`-driven block |
| Mac LAN IP | `ipconfig getifaddr en0` |
| List simulators | `xcrun simctl list devices available \| grep iPhone` |
| List signing identities | `security find-identity -v -p codesigning` |

> **Signing/notarization for *distribution*** (Gatekeeper-friendly Tauri `.dmg`,
> TestFlight IPA) is a separate task — this runbook covers *running* the shells (dev +
> personal-device installs), not store distribution.

## Don't-commit checklist

- `frontend/.env.local` — gitignored; holds `APPLE_TEAM_ID` (+ the dev redirect URI).
  Never commit.
- `ios/App/App.xcodeproj/project.pbxproj` — if the GUI signing flow wrote your
  `DEVELOPMENT_TEAM` into it, treat that as a local-only edit (revert before committing).
- `capacitor.config.ts` / `tauri.conf.json` URL changes for a one-off prod build — local
  only; the committed defaults are localhost (Tauri) / Cloud Run (Cap).
