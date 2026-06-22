---
title: Native-wrap UI redesign (Tauri 2 macOS + Capacitor 7 iOS)
status: draft
created: 2026-06-22
owner: Rajnish Khatri
todos:
  - decide-tokens-source-of-truth
  - establish-token-pipeline
  - export-current-ui-to-figma
  - redesign-layout-in-figma
  - figma-to-code-handoff
  - build-primitive-layer
  - redesign-chat-surface
  - responsive-variants
  - storybook-as-spec
  - wrap-shells
related:
  - repo-root-cleanup-layout
decisions:
  tooling: code-first IMPLEMENTATION (shadcn/ui + Tailwind v4 @theme + Storybook + v0 for variants)
  design-surface: Figma for LAYOUT redesign — capture current UI → redesign in Figma → hand off to coding agents via Dev Mode MCP (added 2026-06-22)
  layout: one fluid responsive layout (viewport queries for structure, container queries for components)
  token-source-of-truth: git (DTCG JSON) is authoritative; Figma Variables mirror via Tokens Studio (one-way code→Figma by default)
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

## 1. Tooling decision (updated 2026-06-22)

Split the surfaces: **Figma is the layout-design surface; code-first is the implementation substrate.**
Figma earns its keep specifically for a *layout* redesign (cheap exploration canvas + a token bridge
that keeps design and code honest). It is ceremony for component-level polish — for those, stay
code-first.

| Concern | Choice | Why |
|---|---|---|
| Layout design surface | **Figma** (Dev Mode + Variables) | low-stakes canvas to explore layouts without writing/reverting React; spec source for the agent handoff |
| Component substrate | **shadcn/ui** over Tailwind v4 | what v0/Cursor/Claude all assume; you own the code |
| Design→code handoff | **Figma Dev Mode MCP server** → Claude Code/Cursor | agent reads frame + Variables, writes shadcn + tokens |
| Component reuse in handoff | **Code Connect** (Org/Enterprise) *or* curated shadcn list in prompt (Pro) | makes the agent reuse `Button.tsx`, not reinvent `<div>` |
| Token contract | **DTCG JSON → Style Dictionary → Tailwind `@theme` CSS** | one source of truth, feeds web + both shells + Figma Variables |
| Living spec | **Storybook** (already partially present — `*.stories.tsx` exist) | every chat state is a story; complements Figma frames |
| New variants | **v0 (Vercel)** | emits React+Tailwind+shadcn that merges with cleanup |
| Visual-canvas alt | **Penpot** if you reject Figma's seat cost | open token export, no per-seat tax (see §11 cost table) |

Storybook already has a foothold: `PyramidPanel.stories.tsx`, `SandboxedCanvas.stories.tsx`,
`ToolCard.stories.tsx`. Extend that, don't bootstrap from zero.

> **Division of labor:** Figma owns the *layout/composition* (where panels live, responsive
> behavior, visual hierarchy). Code owns the *component internals + tokens*. Don't try to model every
> shadcn prop in Figma — model the screens, hand off, let the agent fill components from §3 tokens.

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

## 2.5. Figma layout-redesign phase

The added phase. **Tokens (§2) come first** — Figma Variables must mirror the real token set from day
one, or the agent handoff produces arbitrary values (`leading-[22.126px]`) that poison the scale.

### The honest constraint: code → Figma is lossy and one-way
Importing the live React/Tailwind UI into Figma captures **only what is visible** (a DOM/CSS walk).
It strips React state, prop structure, component identity, variants, and hover/interaction states,
and it resolves Tailwind utilities to **pixel values, not your `text-sm`/spacing scale**. Round-trip
(code→Figma→code) compounds loss at every hop — **do not treat it as a production loop.** Use
code→Figma only as a **visual starting canvas**; the value is the Figma→code handoff in §2.5c.

### 2.5a. Capture current UI into Figma (½–1 day)
- Import **3–5 core screens only** (chat surface desktop, chat surface phone-width, thread sidebar,
  right tabbed panel, an empty/streaming state) from `localhost`/staging via **html.to.design**
  (paste-URL or browser-extension → ⌘V into canvas; ~12 free imports/mo, Auto Layout still beta).
  - Alternative: Figma's own **`generate_figma_design`** (Claude Code → Figma, captures rendered
    screens as editable frames, preserves multi-screen flows).
- **Do NOT import the whole app.** Import = pixel canvas, not structure.
- Then **rebuild the components you'll actually iterate on natively in Figma** from those frames +
  the §2 tokens, as proper Figma components/variants. The import gives you the picture; the native
  rebuild gives you clean, variant-aware components worth handing back to an agent.

### 2.5b. Establish Figma Variables aligned to the §2 tokens (1–2 days)
- Stand up **Tokens Studio** in Figma; sync the existing DTCG tokens **code → Figma** so Figma
  Variables match production from day one.
