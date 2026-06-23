---
title: Native-wrap UI redesign (Tauri 2 macOS + Capacitor 7 iOS)
status: draft
created: 2026-06-22
owner: Rajnish Khatri
todos:
  - decide-tokens-source-of-truth
  - establish-token-pipeline
  - target-cursor-warm-neutral-aesthetic
  - build-primitive-layer
  - sync-library-to-claude-design
  - design-layouts-with-design-agent
  - redesign-chat-surface
  - responsive-variants
  - storybook-as-spec
  - wrap-shells
related:
  - repo-root-cleanup-layout
decisions:
  tooling: code-first (shadcn/ui + Tailwind v4 @theme + Storybook + v0 for variants)
  design-surface: Claude Design (claude.ai/design) via /design-sync — sync the real component library so the design agent composes layouts from our actual parts (replaces the earlier Figma plan, 2026-06-22)
  aesthetic: Cursor warm-neutral — warm off-white canvas, near-black text, ONE reserved accent, hairline borders, soft (radius-lg) chrome, sunken sidebar + soft selected row, pill composer (2026-06-22; this is the P1/P2 visual target)
  layout: one fluid responsive layout (viewport queries for structure, container queries for components)
  token-source-of-truth: git (DTCG JSON) is authoritative; design lives in code, synced to claude.ai/design
  wrap-target: Tauri 2 (macOS, notarized DMG + Sparkle), Capacitor 7 (iOS, TestFlight → App Store)
---

# Native-wrap UI redesign plan

Redesign the existing Next.js 15 / React 19 / Tailwind v4 / CopilotKit chat frontend so it
feels native when wrapped by **Tauri 2 (macOS)** and **Capacitor 7 (iOS)** — without a Swift
rewrite. Decided path: **Path A (wrap)**, **code-first design tooling**, **one fluid responsive
layout**. The goal is to keep the flat maintenance curve (one web codebase ships everywhere)
while raising the bar on look, feel, and native affordances.

## 0. Current-state inventory (ground truth, 2026-06-22)

The frontend is small and already has a usable token seed — this is an *evolution*, not a greenfield.

- **Composition root:** `app/page.tsx` (62 LOC) — trivial to re-lay-out.
- **Tokens today:** `app/globals.css` `@theme` block — colors (`--color-bg/fg/muted/accent/border/surface`),
  a 1.2 type scale with paired line-heights, Geist sans+mono, `--radius-sm/md`, dark mode via
  `[data-theme="dark"]`. **No `tailwind.config.*`** — confirmed Tailwind v4 CSS-first.
- **Component domains (40 .tsx, ~24k LOC incl. tests):**
  - chat core — `Composer`, `StreamingMarkdown`, `CodeBlock`, `RunControls`, `TaskList`, `ThemeToggle`
  - shell/nav — `ThreadSidebar`, `SidebarPanel`, `SidebarTabBar`, `TaskUnderstandingCard`
  - memory — `MemoryPanel`, `RecallIndicator`, `RecalledMemories`
  - generative/tools — `PyramidPanel`, `SandboxedCanvas`, `ToolCard`
  - primitives — **only** `ui/button.tsx` ← the gap to fill
- **BFF routes (unchanged by redesign):** `/api/run/stream`, `/api/run/cancel`,
  `/api/run/understanding/[threadId]`, `/api/threads*`, `/api/memory*`, `/api/auth/[...workos]`.
- **Test surface to preserve:** 44 e2e specs + component tests. Redesign must keep selectors/roles
  green or migrate them deliberately.

**Implication:** the expensive part of most redesigns (unwinding a mature design system) does not
apply. We are *establishing* a primitive layer for the first time over an existing token seed.

## 1. Tooling decision (updated 2026-06-22 — Figma dropped for Claude Design)

**Design lives in code; the design surface is Claude Design (claude.ai/design) via `/design-sync`.**
Figma is dropped — for a no-designer TS team it costs a paid Dev seat and a lossy code→Figma import.
Instead, we build the component library in code (the same shadcn primitives we ship), **sync it to a
Claude Design project**, and then the **design agent composes layouts out of our actual components** —
on-brand, mapping 1:1 to shippable code, no per-seat cost.

