# PreACT English Coach — LOCKED Nav / Interaction / Style Spec

**Status: LOCKED.** This supersedes `PreACT-English-Coach-v2-Wide-Layout-CoachPanel-Implementation-Spec.md`
for every value where the two disagree. Direction **2b** ("hint ladder + conversation") is the
chosen coach-column layout, validated at desktop, iPad (landscape + drawer fallback), and iPhone.
Companion visual: **`Coach Layout Options.dc.html`, turn 5** (redline diagrams — dimension lines +
token callouts on the same four surfaces this doc specifies).

Scope unchanged: frontend-only, `(coach)` route group at `/learn/*`. No backend/engine/LLM/auth
changes. No new npm dependencies.

---

## 1. Breakpoints & the one decision rule

Surface labels are unchanged (`frontend/components/shell/use_surface.ts`):

- `iphone`: viewport width **≤ 480px**
- `ipad`: **481–1024px**
- `desktop`: **> 1024px**

Everything about whether the coach is inline, drawered, or full-screen reduces to **one rule**,
evaluated continuously (on mount and on resize):

```ts
const RAIL_EXPANDED = 224;   // px — w-56, unchanged
const RAIL_COLLAPSED = 64;   // px
const SPLIT_MIN_CONTENT = 900; // px

function coachMode(surface: Surface, viewportWidth: number, sidebarWidth: number):
  "inline" | "drawer" | "fullscreen" {
  if (surface === "iphone") return "fullscreen";       // never inline or drawer
  const contentWidth = viewportWidth - sidebarWidth;
  return contentWidth >= SPLIT_MIN_CONTENT ? "inline" : "drawer";
}
```

`sidebarWidth` is `RAIL_COLLAPSED` on every content screen (see §2 — always collapsed there) or
whatever the Home/Progress persisted state resolves to. This is why iPad **landscape** (1024 − 64 =
960 ≥ 900) gets the inline split and iPad **portrait** (768 − 64 = 708 < 900) gets the drawer —
"landscape/portrait" are just the common real-world instances of the one 900px rule, not a separate
branch of logic.

---

## 2. Shell / sidebar

**File:** `frontend/app/(coach)/learn/layout.tsx` + `frontend/components/shell/AppNav.tsx`.

| Property | Value |
|---|---|
| Expanded width | **224px** (`w-56`, existing) |
| Collapsed (icon rail) width | **64px** |
| Rail item size | **38×38px** circular button (DS `.btn-icon` — the DS touch layer auto-bumps this to 44×44 under `pointer: coarse`, no extra work needed) |
| Rail item spacing | 12px gap, vertical stack, 14px top/bottom padding |
| Expanded row | DS `.nav-item` class as-is (padding 8px 10px, `--radius-md`, `--text-base`/500; `.nav-item.is-active` for the current route) |
| Tooltip on rail icons | DS `.tooltip-content` on hover/focus, shows the nav label |
| Theme toggle position | Last item in the rail (after Progress), separated by a `.separator-h` with 12px margin above; same 38×38 icon-only control in both expanded and collapsed states — **never removed** |
| Toggle control | Chevron button, 40×40px, top of rail; `aria-label="Expand sidebar"` / `"Collapse sidebar"`; global `[` key toggles it (ignored while focus is in `input`/`textarea`/`[contenteditable]`) |
| Motion | `width 180ms cubic-bezier(0.4,0,0.2,1)`; **instant, no transition** under `prefers-reduced-motion: reduce` |

### 2.1 Collapse rule — **locked simple version**

> **Content screens (Quiz, Coach, Skill, Test) always mount with the sidebar collapsed to the icon
> rail. No exceptions, no persisted override.** The learner can manually re-expand mid-session
> (in-memory only); navigating to another content screen — or reloading — collapses it again.

Home and Progress are the only screens with a *persisted* preference:

- `localStorage["preact.shell.sidebar"]` = `"expanded" | "collapsed"`, default `"expanded"`.
- Read on mount of Home/Progress; written whenever the learner toggles on Home/Progress.
- Content-screen toggling never reads or writes this key.

This removes the earlier draft's `sidebarUserPinned` / sessionStorage precedence entirely — one
fewer piece of state, one deterministic rule.

---

## 3. Quiz split (desktop + iPad, `coachMode === "inline"`)

**File:** `frontend/app/(coach)/learn/quiz/page.tsx`.

### 3.1 Height chain (unchanged requirement)