- **Source of truth = git** (DTCG JSON). Figma Variables are a **read-only mirror**; Tokens Studio's
  GitHub sync provider commits to a branch, merge conflicts resolve in git, not Figma. Pick one
  authoring surface per token tier — true bidirectional editing is where teams get burned.

### 2.5c. Redesign the layout in Figma (the actual value — days→weeks)
- Do layout/composition exploration here: where panels live, three-pane→single-column collapse,
  visual hierarchy, the streaming-chat states from §6. This is the cheap, low-stakes surface a
  no-designer dev team benefits from — try layouts without writing/reverting React.
- Bind every component to the §2.5b Variables so designs stay token-true.
- Produce **separate desktop and phone-width frames** (the MCP can't infer responsive behavior —
  it needs both; see §5).

### 2.5d. Hand off Figma → code via Dev Mode MCP (per screen)
- Run the **Figma Dev Mode MCP server** (local, in the Figma **desktop app**, Dev Mode toggle, at
  `http://127.0.0.1:3845/mcp`). Register with Claude Code:
  `claude mcp add --transport http figma-desktop http://127.0.0.1:3845/mcp`.
- The server exposes frames/layout, **Variables & styles**, screenshots, component metadata, and
  Code Connect mappings (~14 tools). **Requires a paid Dev/Full seat.** A remote server exists on all
  plans but is rate-limited.
- **Component reuse:** if on **Org/Enterprise**, set up **Code Connect** to map Figma components →
  the real `components/ui/*` shadcn files so the agent imports `Button.tsx` (correct props) instead
  of generating fresh divs. On **Professional** (no Code Connect), instead feed Claude Code a
  **curated list of existing shadcn components + the §2 token names** in the prompt, or use
  **Builder.io Visual Copilot** for component-mapped output.

### 2.5e. Implement against shadcn + tokens (the agent loop)
- Loop: "Read this Figma frame via MCP, implement it with our shadcn primitives (§3) and `@theme`
  tokens (§2)." Realistic yield ~75–85% on simple layouts, lower on complex/responsive.
- **Budget cleanup** for the three things MCP can't see: responsive breakpoints (feed both frame
  URLs), hover/interaction states (annotate in the prompt), and raster assets (export manually).
- Land output as shadcn components + Storybook stories (§3, §1) — Figma frame and Storybook story
  are the two halves of the spec.

> **Where Figma pays off vs ceremony:** for *layout* redesign (this phase) it earns its keep. For
> later component-level tweaks, skip Figma and stay code-first — editing JSX is faster than syncing
> a frame. Don't model every shadcn prop in Figma.

## 3. Primitive layer (the gap)

Today there is exactly one primitive (`ui/button.tsx`). Establish the shadcn primitive set the
redesigned features will compose from. Add only what the chat app actually needs — do not import
the whole shadcn catalog.

Priority primitives: `button` (reconcile existing), `input`/`textarea` (Composer), `dialog`/`sheet`
(mobile drawers/panels), `dropdown-menu` (message actions), `tooltip` (desktop-only, hover-gated),
`scroll-area`, `tabs` (SidebarTabBar), `card`, `badge`, `separator`, `skeleton` (streaming states),
`toast` (errors/cancel). All consume tokens from §2 — no hardcoded colors.

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
| **PF0** | Figma setup (§2.5a/b) — capture 3–5 core screens via html.to.design; Tokens Studio mirror of §2 tokens (git→Figma) | 2–3 d | Figma Variables match DTCG build; core screens on canvas |
| **PF1** | Layout redesign in Figma (§2.5c) — desktop + phone frames, token-bound, streaming states | days→1–2 wk | desktop + phone frames per screen; stakeholder review |
| **PF2** | Figma→code handoff wiring (§2.5d) — Dev Mode MCP registered with Claude Code; Code Connect (Org) or curated-component prompt (Pro) | 1–2 d | agent reads a frame + Variables and emits shadcn against §2 tokens |
| **P1** | shadcn primitive layer (§3) consuming tokens; reconcile existing `button` | 3–4 d | primitives in Storybook |
| **P2** | Implement redesigned chat surface (§6) from Figma frames via handoff (§2.5e) | 1–1.5 wk | all chat states are stories; e2e selectors green |
| **P3** | Responsive variants (§5) — drawer/sheet collapse, container queries | 4–5 d | desktop + phone widths verified in Storybook + browser |
| **P4** | Native-feel layer (§4) — safe-area, hover-gating, 44pt, system font option | 3–4 d | renders correctly in plain browser (pre-wrap) |
| **P5** | Tauri 2 macOS shell — custom titlebar, drag regions, notarized DMG + Sparkle appcast | 1 wk | DMG installs; WorkOS auth callback works in WKWebView |
| **P6** | Capacitor 7 iOS shell — safe-area plugin, keyboard, TestFlight build | 1 wk | TestFlight build; SSE stream + auth work on device |

