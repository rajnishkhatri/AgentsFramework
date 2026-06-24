---
type: decision-record
title: 'ADR-0001: Tauri 2 (macOS) + Capacitor 7 (iOS) over Electron and native frameworks'
status: accepted
created: 2026-06-24
updated: 2026-06-25
owner: Rajnish Khatri
related: native_wrap_ui_redesign.plan.md, p5_tauri_macos_shell.plan.md, p6_capacitor_ios_shell.plan.md, p5_mac_shell_options.research.md
tags: [decision-record, native-wrap, technology-choice]
---

# ADR-0001: Tauri 2 (macOS) + Capacitor 7 (iOS) over Electron and native frameworks

**Status:** Accepted (2026-06-24).
**Related:** [native_wrap_ui_redesign.plan.md](../plans/native_wrap_ui_redesign.plan.md) · [p5_tauri_macos_shell.plan.md](../plans/p5_tauri_macos_shell.plan.md) · [p6_capacitor_ios_shell.plan.md](../plans/p6_capacitor_ios_shell.plan.md) · [p5_mac_shell_options.research.md](../plans/p5_mac_shell_options.research.md)
**Audience:** Anyone reconsidering the desktop/mobile shell choice for the AgentsFramework frontend.

---

## Context

The frontend is a single **Next.js 15 / React 19** web app served by a BFF
(`next.config.ts` uses `output: "standalone"` — there is no static export; the BFF
middleware, API routes, and WorkOS AuthKit auth must be running). It must ship as
native-feeling **macOS** and **iOS** apps without forking the codebase.

The shells were chosen and scaffolded during P5/P6:

- **macOS** — Tauri 2 (`frontend/src-tauri/`), loading the live web origin in WKWebView.
- **iOS** — Capacitor 7 (`frontend/ios/`), loading the same origin in WKWebView via
  `server.url`.

Both shells load a running HTTP origin (Cloud Run BFF in prod, `localhost:3000` /
LAN dev server in dev) — neither bundles a static export.

This ADR records *why* that pairing was chosen over Electron and over true-native
frameworks (React Native / Flutter / SwiftUI), and what it commits us to, so the
decision is not re-litigated in a PR thread (per the frontend style guide §"Prescriptive
tone").

### The decisive insight

Both Tauri and Capacitor render the UI in the **OS WebView (WKWebView on Apple
platforms)**. So "native look and feel" comes ~95% from our own CSS / design system —
the redesign already in flight (`native_wrap_ui_redesign.plan.md`: Cursor warm-neutral
aesthetic, P4 mobile polish — safe areas, 44pt touch targets, system-font-first stack) —
**not** from the shell framework. The shell only contributes window chrome,
traffic-light placement, safe-area insets, keyboard behavior, and OS integration (deep
links, notifications). The framework comparison therefore only changes the answer if we
leave the single-web-codebase model for a true-native-widget path, which is a much larger
rewrite.

---

## Decision

**Ship the macOS app with Tauri 2 and the iOS app with Capacitor 7, both rendering the
single Next.js web app in the OS WebView.** Do not adopt Electron, React Native, Flutter,
or SwiftUI for these shells.

---

## Options considered & rejected

### Desktop — Tauri 2 vs Electron

| Dimension | Tauri 2 (chosen) | Electron (rejected) |
|---|---|---|
| Installer size | ~2–10 MB | 80–150+ MB (bundles Chromium) |
| Idle RAM | ~30–50 MB | ~150–300 MB |
| Startup | < 0.5 s | 1–2 s |
| Renderer | OS WebView (WKWebView on macOS) | Bundled Chromium |
| Rendering consistency | Varies per-OS (WebKit vs WebView2) | Identical everywhere |
| Mobile | Yes (Tauri 2) | No |
| Auto WebView security patches | Yes (rides OS Safari updates) | No (ship a new Chromium) |

Electron's only durable edges are **rendering consistency** (bundled Chromium → no
WebKit-only CSS bugs) and **packaging maturity**. Neither renders native widgets — both
are HTML/CSS — so neither is more "native" by default. Electron's consistency advantage
is purchasable with WKWebView testing; its size/startup cost is not recoverable.