`html,body,#shell { height: 100dvh }` → shell `display:flex;overflow:hidden` → `<main>` `flex:1;
min-height:0;overflow:hidden` → split row `display:flex;height:100%;min-height:0` → each column
`min-height:0` with its own `overflow-y:auto`. The window never scrolls on this surface.

### 3.2 Column widths

| Column | Desktop (>1024px) | iPad (481–1024px, inline mode) |
|---|---|---|
| Icon rail | 64px (fixed) | 64px (fixed) |
| Item column | `flex:1`, inner content `max-width:720px`, centered, `padding:32px 32px 48px` | `flex:1`, inner content `max-width:560px`, centered, `padding:24px 24px 40px` |
| Coach column | `width: clamp(400px, 30vw, 480px)` | **fixed 360px** (no clamp — iPad's bounded width doesn't need one) |
| Divider | 1px solid `var(--color-border)` between columns (no gap) | same |

### 3.3 Item column typography (unchanged content, locked type scale)

- Stem: `--text-2xl` (1.75rem) / 600 / line-height 1.2.
- Question line: `--text-xl` (1.5rem) / 600 / line-height 1.3.
- Option rows: DS `.card`-style container per row — border `1.5px solid color-mix(in oklab, var(--color-fg) 18%, transparent)`, `--radius-lg`, padding `16px 20px`, 8px gap between rows; letter badge 32×32 circle, `1px solid var(--color-border)`, `--text-sm`/600 muted.
- "Get a hint": DS `.btn-outline .btn-lg` + inline override `border-style:dashed;border-color:var(--color-accent);color:var(--color-accent)`.
- "Reveal answer": plain text button, `--text-base`, `var(--color-muted)`.
- "Submit answer": DS `.btn-default .btn-lg`, `width:100%`, height 56px.

---

## 4. Coach column — direction 2b (applies inside inline panel, drawer, AND fullscreen — only the outer width/chrome differs)

**Files:** `frontend/components/coach/CoachPanel.tsx` (inline), new `CoachDrawer.tsx` (<900px),
`CoachWorkspace.tsx`/`CoachChrome.tsx` (iPhone fullscreen route).

Three fixed/scroll/pinned zones, identical structure everywhere:

### 4.1 Zone A — Fixed header

- Padding `16px 18px 12px`; `border-bottom: 1px solid var(--color-border)`.
- Title "Your Coach" — `--text-lg` (1.25rem) / 600. Close (✕, inline mode) or Back (‹, fullscreen-from-tab) — 32×32 DS `.btn-icon.btn-ghost`.
- Status row: DS `.status-orb.is-success` (11px, pulsing per DS keyframe) + `--text-sm` muted text: **`"Adaptive · always on · {topicLabel} · {itemRef}"`** e.g. `"Adaptive · always on · Q1 · s-punc"`. Cold (no pin): **`"Adaptive · Ready when you are"`** — copy-only change, zone height unchanged.
- Mode badges row, 6px gap: active mode = DS `.badge-accent`; inactive = DS `.badge-outline`. Labels verbatim: **"In-drill Socratic"**, **"Deep-dive"**, **"Misconception"** (only shown when flagged).

### 4.2 Zone B — Scroll region (`overflow-y:auto`, DS `.scroll-area-viewport` for the themed scrollbar)

Padding `14px 16px`. Two blocks, top to bottom:

**Hint ladder block**
- Header row: **"HINT LADDER"** (`--text-xs`/700/uppercase/letter-spacing .06em/muted) + right-aligned counter **`"{used} of {total} used"`** (`--text-xs` muted).
- One row per revealed nudge. Row = button, min-height 44px, padding `9px 12px`, `1px solid var(--color-border)`, `--radius-md`.
  - **Collapsed:** chevron (▸, 12px, `var(--color-accent)`) + index `"01"` (mono, `--text-xs`, accent) + the nudge's own short prompt text in full (never truncated — these run 6–10 words by design).
  - **Open:** chevron rotates 90° (150ms; instant under reduced-motion) → `▾`; background becomes `var(--color-accent-light)`, border `color-mix(in oklab, var(--color-accent) 40%, transparent)`; body `padding:0 14px 12px 34px`, `--text-sm`/1.55.
  - **Default state:** the **most-recently revealed** nudge auto-expands; earlier ones default collapsed. Not an exclusive accordion — the learner may manually open more than one; manual state always wins over the auto-expand-latest default for that row until the item changes.