**Ordering:** P0 (tokens) gates PF0 — Figma Variables must mirror real tokens before any handoff.
PF0→PF1→PF2 run after P0; P1 can start in parallel with PF1. P2 *consumes* the Figma frames, so it
follows PF2. P0–P4 + PF* are pure web work (no native toolchain) and ship to the existing Cloud Run
web app along the way — the redesign is live on web before either shell exists. P5/P6 are the wrap.

> **If you skip Figma later:** PF0–PF2 are optional. Dropping them reverts to the original code-first
> path (P0→P1→P2 with v0 for variants). The token pipeline (§2) and everything downstream are
> unchanged — Figma is additive, not load-bearing.

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
- **Figma import poisons the token scale:** code→Figma resolves Tailwind utilities to raw pixels
  (`leading-[22.126px]`). Mitigate by doing §2 (tokens) BEFORE PF0 and binding Figma components to
  Variables — never let imported pixel values become the spec.
- **Agent reinvents components without Code Connect:** on Professional (no Code Connect), the MCP
  handoff generates fresh divs instead of reusing `components/ui/*`. Mitigate with a curated
  component+token prompt or Builder.io Visual Copilot — or budget the Org plan.
- **MCP blind spots:** the Dev Mode MCP cannot see responsive breakpoints, hover/interaction states,
  or raster assets. Always feed both desktop+phone frames, annotate states in the prompt, export
  assets manually. Budget per-screen cleanup (§2.5e).
- **Round-trip temptation:** code→Figma→code is lossy at every hop. Keep it one-way per phase
  (capture once → redesign → hand off); do not bounce screens back and forth.
- **Figma desktop-app dependency:** the local MCP only responds while the Figma desktop app is open
  with the server toggled on (beta). Plan handoff sessions accordingly.

## 10. Open questions

1. **Geist vs system font per platform** — keep Geist everywhere (brand consistency) or switch to
   SF Pro/system-ui inside the wraps (maximal native feel)? Affects §2a/§4c.
2. **e2e migration policy** — stabilize `data-testid` up front, or rewrite specs against the new DOM
   per phase? Sizes the test work in P2/P3.
3. **iOS scope** — full phone layout now, or iPad-acceptable first (your current UI nearly fits a
   tablet)? Could collapse P3's mobile work.
4. **Penpot later?** If a designer is likely within ~6 months, stand up Penpot in P0 so token
   authorship has a GUI from the start.
5. **macOS distribution** — confirm DMG+Sparkle over Mac App Store for v1 (recommended), and whether
   you need an Apple Developer Program enrollment now (required for notarization + TestFlight).
6. **Figma plan tier** — buy **Organization** (~$25/Dev seat/mo) to get **Code Connect** for clean
   shadcn reuse, or stay on **Professional** (~$12/Dev seat/mo) and use a curated-component prompt /
   Builder.io for mapping? Code Connect is Org/Enterprise-only.
7. **Is this a genuine layout redesign** (Figma pays off) or component polish (stay code-first)?
   Be honest — if it's polish, PF0–PF2 are ceremony.
8. **Who runs the Figma desktop app + local MCP** during agent handoff sessions, and is anyone
   comfortable enough in Figma to do the native component rebuild in §2.5a?

## 11. Figma cost & licensing (2026)

Per editor/month. A **paid Dev or Full seat is the minimum** for the local Dev Mode MCP server.

| Plan | Full | Dev | Collab | Code Connect | MCP notes |
|---|---|---|---|---|---|
| Starter (free) | — | — | — | no | remote MCP throttled (~6 tool calls/mo) |
| **Professional** | $16 | **$12** | $3 | **no** (use prompt/Builder.io) | local MCP on Dev seat; remote ~200 calls/day |
| Organization (annual) | $55 | **$25** | $5 | **yes** | recommended if you want Code Connect |
| Enterprise | $90 | $35 | $5 | yes | — |

Other phase tooling: **html.to.design** free ~12 imports/mo; **Tokens Studio** free tier covers
git-sync for a small team; **Style Dictionary / shadcn / Storybook / v0** as in §1. The
**Framelink/GLips Figma-Context-MCP** is a free open-source alternative that works with any account
(no paid seat) but biases output toward generic structure rather than your codebase patterns.

**Recommendation:** start on **Professional + one Dev seat** ($12/mo) + a curated-component handoff
prompt. Only move to **Organization** for Code Connect if the prompt-based reuse proves too noisy
after PF2. Reassess at open question #6.