| Concern | Choice | Why |
|---|---|---|
| Design surface | **Claude Design** (claude.ai/design) | prompt the design agent; it builds with OUR real components |
| Design ↔ code bridge | **`/design-sync`** (`DesignSync` tool) | converts the built library → Claude Design format, uploads, keeps in sync |
| Component substrate | **shadcn/ui** over Tailwind v4 | what v0/Claude/design-sync all consume; you own the code |
| Token contract | **DTCG JSON → Style Dictionary → Tailwind `@theme` CSS** | one source of truth, feeds web + both shells; styles ride along in the sync |
| Living spec | **Storybook** (already partially present — `*.stories.tsx` exist) | every chat state is a story; also the preferred design-sync "shape" |
| New variants | **v0 (Vercel)** | emits React+Tailwind+shadcn that merges with cleanup |

Storybook already has a foothold: `PyramidPanel.stories.tsx`, `SandboxedCanvas.stories.tsx`,
`ToolCard.stories.tsx`. Extend that — design-sync's high-fidelity path prefers a Storybook "shape"
(previews come from real stories), so growing Storybook coverage doubles as design-sync readiness.

> **Why this beats Figma here:** no code→Figma import (lossy, one-way), no Dev-seat cost, no token
> mirror to keep honest. The library you build *is* the design system the agent designs with, and
> every layout it produces is already your real components. The cost is that design-sync imports what
> you've **already built** — so it runs *after* the primitive layer exists (see §2.5 + P-sync).

## 2. Token pipeline — the cross-platform contract

One token file is the single source of truth for color/spacing/type across web + Tauri + Capacitor,
because all three render the same web CSS.

```
design/tokens/*.tokens.json   (DTCG, $-prefixed, git-tracked — the authority)
        │  style-dictionary build
        ▼
frontend/app/globals.css  @theme { … }   (generated block, do not hand-edit)
        │  Tailwind v4 emits utilities + CSS vars
        ▼
web  ──► Tauri (WKWebView)  ──► Capacitor (WKWebView)   (same CSS everywhere)
```

### 2a. Migrate the existing seed into DTCG
Lift the current `@theme` values into `design/tokens/`:
- `color.tokens.json` — promote the flat `--color-*` set to semantic tokens
  (`color.bg`, `color.fg`, `color.accent`, `color.border`, `color.surface`) + a dark theme set.
  Keep the `color-mix(oklab)` derivations or precompute them in Style Dictionary.
- `type.tokens.json` — the 1.2 scale + paired line-heights (already well-specified — preserve verbatim).
- `space.tokens.json`, `radius.tokens.json` — extract `--radius-sm/md`, add a spacing scale.
- `font.tokens.json` — Geist sans/mono stacks, **add the native system fallback** so wrapped
  builds inherit the OS font when Geist isn't preferred (see §4).

### 2b. Style Dictionary config
- Output a single `@theme { … }` CSS block written into (or `@import`-ed by) `globals.css`.
- Mark the generated region with comment guards so it's never hand-edited.
- `pnpm tokens:build` script; wire into the `dev`/`build` pipeline so drift can't ship.

> **Rule:** after §2 lands, nobody edits color/type/spacing in component files or `globals.css`
> directly — they edit DTCG JSON and rebuild. This is what keeps web + both shells from diverging.

## 2.5. Claude Design layout phase (via `/design-sync`)

Replaces the earlier Figma plan. The design surface is **Claude Design** (claude.ai/design): we sync
our **real, built component library** into a Claude Design project with `/design-sync`, then prompt
the **design agent**, which composes layouts out of our actual components — every design it produces
is on-brand and maps 1:1 to shippable code.

### The ordering constraint (why this runs AFTER P1, not before P3)
`/design-sync` imports what we've **already built** — it converts the repo's compiled component
library to Claude Design's format and uploads it. Today the library is ~40 feature components + ONE
primitive (`ui/button.tsx`); syncing now would import essentially a button. So this phase runs
**after §3 / P1 (the shadcn primitive layer exists)** and ideally after enough Storybook coverage
that design-sync's high-fidelity path has real stories to verify against. Tokens (§2) come first too,
since `styles.css`/tokens ride along in the sync and define the look every design inherits.