- **"+ One more nudge"** — DS `.btn-outline` + inline `border-style:dashed;color:var(--color-accent);border-color:var(--color-accent)`, `--text-sm`/600, padding `6px 15px`, min-height 44px (touch layer). **Exhausted state:** `opacity:.5;cursor:not-allowed`, `aria-disabled="true"`, and a DS `.tooltip-content` on hover/focus reading **`"You've used all available nudges for this item"`**. Composer position never shifts because of this.

`.separator-h`, margin `14px 0`.

**Conversation block**
- Header: **"CONVERSATION"**, same style as "HINT LADDER".
- User message: `align-self:flex-end`, `max-width:80%`, `background:var(--color-selected)`, `--radius-md`, padding `8px 12px`, `--text-sm`. **Always fully expanded — never collapsible** (the question is the anchor for the collapsed answer below it).
- Coach answer — **`CollapsibleCoachAnswer`**, a real `<button aria-expanded aria-controls>` row, min-height 44px:
  - **Collapsed:** chevron (▸) + **"Coach"** (`--text-sm`/600) + first sentence, single-line, `text-overflow:ellipsis`, `--text-sm` muted. **No timestamp — dropped entirely, both states** (this revises the earlier draft's D1, which included one).
  - **Expanded:** chevron `▾`; summary line hidden; full body shown, padding `0 14px 13px 33px`, `--text-sm`/1.55, `var(--color-fg)`.
  - Container: `1px solid var(--color-border)`, `--radius-md`, `background: var(--color-bg)` — **stays neutral in both states** (unlike ladder rows, which tint on open; this visually separates "pedagogy ladder" from "chat").
  - **Auto-collapse:** when a reply **completes**, all prior non-error answers collapse; the new reply stays expanded. Manual toggles override until the *next* completion re-applies the rule to everything except the new latest.
  - **Streaming:** force-expanded, chevron hidden/disabled, cannot be collapsed until the stream ends.
  - **Error:** force-expanded, excluded from auto-collapse, Retry (DS `.btn-outline .btn-sm`, danger-tinted text) stays inside the visible body.

**a11y (Zone B):**
- The conversation list only is `role="log" aria-live="polite"`. The ladder list is a plain list — **not** inside the live region.
- Revealing a nudge announces via a separate visually-hidden `aria-live="polite"` status node ("Nudge {n} revealed") that clears ~1s later — the ladder rows themselves don't need to sit inside a log region to get this announcement.
- Collapsing/expanding an answer: **no focus move, no live-region write.** Collapsed bodies use the `hidden` attribute (out of the AX tree).

### 4.3 Zone C — Pinned footer (`flex: none`)

Padding `12px 16px` (inline/drawer) — `16px 18px + env(safe-area-inset-bottom)` on iPhone fullscreen.

- Chip row: DS `.btn-outline .btn-sm` per chip, 8px gap, wraps. Copy unchanged: **"Explain the rule simply"**, **"Give me a similar item"**.
- Composer: DS `.composer-box` + `.composer-input` + `.composer-send`, with one override —
  **`.composer-input { min-height: 58px }`** (= 2 lines at `--text-base` 1.125rem / line-height 1.6:
  `2 × 1.125rem × 1.6 = 3.6rem = 57.6px`, rounded to 58px). Placeholder copy: **"Ask about this
  item…"** when an item is pinned, **"Ask the coach…"** in the cold/no-pin state. Send button:
  DS `.composer-send` (36px circle; 44px under `pointer: coarse`).

> Note on the exploration mockups (turns 1–4 above): those cards used compact, hand-tuned sizes at
> a reduced preview scale for fast side-by-side comparison. **This section's values — the DS type
> scale, the DS component classes, and the 58px composer — are the production-locked numbers.**

---

## 5. Drawer (`coachMode === "drawer"`, content width < 900px on desktop or iPad)

**New file:** `frontend/components/coach/CoachDrawer.tsx` — a chrome wrapper that renders the
*same* `CoachPanel` content (composition, not a fork) inside an overlay.

| Property | Value |
|---|---|
| Panel width | `min(430px, 92vw)` |
| Position | `position: fixed; top:0; right:0; bottom:0` |
| Scrim | `position: fixed; inset:0; background: rgba(0,0,0,.32)` |
| Open transition | Panel `transform: translateX(100%) → translateX(0)`, 220ms `cubic-bezier(0.4,0,0.2,1)`. Scrim opacity `0 → 1`, 180ms. **Instant under reduced-motion.** |
| Close triggers | ✕ button (32×32, top-right of drawer header) · click on scrim · `Escape` key |
| Focus | On open: focus moves to the drawer's close button. Tab/Shift+Tab cycle **inside** the drawer only (focus trap). On close: focus **returns to the trigger pill**. |
| Background interaction | While open, the quiz content behind the scrim is `aria-hidden="true"` (or `inert` where supported) and pointer-events are blocked by the scrim. |
| Trigger (drawer closed) | Floating pill, `position:fixed; bottom:24px; right:24px` (+ safe-area), height 44px, label **"Coach"** + `.status-orb.is-success` dot, shadow per DS `.toast` shadow token. |

---

## 6. iPhone (`coachMode === "fullscreen"`) — unchanged behavior, confirmed

- Quiz stays the existing single-column focus screen: `FocusModeChrome` (✕, no tabs), full-width
  item, rung-1 "Get a hint" on the item. **No inline panel, no drawer, ever** — regardless of any
  future viewport width on this surface class.
- Coach is a distinct **full-screen route** (`/learn/coach`), same Zone A/B/C stack at 100% width,
  `env(safe-area-inset-*)` padding.
  - Entered from the **bottom tab bar** → Zone A shows Back (‹) + the tab bar stays visible (4 tabs:
    Home / Practice / Coach / Progress — **Skill is not in the iPhone tab set**, unchanged from
    `nav_model.ts`).
  - Entered from the **Feedback bridge** or mid-drill → focus mode (✕, no tab bar).
- Zone B/C internals (ladder, collapsible answers, pinned composer/chips) are **identical** to
  desktop/iPad — one component, no iPhone-specific fork.

---

## 7. Feedback → Coach bridge

**File:** `frontend/components/feedback/FeedbackView.tsx` (or equivalent), button copy unchanged:
**"Ask the coach about this."**

```ts
function onAskCoach() {
  setCoachPin(currentItemContext);
  if (surface === "iphone") { router.push("/learn/coach"); return; }
  if (coachMode === "drawer") {
    openDrawer();                              // triggers the 220ms slide-in
    afterTransition(220, () => composerRef.current?.focus());
    return;
  }
  if (panelDismissed) setPanelDismissed(false); // re-open an inline panel the learner had hidden
  requestAnimationFrame(() => composerRef.current?.focus());
}
```

No route change on desktop/iPad in either inline or drawer mode. iPhone is the only surface that
still navigates.

---

## 8. State model (final)

| State | Type | Lives in | Persistence |
|---|---|---|---|
| `sidebarCollapsed` (content screens) | `boolean` | local component state | **none** — always initializes `true` on mount |
| `sidebarCollapsed` (Home/Progress) | `boolean` | `shell_layout_store` | `localStorage["preact.shell.sidebar"]`, default `expanded` |
| `panelDismissed` | `boolean` | `shell_layout_store` | `sessionStorage["preact.shell.panelDismissed"]` (inline mode only) |
| `drawerOpen` | `boolean` | local to quiz page / `CoachWorkspace` | none — ephemeral |
| `revealed` (nudge count) | `number` | `CoachPanel` local (existing) | none — resets per item |
| `ladderManualOverride` | `Map<nudgeIndex, boolean>` | `use_expandable_list` (ladder instance) | none — resets per item |
| `expandedTurnIds` / `manualTurnOverride` | derived `Set` / `Map<id,boolean>` | `use_expandable_list` (conversation instance) | none — re-derived on reload (newest expanded) |
| thread · pin · mode | store snapshot | `coach_thread_store` (existing) | unchanged |

`use_expandable_list.ts` is **one generic hook** (`useExpandableList({ items, autoExpandId,
forceExpandedIds })`) used for **both** the ladder and the conversation list — not two hooks. This
replaces the earlier draft's separate `use_collapsible_thread`.

---

## 9. Component inventory (final)

**New:** `CoachDrawer.tsx`, `CoachTriggerPill.tsx`, `CollapsibleCoachAnswer.tsx` (no timestamp prop),
`HintLadderList.tsx`, `use_expandable_list.ts` (generic hook, replaces the two-hook draft).

**Changed:** `learn/layout.tsx` (rail always-collapsed-on-content-screens rule, drop session-pin
logic), `AppNav.tsx` (icon rail variant), `quiz/page.tsx` (coachMode switch, drawer wiring, bridge),
`CoachPanel.tsx` (Zone A/B/C restructure, ladder extraction), `CoachWorkspace.tsx` / `CoachChrome.tsx`
(same zones, iPhone fullscreen chrome), `FeedbackView.tsx` (bridge per §7).

**Not a component:** the height chain (`100dvh` + `min-height:0` + `overflow-y:auto` on Zone B) —
a className contract, documented, not abstracted.

---

## 10. Design tokens used (reference — no new tokens invented)

| Token | Light value | Dark value |
|---|---|---|
| `--color-bg` | `#f9f7f5` | `#241c15` |
| `--color-fg` | `#1f1e1d` | `#f9f7f5` |
| `--color-muted` | `#7d7a75` | `#e4e1da` |
| `--color-accent` | `#d87758` | `#e5967c` |
| `--color-accent-light` | `color-mix(accent 15%, transparent)` | `rgba(229,150,124,.22)` |
| `--color-border` | `color-mix(fg 12%, transparent)` | `rgba(248,248,248,.141)` |
| `--color-surface` | `color-mix(bg 96%, fg 4%)` | `#322a24` |
| `--color-surface-sunken` | `color-mix(bg 92%, fg 8%)` | `#3f3831` |
| `--color-selected` | `color-mix(fg 6%, transparent)` | `rgba(245,245,245,.102)` |
| `--color-success` | `#2f8f5b` | `#5cba86` |
| `--color-danger` | `#c0392b` | `#e57368` |
| `--radius-sm/md/lg` | `10px / 16px / 22px` | same |
| `--text-xs…2xl` | `0.875 → 1.75rem`, line-heights `1.2–1.5` | same |
| `--font-sans` | Geist stack | same |

Components consumed as-is: `.btn-*`, `.badge-*`, `.composer-box`/`.composer-input`/`.composer-send`,
`.nav-item`, `.status-orb`, `.tooltip-content`, `.scroll-area-viewport`, `.separator-h`, `.card`/`.etched`.
Touch layer (`@media (pointer: coarse)`) already bumps hit targets to ≥44px — no bespoke touch CSS
needed.

---

## 11. Acceptance criteria (EARS) — locked, supersedes the draft's 15

**Failure & edge paths**

- **AC-1** — IF content width is below 900px, THEN THE SYSTEM SHALL NOT render the coach inline; it SHALL render as an overlay drawer opened via a pinned "Coach" control.
- **AC-2** — WHILE the drawer is open, THE SYSTEM SHALL trap focus within it, close it on Escape or a scrim click, and return focus to the trigger control on close.
- **AC-3** — WHILE a coach reply is streaming, THE SYSTEM SHALL force that answer expanded and SHALL NOT allow it to be collapsed until the stream completes.
- **AC-4** — IF a coach turn is in an error state, THEN THE SYSTEM SHALL keep it expanded, exclude it from auto-collapse, and keep Retry reachable.
- **AC-5** — WHEN all ladder rungs for the current item are exhausted, THEN THE SYSTEM SHALL disable "One more nudge" with an accessible reason, without moving or hiding the composer.
- **AC-6** — WHILE the sidebar is collapsed, THE SYSTEM SHALL keep the theme toggle reachable in the icon rail.
- **AC-7** — WHEN the learner collapses or expands a coach answer, THE SYSTEM SHALL NOT move keyboard focus and SHALL NOT re-announce prior content through the live region.
- **AC-8** — IF prefers-reduced-motion is set, THEN THE SYSTEM SHALL apply all sidebar, answer, and drawer transitions instantly, with no animation.
- **AC-9** — WHEN the learner navigates to Quiz, Coach, Skill, or Test, THE SYSTEM SHALL always mount the sidebar collapsed to the icon rail, regardless of prior session state.

**Nominal behavior**

- **AC-10** — WHERE the surface is desktop or iPad AND content width is at least 900px, THE SYSTEM SHALL render the quiz item and the live coach panel side-by-side sharing one coach thread.
- **AC-11** — WHILE on the inline split, THE SYSTEM SHALL scroll the item column and the coach log independently and SHALL NOT scroll the browser window.
- **AC-12** — THE SYSTEM SHALL keep the composer, chip row, and "One more nudge" control pinned and visible regardless of coach-log scroll position.
- **AC-13** — WHEN a coach reply completes, THE SYSTEM SHALL collapse all prior non-error answers and keep only the newest expanded.
- **AC-14** — WHEN a new nudge is revealed, THE SYSTEM SHALL auto-expand that ladder row and leave every other ladder row in its current state.
- **AC-15** — THE SYSTEM SHALL render the coach composer with a minimum input height of two text lines (58px) at all times, growing further as typed content wraps.
- **AC-16** — WHEN the learner activates "Ask the coach about this" on a wide, inline-mode surface, THE SYSTEM SHALL pin the item context and move focus to the coach composer without navigating.
- **AC-17** — WHEN the learner activates "Ask the coach about this" while content width is below 900px, THE SYSTEM SHALL open the coach drawer, pin the item context, and move focus to the composer once the open transition completes.
- **AC-18** — WHERE the surface is iPhone, THE SYSTEM SHALL NOT render an inline coach panel or a drawer; Coach SHALL be reachable only as a full-screen route, and Skill SHALL NOT appear in its tab bar.
- **AC-19** — WHEN the learner dismisses the inline coach panel, THE SYSTEM SHALL preserve the coach thread and keep it reachable from the Coach nav item.
- **AC-20** — THE SYSTEM SHALL render a collapsed coach answer as a chevron, the label "Coach", and a single-line truncated first sentence, with no timestamp.

---

## 12. Test matrix

| AC | Test type | Assertion | Viewport(s) |
|---|---|---|---|
| AC-1 | E2E (Playwright) | At 768×1024 (iPad portrait), `[data-testid=coach-panel-inline]` absent; `[data-testid=coach-trigger-pill]` visible | 768×1024 |
| AC-2 | E2E | Open drawer → `Escape` closes it; focus lands back on trigger pill; Tab cycles only within drawer while open | 768×1024, 390×844 (n/a — iPhone has no drawer, negative test) |
| AC-3 | Component (RTL) | Render turn with `status:"streaming"` → toggle button `disabled`/absent; `aria-expanded=true` fixed | n/a |
| AC-4 | Component | Render turn with `status:"error"` → expanded, Retry button present after simulated auto-collapse event | n/a |
| AC-5 | Component | `usedNudges === total` → button `aria-disabled=true`, `title` set, composer position (snapshot) unchanged | n/a |
| AC-6 | E2E | Collapse sidebar → theme toggle still clickable, toggles `data-theme` | 1440×900, 1024×768 |
| AC-7 | Component + axe | Toggle collapse → `document.activeElement` unchanged; no new `aria-live` text node created | n/a |
| AC-8 | E2E (emulate `prefers-reduced-motion: reduce`) | Sidebar/drawer/answer transitions: computed `transition-duration` is `0s` | 1440×900 |
| AC-9 | E2E | Navigate Home (expanded) → Quiz → sidebar width is 64px on mount | 1440×900, 1024×768 |
| AC-10 | E2E | At 1440×900 and 1024×768, both `[data-testid=quiz-item]` and `[data-testid=coach-panel-inline]` are visible simultaneously | 1440×900, 1024×768 |
| AC-11 | E2E | Scroll coach log → item column `scrollTop` unchanged; `document.scrollingElement.scrollTop === 0` throughout | 1440×900 |
| AC-12 | E2E | Scroll log to bottom → composer/chips/nudge button bounding-box `top` unchanged before/after | 1440×900 |
| AC-13 | Unit (`use_expandable_list`) | Given 3 completed turns + 1 new completion → expanded set `= {newest.id}` | n/a |
| AC-14 | Unit | Reveal nudge 3 → `expandedLadderIds` includes 3; 1 and 2 retain prior state | n/a |
| AC-15 | Component | Computed `min-height` of `.composer-input` `== 58px` | n/a |
| AC-16 | E2E | Click "Ask the coach about this" on 1440×900 → no `location` change; composer `document.activeElement` | 1440×900 |
| AC-17 | E2E | Same click at 768×1024 → drawer `translateX(0)` after 220ms; composer focused | 768×1024 |
| AC-18 | E2E | At 390×844, no element matches `[data-testid=coach-panel-inline]` or `[data-testid=coach-drawer]`; tab bar has exactly 4 items, none labeled "Skill" | 390×844 |
| AC-19 | E2E | Dismiss panel → navigate to `/learn/coach` → prior turns still present | 1440×900 |
| AC-20 | Component | Collapsed answer DOM: chevron + "Coach" + one truncated `<span>`; no time-formatted node present | n/a |

---

## 13. Non-goals (unchanged)

iPhone tab bar/focus-mode redesign beyond what's specified in §6 · question/hint bank content ·
hint-rung pedagogy · non-reveal guarantee · coach LLM behavior/prompts · auth/WorkOS · backend/engine ·
any new npm dependency · Dashboard/Summary/Skill/Progress/Test screen internals beyond shell chrome ·
theme tokens/palette.