### iOS — Capacitor 7 vs React Native vs Flutter vs SwiftUI

| | Capacitor 7 (chosen) | React Native | Flutter | SwiftUI |
|---|---|---|---|---|
| UI rendering | WebView (our web UI) | Real native widgets | Own Skia/Impeller engine | Real native widgets |
| Native by default | No — styled toward platform | Yes | No — "looks like Flutter" | Yes (Apple-only) |
| Code reuse w/ web app | ~100% (same Next.js) | Low (separate RN tree) | None (Dart rewrite) | None (Swift rewrite) |
| Perf ceiling | WebView ceiling (good on modern WebKit, 60fps for moderate UI) | Native | Highest/most consistent | Native |

**React Native is the only option that is native-by-default** (real UIKit-backed
widgets); SwiftUI is too but is Apple-only and abandons the web codebase entirely.
For a chat/agent surface (lists, composer, streaming text) the WebView ceiling is
adequate, and our P4 polish closes most of the perceived-native gap. The cost of RN /
Flutter / SwiftUI — losing the single web codebase — is not justified by that gap.

---

## Rationale (2026)

1. **The single Next.js codebase serving web + desktop + iOS from one origin is the
   highest-leverage property of the stack.** Electron keeps it but adds ~150 MB and worse
   startup for the one benefit (render consistency) we can get by testing in WKWebView.
   RN / Flutter / SwiftUI discard the single codebase for native widgets a chat surface
   does not need.
2. **The 2026 market is consolidating on exactly this model** — system WebView +
   lightweight backend (Tauri, Capacitor, Neutralino, Blazor Hybrid / WebView2).
   True-native frameworks (SwiftUI, Qt) remain the choice only for Apple-exclusive or
   performance-critical / embedded apps, not web-first products.
3. **Native feel = CSS, not shell.** The native-feel investment is the shell-agnostic
   redesign already underway (P0–P3 done, P4 partial), so the shell choice should
   optimize for size / startup / single-codebase, where Tauri + Capacitor win.

---

## What the agentic leaders actually ship (2026)

The "Tauri wins benchmarks" narrative is the indie/efficiency consensus; the
production-agentic consensus is more mixed, and worth recording so this ADR isn't read
as contrarian:

| Company / product | Desktop | Mobile |
|---|---|---|
| **Anthropic — Claude** | Electron | Native iOS + Android |
| **Cursor** | Electron (inherited — it's a VS Code fork, not an evaluated choice) | PWA (web app added to home screen; phone is a remote for cloud agents) |
| **OpenAI — ChatGPT** | Native Swift (macOS) — Windows shipped months later for lack of a shared codebase | Native |
| **Slack** | Electron | Fully native (Swift/Kotlin) — *evaluated and rejected* React Native + Flutter |

Two lessons, neither of which overturns the decision:

1. **The leaders pick Electron not because it is "more native" — it isn't — but because
   bundled-Chromium rendering consistency + a decade of shipping tooling beat binary size
   when you ship fast and broad.** This is a real signal, addressed in Consequences.
2. **Their choices cluster at the *extremes* of a "how primary is mobile" axis** — Cursor
   (companion → PWA, no native cost) vs Slack/Anthropic (primary daily surface → full
   native, 2× the work). Our Capacitor choice is the deliberate middle: mobile matters
   enough to need a real shell (push, deep-link auth, app-store presence a PWA can't give),
   but not enough to justify forking into a separate native codebase. The middle is only
   wrong if we are secretly at an extreme — see the mobile decision-trigger in
   Consequences.

---

## Weighted scoring (for our workload: single web origin, desktop + iOS, small team)

Criteria weighted by how much they matter *here*, not in the abstract. Scores 1–5.

| Criterion | Weight | Tauri+Cap | Cap→Electron | Electron+Cap | Swift+Cap |
|---|---|---|---|---|---|
| Single codebase preserved | 22% | 5 | 5 | 4 | 2 |
| Mobile (iOS) reach | 18% | 5 | 5 | 5 | 4 |
| Render consistency | 16% | 3 | 4 | 5 | 5 |
| Shipping tooling (update/sign/notarize) | 14% | 3 | 4 | 5 | 4 |
| Native look & feel | 12% | 4 | 3 | 3 | 5 |
| Size / perf / startup | 10% | 5 | 3 | 2 | 4 |
| Security / attack surface | 8% | 5 | 3 | 3 | 4 |
| **Weighted total /10** | | **7.85** | **7.05** | **6.95** | **5.55** |

Tauri + Capacitor wins on the heavily-weighted axes (codebase, mobile reach, size,
security). Electron's wins (consistency, tooling) are real but lower-weighted *for a
chat/agent workload*. The closest alternative is **Capacitor → Electron desktop** (one
toolchain for iOS + desktop, Electron's Chromium consistency under the hood) — relevant
only if the WebGPU trigger below fires.

### Performance & tooling, measured

- **Desktop (Tauri vs Electron):** installer 2–10 MB vs 80–200 MB; idle RAM 30–50 MB vs
  150–300 MB; startup < 0.5 s vs 1–2 s. Tauri wins every raw-performance category. Source:
  Nickel benchmark suite (Feb 2026), Open Web Foundation Desktop App Performance Tracker.
- **Mobile (Capacitor vs RN vs native):** native + RN sustain ~60fps on the UI thread;
  Capacitor's WebView is ~20–30 ms behind on **mid-range Android**, near-parity on
  high-end. For a chat surface (light DOM, streaming text, lists) the gap is not
  perceptible.
- **Tooling is the inverse of performance:** Electron's `electron-updater` (diff updates,
  staged rollouts, notarization "just works") and RN's Meta-backed plugin ecosystem are
  deeper than Tauri's (full-binary updater, younger release-engineering) and Capacitor's
  (adequate official plugins, smaller community — but runs Cordova plugins). Our actual
  plugin needs (push, keyboard, safe-area, deep-link auth) are covered by Capacitor's
  *official* plugins, and the P5 Tauri auth path is already proven.

---

## Heavy / specialized integrations — where the choice can flip

For most integrations the WebView is engine-agnostic, but two categories matter:

| Integration | Tauri 2 | Electron | Winner |
|---|---|---|---|
| Rich charts (Canvas/**WebGL** — ECharts, Plotly, LightningChart) | Excellent (WebGL in every WebView) | Excellent | tie (Tauri lighter) |
| **WebGPU** charts / GPU compute | ⚠️ experimental/unsafe flag; Linux "soon-ish", macOS uncertain | ✅ guaranteed via bundled Chromium | **Electron** |
| LibreOffice / OnlyOffice / office automation | ✅ Rust **sidecar** manages the external binary cleanly; OnlyOffice Document Server embeds via iframe | works via Node `child_process` | **Tauri** (slight) |
| Gaming — WebGL | good, but **per-OS WebView testing required** | ✅ consistent Chromium | **Electron** |
| Gaming — WebGPU / heavy GPU | ⚠️ not reliable yet | ✅ mature (why Figma ships on Electron) | **Electron** |
| Native hardware / external binaries | ✅ sidecar lifecycle model | manual spawn/monitor | **Tauri** |

**The one genuine Tauri *capability* gap (not a maturity gap) is WebGPU / GPU-compute.**
Standard WebGL charting and office automation favour or tie with Tauri (the sidecar model
is actually a *better* fit for driving LibreOffice/OnlyOffice). So the entire desktop
decision reduces to a single roadmap question, captured as a decision-trigger below.

---

## Switching cost (measured against the real shell)

The Tauri shell is small and well-factored — `frontend/src-tauri/` is **~580 LOC of
Rust** (`lib.rs` 296, `auth.rs` 278, `main.rs` 6) plus config + reusable icons. The web
app is untouched by the shell, and the PKCE auth logic is isolated pure logic.

| Switch | Cost | Why |
|---|---|---|
| Stay on Tauri | **0** | Already built and working (P5 done) |
| **Tauri → Electron** (desktop) | **~1–2 weeks** | Rewrite 580 LOC Rust → JS (nav-intercept → `will-navigate` + `setAsDefaultProtocolClient` + `open-url`; CSP-proof inject → `executeJavaScript`; UA marker → `setUserAgent`). Icons + web app + PKCE *algorithm* port directly. ~1 week code, ~1 week re-validating the WorkOS/CSP/deep-link auth path. |
| Add Electron *under* Capacitor (desktop) | ~3–5 days | Capacitor's Electron target; but still re-does the Tauri auth in Capacitor's model |
| **Capacitor → React Native** (mobile) | **~2–4 months** | Not a shell swap — a full rewrite of the Next.js UI as native RN components; discards the single codebase |

**Key finding: we are not deeply locked into Tauri.** Tauri → Electron is a ~2-week
sprint, not a quarter, *because* the shell is small and the web app is engine-agnostic.
The expensive, hard-to-reverse decision in this stack is **mobile** (Capacitor → RN is
months) — the desktop shell is the cheap one to change.

---

## Consequences

- **Commits us to the single web codebase** as the source of truth for all three targets.
- **Accepts WKWebView as the one shared risk.** Both shells use WebKit, so a WebKit-only
  CSS bug hits **desktop *and* iOS** simultaneously — this is Tauri/Capacitor's single
  genuine downside vs Electron's bundled Chromium. Mitigation: a standing **WKWebView
  fidelity gate** — render the redesigned surfaces in Safari Technology Preview / real
  WKWebView and diff against Chromium, focusing on container queries (P3), `:has()`,
  fonts, scrollbars, and form controls. (See `native_wrap_ui_redesign.plan.md` P3/P4.)
- Tauri (Rust) and Capacitor (native iOS) shells each carry a thin native layer
  (deep-link auth, keyboard/safe-area handling) that must be maintained per-platform.
- **Desktop shipping infrastructure is the concrete cost of the performance win.** Tauri's
  auto-update (full-binary, not diff), notarization, and crash-reporting need more
  first-principles work than Electron's battle-tested `electron-updater` would. This is a
  one-time setup cost, not a per-feature one — budget for it in the P5 release-engineering
  step.

### Decision-triggers — revisit this ADR if either fires

These keep the decision honest by naming, in advance, the conditions under which it
should flip:

1. **WebGPU / GPU-compute on desktop.** If the roadmap commits to a real gaming interface,
   WebGPU dashboards, or GPU-compute-class visualization, that is the one workload where
   Tauri has a current *capability* gap (not just maturity). The right response is **not**
   "Electron + Capacitor" but **Capacitor → Electron desktop** (one toolchain, Chromium's
   guaranteed GPU pipeline). The switch is a ~1–2 week sprint (see Switching cost) — so
   **do not pre-pay it now**; exercise it if and when WebGPU becomes real.
2. **Mobile becomes a premium primary surface.** If iOS shifts from a co-equal surface to
   a flagship experience competing with native apps on feel/performance, the WebView
   ceiling will frustrate, and the leaders' pattern (Slack/Anthropic → full native) starts
   to apply. This is the expensive switch (~2–4 months), so it should be a deliberate,
   ADR-amending decision — not a drift.

Until either fires, **stay on Tauri + Capacitor**: it is built, costs $0, wins the
weighted score for a chat/agent + WebGL-charts + office-automation workload, and the one
plausible escape hatch (Electron for desktop) is cheap and well-understood.

---

## Supersedes / related

This ADR makes canonical the shell choice scaffolded in
[p5_tauri_macos_shell.plan.md](../plans/p5_tauri_macos_shell.plan.md) and
[p6_capacitor_ios_shell.plan.md](../plans/p6_capacitor_ios_shell.plan.md), and records
the rationale behind the options surveyed in
[p5_mac_shell_options.research.md](../plans/p5_mac_shell_options.research.md). The
broader UI direction lives in
[native_wrap_ui_redesign.plan.md](../plans/native_wrap_ui_redesign.plan.md).