### What `/design-sync` does (mechanics)
- Detects the source **shape**: a **Storybook** repo (preferred — previews come from real stories,
  verified against the storybook render) or a **package** repo (rich previews authored from usage
  examples, graded on an absolute rubric). We have `.storybook` foothold already → Storybook shape.
- Builds a deterministic bundle from the repo's own `dist/` (`_ds_bundle.js` + `styles.css` +
  per-component `.html`/`.jsx`/`.d.ts`/`.prompt.md`), **visually verifies every component preview**
  (a first-time high-fidelity sync can take **hours** and significant tokens), and uploads to a
  **new Claude Design project** created for it.
- Writes `.design-sync/config.json` (pin + shape) and `.design-sync/conventions.md` (the header the
  design agent reads — our wrapping/provider/token vocabulary). Re-syncs are incremental and mostly
  deterministic via the `_ds_sync.json` anchor.

### Prereqs before running it
1. A built component library (`dist/`) — the shadcn primitive set from §3 + the redesigned chat
   components, compiled.
2. Storybook stories covering the §6 states (also the design-sync "shape" + verification source).
3. Tokens (§2) wired into `styles.css` so the synced look matches production.
4. A claude.ai login with design-system access (the tool prompts for `/design-login` if missing).

### The loop (after the sync lands)
- Prompt the **design agent** in the Claude Design project to compose the redesigned screens
  (desktop three-pane, phone single-column + drawer/sheet, the §6 streaming states) **from our
  synced components**, toward the **§2.6 Cursor warm-neutral aesthetic** (its `conventions.md` header
  should state the look so every composition stays on-brand).
- Because it builds with our real parts, its output maps to shippable code — pull it back as the
  actual chat-surface implementation (P2), then keep Storybook stories as the living spec (§1).
- **Re-sync** whenever the library changes (new primitive, restyled component) so the design agent
  always designs with the current parts — incremental, cheap after the first run.

> **Why this beats the dropped Figma plan:** no lossy code→Figma import, no paid Dev seat, no token
> mirror to keep honest, and the design agent designs with our *actual* components instead of Figma
> stand-ins. The one cost is sequencing — it needs the library to exist first (P1), so it can't be
> the *front* of the redesign the way the Figma canvas was framed.

## 2.6. Design direction — Cursor warm-neutral aesthetic (the P1/P2 visual target)

The redesign targets the **Cursor (Composer) desktop look**: a warm, soft, low-chrome aesthetic that
reads as a native Mac app rather than a website. This is the visual brief the P1 primitives and P2
chat surface implement, and the look the design agent (§2.5) should compose toward.

**The look in one line:** warm off-white canvas · near-black text · ONE reserved accent · hairline
borders · soft (`radius-lg`) corners · a recessed sidebar with a soft selected-row fill · a
pill-shaped composer.

### Already landed (token layer, P0 follow-up — 2026-06-22)
Four token deltas shipped through the §2 pipeline; build green, only `--color-muted` changed value:
- `--radius-lg: 0.75rem` — the soft pill composer + rounded message cards.
- `--color-surface-sunken` (recessed sidebar/rail, one step darker than `--color-surface`).
- `--color-selected` (translucent `fg/6%` active-row fill).
- `muted` warmed `#6b7280 → #7d7a75` (light) / `#9ca3af → #a3a09a` (dark) — neutrals in the warm
  family, not cool blue-gray.

### Component-shape rules (P1/P2 — how primitives consume the tokens)
These are *shape* decisions, not tokens — they belong in the shadcn primitive + chat-surface work:
- **Composer = pill.** `input`/`textarea` styled at `radius-lg`, inline leading `+` affordance,
  circular send/mic button on the trailing edge (solid `fg` circle, see the §6 streaming states).
- **Sidebar = recessed.** Left rail on `--color-surface-sunken`; the active thread row uses
  `--color-selected` (soft fill, not a hard highlight); hover one notch lighter.
- **Accent is rationed.** Indigo (`--color-accent`) on exactly ONE primary action per surface
  (e.g. the equivalent of Cursor's "Update"/primary button) — everything else is neutral.
- **Borders are hairlines.** 1px at `--color-border` / `--color-border-light`; prefer surface
  contrast over heavy strokes for separation.
- **Inline code chips.** `--color-surface` fill + mono + `radius-sm` (already the StreamingMarkdown
  shape — keep it).
- **Cards/panels at `radius-md`/`radius-lg`** with hairline borders, on `--color-surface`.

> **Where this binds:** P1 primitives (`button`, `input`/`textarea`, `card`, `tabs`) bake in the
> radius + accent-rationing rules; P2 composes the pill composer + recessed sidebar + soft selection.
> The aesthetic rides entirely on §2 tokens — no hardcoded colors — so the wraps (Tauri/Capacitor)
> inherit it for free.

## 3. Primitive layer (the gap)

Today there is exactly one primitive (`ui/button.tsx`). Establish the shadcn primitive set the
redesigned features will compose from. Add only what the chat app actually needs — do not import
the whole shadcn catalog.

Priority primitives: `button` (reconcile existing), `input`/`textarea` (Composer), `dialog`/`sheet`
(mobile drawers/panels), `dropdown-menu` (message actions), `tooltip` (desktop-only, hover-gated),
`scroll-area`, `tabs` (SidebarTabBar), `card`, `badge`, `separator`, `skeleton` (streaming states),
`toast` (errors/cancel). All consume tokens from §2 — no hardcoded colors — and bake in the §2.6
Cursor warm-neutral shape rules (`radius-lg` chrome, rationed accent, hairline borders).

## 4. Native-feel layer (web → Tauri + Capacitor)

CSS/HTML changes that make one web UI feel native on a Mac window AND an iPhone. These are additive
to the redesign, not separate.

### 4a. iOS app-feel
- **Safe areas:** pad shell with `env(safe-area-inset-*)`; adopt `@capacitor-community/safe-area@^7`
  (Capacitor WebView has a known keyboard-resize bug) for notch / Dynamic Island / home-indicator
  + keyboard handling.
- **Kill the "website" feel:** `-webkit-touch-callout: none`, `-webkit-user-select: none`
  (but **keep selection on message text** — users copy answers), `overscroll-behavior: contain`,
  momentum scroll on scroll containers.
- **Input bar pinned above keyboard;** scroll-to-bottom button when scrolled up; **long-press**
  for message actions (replaces hover toolbars on touch).

### 4b. macOS app-feel (Tauri 2)
- Custom titlebar: `titleBarStyle: "Overlay"`, `hiddenTitle: true`, `trafficLightPosition`.
- Draggable regions via **`data-tauri-drag-region`** (Tauri attr — NOT `-webkit-app-region`);
  must be set per child element.
- Consider `tauri-plugin-decorum` / mac-rounded-corners for inset/corner polish.
- Respect `prefers-color-scheme` → drive `[data-theme]`.

### 4c. Cross-cutting
- **Touch targets ≥ 44×44pt** (HIG) on interactive elements.
- **Gate hover styles behind `@media (hover: hover)`** so they don't stick on touch.
- **System font option:** add `"SF Pro", system-ui, -apple-system` to the font stack so the wrapped
  UI can inherit the OS font (token in §2a; decide Geist-first vs system-first per platform).

## 5. Responsive strategy (locked: one fluid layout)

- **Viewport media queries → page structure.** Desktop = three-pane (left thread rail · chat ·
  right tabbed panel). Phone = single column; left rail → `sheet` drawer, right panel → bottom `sheet`.
- **Tailwind v4 container queries (`@container`) → component internals.** Composer, ToolCard,
  TaskUnderstandingCard adapt to *their slot*, not the viewport — so they look right in a wide Mac
  window and a narrow phone alike.
- Capture compact states with `@max-*:` variants. No platform-forked layouts (that re-steepens the
  maintenance curve Path A buys down).

## 6. Streaming-chat UX bar (2026 patterns)

Redesign the chat surface to current agentic-UI expectations:
- Token-by-token streaming with a prominent **stop** (wire to `/api/run/cancel`) + **regenerate**.
- Per-message actions (copy / edit / branch) — hover toolbar on desktop, long-press on mobile.
- **Collapsible tool-call + reasoning ("thinking") disclosure** — you already surface
  `TaskUnderstandingCard`, `ToolCard`, `TaskList`; unify them into a consistent disclosure pattern.
- Buffer incomplete markdown; defer code-fence rendering until the closing fence (guard
  `StreamingMarkdown`/`CodeBlock`).
- **Accessibility:** wrap streaming output in `aria-live="polite"` `aria-atomic="false"`
  `aria-relevant="additions"`, debounce announcements during fast streams; honor
  `prefers-reduced-motion` for caret/typing animation.

## 7. Phased execution

| Phase | Deliverable | Rough size | Gate |
|---|---|---|---|
| **P0** | DTCG tokens migrated from current `@theme`; Style Dictionary build; generated `globals.css` block | 2–3 d | `pnpm tokens:build` green; visual diff = no regression |
| **P1** | shadcn primitive layer (§3) consuming tokens + §2.6 Cursor warm-neutral shape rules; reconcile existing `button` | 3–4 d | primitives in Storybook, on-aesthetic |
| **PS1** | design-sync readiness — Storybook stories for primitives + §6 chat states; `dist/` build of the library | 2–4 d | `.storybook` covers the synced surface; library builds |
| **PS2** | `/design-sync` first run (§2.5) — create Claude Design project, sync the library, author `conventions.md` | hours–1 d (sync may run hours) | components verified + visible in the Claude Design project |
| **PS3** | Design layouts with the design agent (§2.5 loop) — compose desktop/phone screens + §6 states from synced components | days | screens designed; pulled back as implementable code |
| **P2** | Implement redesigned chat surface (§6) from the design-agent output — pill composer, recessed sidebar, soft selection (§2.6) | 1–1.5 wk | all chat states are stories; e2e selectors green; matches the §2.6 aesthetic |
| **P3** | Responsive variants (§5) — drawer/sheet collapse, container queries | 4–5 d | desktop + phone widths verified in Storybook + browser |
| **P4** | Native-feel layer (§4) — safe-area, hover-gating, 44pt, system font option | 3–4 d | renders correctly in plain browser (pre-wrap) |
| **P5** | Tauri 2 macOS shell — custom titlebar, drag regions, notarized DMG + Sparkle appcast | 1 wk | DMG installs; WorkOS auth callback works in WKWebView |
| **P6** | Capacitor 7 iOS shell — safe-area plugin, keyboard, TestFlight build | 1 wk | TestFlight build; SSE stream + auth work on device |

**Ordering:** P0 (tokens) → P1 (primitives) gate **PS1→PS2→PS3** — design-sync imports a *built*
library, so the primitives must exist and be storybook-covered before the first sync. PS3 (design
agent composes layouts) feeds P2 (implement). Re-run design-sync (incremental) whenever the library
changes so the agent always designs with current parts. P0–P4 + PS* are pure web work (no native
toolchain) and ship to the existing Cloud Run web app along the way — the redesign is live on web
before either shell exists. P5/P6 are the wrap.

> **design-sync is optional/additive.** Dropping PS1–PS3 reverts to the pure code-first path
> (P0→P1→P2 with v0 for variants). The token pipeline (§2) and everything downstream are unchanged —
> the design agent is a layout accelerator, not load-bearing. Its one hard requirement is sequencing:
> it needs the library to exist first (P1).

## 8. Deployment strategy

- **Web (unchanged):** redesign ships to Cloud Run on the existing cadence. Apps are thin clients
  pointed at the same `/api/run/stream`.
- **macOS:** notarized DMG + **Sparkle** auto-update (skip Mac App Store v1 — sandbox fights
  backend/localhost needs). CI: `tauri build` → `codesign` → `notarytool` → publish DMG + appcast.
  Shell re-ships only when *native* code changes (rare); web layer updates via the loaded URL/bundle.
- **iOS:** Capacitor → Xcode → **TestFlight → App Store** (Fastlane or Xcode Cloud). Requires:
  server-side moderation story, working delete-account flow (Guideline 5.1.1(v)), age rating ≥ 17,
  IAP only if charging in-app.

## 9. Risks / watch-items

- **e2e selector churn (44 specs):** redesign WILL move DOM. Decide per-phase: keep `data-testid`
  stable, or migrate specs deliberately. Don't let the suite go red silently (see memory:
  sidebar `guard` swallowing errors historically).
- **CopilotKit/AG-UI coupling:** the chat surface is CopilotKit-driven. Redesign the *presentation*,
  not the runtime wiring — verify streaming still flows after each chat-component change.
- **Token-drift regressions:** once §2 lands, any hand-edited color in a component is a bug.
  Add a lint/CI check that the generated `@theme` region matches the DTCG build.
- **Auth in WKWebView:** WorkOS AuthKit callback must survive the Tauri/Capacitor webview redirect.
  De-risk early in P5/P6 (this is the #1 thing that breaks wrapped auth).
- **design-sync needs a real library first:** it imports the *built* component library. Running it
  before P1 syncs ~one button. Gate PS2 on P1 + Storybook coverage (PS1) — don't run the first
  (hours-long, token-heavy) sync against a primitive-less repo.
- **First-sync cost:** a first-time high-fidelity sync visually verifies every component and can take
  **hours + significant tokens**. Budget it; re-syncs are incremental/cheap via the `_ds_sync.json`
  anchor. Keep the synced surface scoped (don't import the whole shadcn catalog — §3).
- **Design-agent output still needs the §9 guardrails:** screens it composes must keep e2e selectors
  green and not break the CopilotKit/AG-UI runtime wiring (presentation only). Treat its output like
  any generated code — review against the same gates.
- **Stale synced library:** if the library changes and you don't re-sync, the design agent designs
  with outdated parts. Re-run design-sync after any primitive/restyle change (incremental).
- **Login dependency:** `/design-sync` needs a claude.ai login with design-system access; it prompts
  for `/design-login` if missing. Confirm access before PS2.

## 10. Open questions

1. **Geist vs system font per platform** — keep Geist everywhere (brand consistency) or switch to
   SF Pro/system-ui inside the wraps (maximal native feel)? Affects §2a/§4c.
2. **e2e migration policy** — stabilize `data-testid` up front, or rewrite specs against the new DOM
   per phase? Sizes the test work in P2/P3.
3. **iOS scope** — full phone layout now, or iPad-acceptable first (your current UI nearly fits a
   tablet)? Could collapse P3's mobile work.
4. **macOS distribution** — confirm DMG+Sparkle over Mac App Store for v1 (recommended), and whether
   you need an Apple Developer Program enrollment now (required for notarization + TestFlight).
5. **Storybook coverage scope (PS1)** — how many of the §6 chat states get stories before the first
   sync? More coverage = better design-sync verification, but more PS1 work.
6. **When to first run `/design-sync`** — right after P1 (primitives only), or after P2's redesigned
   chat components also exist (richer library to design with)? Trades earlier design-agent access vs
   a fuller first sync.

## 11. Design-sync cost & dependencies

No per-seat design-tool cost (this is why Figma was dropped). Dependencies:

- **claude.ai login with design-system access** — `/design-sync` prompts for `/design-login` if
  missing. This is the only access gate.
- **First-sync compute** — a first-time high-fidelity sync visually verifies every component;
  budget **hours of wall-clock + significant tokens** once (PS2). Re-syncs are incremental and cheap
  via the `_ds_sync.json` anchor.
- **A buildable library** — design-sync ships the repo's compiled `dist/`, so the component kit must
  build (PS1). Storybook "shape" is preferred (previews from real stories).

Other tooling unchanged from §1: **shadcn / Tailwind v4 / Style Dictionary / Storybook / v0** —
all free/OSS. The dropped Figma path would have cost a **$12–35/Dev-seat/mo** seat plus a lossy
import; design-sync replaces it at zero seat cost, with the tradeoff that it runs *after* P1.
