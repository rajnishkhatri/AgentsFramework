> **EXPORT NOTE (corrected 2026-06-23 against the shipped app) —** this package ships the
> stylesheet (`styles.css`) rebased to **root = 16px** (production). Where this spec still shows a
> "px @17.5" column below, that column is **STALE** — the **rem column is canonical**; multiply by
> **16** for production px (e.g. `--radius-lg` 0.75rem = **12px**, NOT 13.125px).
>
> **Verified production tokens** (warm-neutral terracotta, from `design/tokens/*` →
> `app/generated-theme.css`): `--color-muted` = **#7d7a75** (light) / **#e4e1da** (dark);
> dark `--color-bg` = **#241c15** (cocoa). An earlier draft of this export wrongly listed
> cool-gray `#6b7280`/`#9ca3af` and `#1f1e1d` — those are the dead pre-terracotta values and the
> dark *fg*; the §2.6 contract forbids cool-gray. Corrected here. Run `Verify.html` for live confirmation.
>
> **Detail panel (§2.1, §4.2):** the right-hand `w-80` detail / bottom-Sheet reasoning panel is
> **NOT yet implemented** — the shipped app is **two-pane** (`grid lg:grid-cols-[auto_2px_1fr]` =
> rail · groove · chat). Treat every "three-pane" / `w-80` / detail-panel reference below as the
> *design target*, not as-shipped. (Deferred; see the plan's P-future note.)
>
> **Touch targets:** the app meets ≥44pt **always-on** via Tailwind `size-11`/`min-h-11` (not the
> bundle's `@media (pointer: coarse)` gate). Both reach 44pt; the mechanism differs.

# AgentsFramework UI — Responsive Layout Spec

**Status:** frozen · **Source of truth:** `_ds/agentsframework-ui-f8ce5c07-a053-4017-a4c0-b0602a2fc3e8/styles.css` + `uploads/conventions.md`
**Last verified against bundle:** 2026-06-23

This spec gives **exact, verifiable values** for three device targets — **Desktop**, **iPhone**, **iPad**.
Every value is traced to a token or class in the bundle. Nothing here is invented. Where a value is
*derived* (e.g. a CSS px from a `rem`), the formula is shown so it can be re-checked.

> **Root font size is 16px in production.** The shipped app has **no** `html{font-size}` override,
> so `rem` resolves against the browser default **16px**. (The standalone bundle preview uses 17.5px,
> which is why the "px @17.5" columns below are stale — divide-and-rebase: **1rem = 16px**.) All `rem`
> values — Tailwind width classes (`w-64`, `p-4`), container-query thresholds — resolve at 16px.
> Examples @16: `--radius-lg` = 12px, `w-64` = 256px, `@container/composer` 20rem = 320px,
> `@container/tool` 22rem = 352px. The `rem` column is canonical.

---

## 0. Breakpoint model (the whole system is TWO layouts, not three)

| Mode | Condition | Pointer | Used by |
|---|---|---|---|
| **Three-pane** | viewport width **≥ 1024px** (`lg`) | any | Desktop · iPad landscape |
| **Single-column + drawer** | viewport width **< 1024px** | any | iPhone · iPad portrait |

- The switch is a **viewport** breakpoint at **`lg` = 1024px**. There is exactly one fork.
- **Touch sizing is a separate axis**, keyed on `@media (pointer: coarse)` — it applies to **both**
  iPhone and iPad regardless of layout mode, and **never** to desktop (fine pointer).
- Component internals adapt by **container width**, not viewport (see §5).

**Verification:** at 1023px the thread rail is a Sheet drawer; at 1024px it is the inline rail. One pixel flips it.

---

## 1. Shared foundation (identical on all three devices)

These are device-independent. Do not redefine per device.

### 1.1 Color tokens — light (`:root`)
| Token | Value |
|---|---|
| `--color-bg` | `#f9f7f5` |
| `--color-fg` | `#1f1e1d` |
| `--color-muted` | `#7d7a75` |
| `--color-accent` | `#c2704e` |
| `--color-accent-light` | `color-mix(in oklab, var(--color-accent) 15%, transparent)` |
| `--color-border` | `color-mix(in oklab, var(--color-fg) 12%, transparent)` |
| `--color-border-light` | `color-mix(in oklab, var(--color-fg) 10%, transparent)` |
| `--color-surface` | `color-mix(in oklab, var(--color-bg) 96%, var(--color-fg) 4%)` |
| `--color-surface-sunken` | `color-mix(in oklab, var(--color-bg) 92%, var(--color-fg) 8%)` |
| `--color-selected` | `color-mix(in oklab, var(--color-fg) 6%, transparent)` |
| `--color-danger` | `#c0392b` |
| `--color-success` | `#2f8f5b` |

### 1.2 Color tokens — dark (`[data-theme="dark"]`)
| Token | Value |
|---|---|
| `--color-bg` | `#241c15` |
| `--color-fg` | `#f9f7f5` |
| `--color-muted` | `#e4e1da` |
| `--color-accent` | `#d98b6a` |
| `--color-accent-light` | `color-mix(in oklab, var(--color-accent) 22%, transparent)` |
| `--color-border` | `color-mix(in oklab, var(--color-fg) 14%, transparent)` |
| `--color-surface` | `color-mix(in oklab, var(--color-bg) 92%, var(--color-fg) 8%)` |
| `--color-surface-sunken` | `color-mix(in oklab, var(--color-bg) 85%, var(--color-fg) 15%)` |
| `--color-selected` | `color-mix(in oklab, var(--color-fg) 10%, transparent)` |
| `--color-danger` | `#e57368` |
| `--color-success` | `#5cba86` |

The single rationed accent rule (§2.6) holds on every device: **terracotta accent only on the one primary CTA per screen.**

### 1.3 Radius tokens
| Token | rem | px @17.5 | Applies to |
|---|---|---|---|
| `--radius-sm` | `0.375rem` | `6.5625px` | chips, badges, small buttons |
| `--radius-md` | `0.5rem` | `8.75px` | inputs, buttons, icon buttons |
| `--radius-lg` | `0.75rem` | `13.125px` | cards, dialogs, sheets, message bubbles |

Pill composer / round buttons use literal `999px` / `50%`, not a token.

### 1.4 Type scale (root = 17.5px)
| Token | rem | px @17.5 |
|---|---|---|
| `--text-xs` | `0.75rem` | `13.125px` |
| `--text-sm` | `0.875rem` | `15.3125px` |
| `--text-base` | `1rem` | `17.5px` |
| `--text-lg` | `1.125rem` | `19.6875px` |
| `--text-xl` | `1.375rem` | `24.0625px` |
| `--text-2xl` | `1.625rem` | `28.4375px` |

Fonts: `--font-sans` = system stack with **Geist** (weights 400/500/600/700); `--font-mono` = system mono.
The type scale **does not change per device** — only layout, hit targets, and spacing do.

---

## 2. Desktop  ·  ≥1024px, fine pointer

### 2.1 Layout — three-pane
```
[ sidebar (sunken) ] │ [ main chat — flex-1 ] │ [ detail panel — collapsible ]
```

| Region | Width | Source | Notes |
|---|---|---|---|
| Sidebar rail (expanded) | `w-64` = **16rem** = `280px` @17.5 | conventions §5 / responsive | Design-target wording says "260px"; as-shipped class is `w-64`. **Canonical = `w-64`.** |
| Sidebar rail (collapsed) | `w-12` = **3rem** = `52.5px` @17.5 | responsive mechanics | Toggle is `w-64 ↔ w-12` |
| Main chat | `flex-1` (fills remainder) | conventions §5 | — |
| Detail panel | `w-80` = **20rem** = `350px` @17.5 | conventions §5 | Collapsible; design-target wording "320px" |
| Rail ↔ chat divider | `.separator-etched-v` (2px etched groove) | conventions | Use groove, **not** flat 1px rule |

Sidebar background = `--color-surface-sunken` (recessed Cursor-rail look). Hairline borders only; **no ambient shadows** (shadows reserved for overlays).

### 2.2 Interactive sizing (base / fine-pointer)
| Element | Size |
|---|---|
| Icon button (`.btn-icon`) | `36 × 36px` |
| Input (`.input`) | height `36px` |
| Button md (`.btn-md`) | padding `8px 16px` |
| Button sm (`.btn-sm`) | padding `4px 10px` |
| Button lg (`.btn-lg`) | padding `10px 20px` |
| Composer pill | `border-radius:999px; padding:7px 8px` |
| Composer icon / send / mic | `36 × 36px` round |
| Tabs trigger | padding `6px 14px` |

### 2.3 Chrome
- Header underline, sidebar group dividers, "TODAY" thread group → `.separator-etched` grooves.
- Tooltips **render** (desktop is `(hover: hover)`).
- Per-message actions → `DropdownMenu` on hover.

---

## 3. iPhone  ·  390–430px, coarse pointer (<1024 → single-column)

Reference widths: **iPhone 15/16 (393×852)**, 12–14 (390×844), Plus/Pro Max (430×932).

### 3.1 Layout — single column + drawer
- Thread rail **hidden**; opened as a **left `Sheet` drawer** via header hamburger.
  - Toggle: `data-testid="drawer-toggle"`, `aria-label="Open conversations"`, **44×44 hit area**.
  - Drawer **auto-closes** on thread-select / new-chat.
- Detail panel → **bottom `Sheet`** (reasoning panel).
- Pill composer pinned to **bottom**, inside safe-area inset.

### 3.2 Touch sizing (`@media (pointer: coarse)` — overrides base)
| Element | Base | **Coarse (iPhone)** |
|---|---|---|
| Icon button | 36×36 | **44×44** |
| Input height | 36 | **44** |
| Textarea min-height | 40 | **48** |
| Composer icon/send/mic | 36×36 | **44×44** |
| Button sm | `4px 10px` | **`10px 16px`**, `.9375rem` |
| Button md | `8px 16px` | **`11px 18px`** |
| Button lg | `10px 20px` | **`13px 22px`** |
| Tabs trigger | `6px 14px` | **`10px 16px`** |
| Composer pill | `7px 8px` | **`8px 8px 8px 10px`** |

**Rule:** every interactive control ≥ **44pt** hit area; the icon glyph stays `size-4/5`, only the button grows.

### 3.3 Compact states
- **< `sm` (640px):** hide header email; main padding tightens `p-3` (`0.75rem`=`13.125px`) → `sm:p-4` (`1rem`=`17.5px`) above 640.
- Sticky `:hover` neutralised under `@media (hover: none)` (no stuck hover after tap).
- Tooltips **do not render** on touch — gated at call site.
- Safe-area padding via `env(safe-area-inset-*)` at layout level. Reference iPhone insets: top **59px** (Dynamic Island) / **47px** (notch), bottom **34px** (home indicator).

---

## 4. iPad  ·  orientation-dependent, coarse pointer

iPad is the one device that **crosses the `lg` breakpoint by orientation.** Spec both states.

Reference sizes: iPad mini 744×1133 · iPad Air 11" **820×1180** · iPad Pro 11" 834×1194 · iPad Pro 13" 1024×1366.

### 4.1 iPad **portrait** (width 744–834px → **< 1024 → MOBILE layout**)
- Uses the **iPhone single-column + drawer layout** from §3 verbatim. Thread rail = left Sheet; detail = bottom Sheet.
- Touch sizing **44px** applies (coarse pointer) — identical to §3.2.
- Above `sm` (640): header email **shows**, main padding `sm:p-4`. (iPad portrait is always ≥744, so it is always in the `≥sm` band — never the §3.3 compact `<640` band.)

### 4.2 iPad **landscape** (width 1024–1366px → **≥ 1024 → DESKTOP layout**)
- Uses the **three-pane layout** from §2: inline `w-64 ↔ w-12` rail, `flex-1` chat, `w-80` detail panel, `.separator-etched-v` divider.
- **But** touch sizing **44px** still applies (coarse pointer): icon buttons 44×44, inputs 44, composer buttons 44 — i.e. the desktop layout with touch-sized controls.
- Tooltips **do not render** (touch); `@media (hover: none)` neutralises hover states even though layout is the desktop three-pane.

### 4.3 The iPad gotcha (must verify)
> iPad Pro 13" portrait is **1024 in landscape, 1024 wide is the threshold** — portrait 13" is 1024px wide and lands **exactly on `lg`**, so it renders **three-pane**, unlike the 11"/Air which are < 1024 portrait and render single-column. Test on the specific iPad target.

| iPad | Portrait width | Portrait layout | Landscape width | Landscape layout |
|---|---|---|---|---|
| mini | 744 | single-column | 1133 | three-pane |
| Air 11" | 820 | single-column | 1180 | three-pane |
| Pro 11" | 834 | single-column | 1194 | three-pane |
| Pro 13" | **1024** | **three-pane** | 1366 | three-pane |

---

## 5. Container queries (all devices — adapt by SLOT, not screen)

Components carry named containers and degrade by their own width, so they read correctly in a wide
Mac window *and* a narrow drawer slot. Thresholds are `rem` (×17.5 for px @ this root).

| Container | Threshold | Behaviour below threshold |
|---|---|---|
| `@container/composer` | `20rem` (`350px` @17.5) | model-picker **label hides**, chevron stays |
| `@container/tool` | `22rem` (`385px` @17.5) | ToolCard **subtitle hides** |
| `@container/understanding` | — | provenance label **wraps** under its heading |

**Design rule:** components degrade by **slot width**, never screen width. Verify by resizing the *panel*, not the window.

---

## 6. Verification checklist

Each row is a deterministic check. Set the viewport, then assert the computed value.
`getComputedStyle(el)` returns px; compare against the **px @17.5** column above.

### 6.1 Layout-mode checks
- [ ] **@1024px** — inline thread rail present (`w-64`/`w-12`), no Sheet backdrop. ✅ three-pane
- [ ] **@1023px** — thread rail absent; hamburger `[data-testid="drawer-toggle"]` present, 44×44. ✅ single-column
- [ ] **iPhone 393** — composer pinned bottom, within `env(safe-area-inset-bottom)`; detail opens as bottom Sheet.
- [ ] **iPad Air portrait 820** — single-column + left Sheet drawer (NOT three-pane).
- [ ] **iPad Air landscape 1180** — three-pane; `.btn-icon` computes **44×44** (touch), tooltips absent.

### 6.2 Token checks (any device)
- [ ] `getComputedStyle(document.documentElement).getPropertyValue('--color-accent')` → `#c2704e` (light) / `#d98b6a` (dark).
- [ ] `.card` border-radius → `13.125px` (`--radius-lg`).
- [ ] `.input` border-radius → `8.75px` (`--radius-md`).
- [ ] Primary CTA uses `.btn-default` gradient + `inset 0 1px 0` highlight — exactly one per screen.

### 6.3 Touch-axis checks
- [ ] Fine pointer (desktop): `.btn-icon` → `36×36`, `.input` height → `36`.
- [ ] Coarse pointer (iPhone + iPad): `.btn-icon` → `44×44`, `.input` height → `44`, `.textarea` min-height → `48`.
- [ ] `@media (hover: none)`: `.nav-item:hover` background is transparent (no sticky hover); `.nav-item.is-active` keeps `--color-selected`.

### 6.4 Container-query checks
- [ ] Composer in a `<20rem` slot: model-picker label hidden, chevron visible.
- [ ] ToolCard in a `<22rem` slot: subtitle hidden.

### 6.5 Surface-language checks
- [ ] Primary divides use `.separator-etched*` grooves (2px, dark-over-#fff85%), not flat 1px.
- [ ] ToolCard / TaskUnderstanding card use `.etched` (inset shadow + bottom highlight).
- [ ] User bubble uses `.bubble-user` gradient, right-aligned, `--radius-lg`; assistant answer is uncarded prose.
- [ ] Icons are lucide line SVGs — **zero emoji**.

---

## 7. Open / to-confirm

1. **Root font size in production.** This spec computes px at `html{font-size:17.5px}` (the bundle's value).
   If the shipped app uses 16px, the px columns shift; rem columns stay valid. — *confirm root.*
2. **Sidebar width wording.** Conventions §5 says "260px"/"320px"; as-shipped classes are `w-64`/`w-80`
   (280px/350px @17.5, or 256px/320px @16). Spec treats the **class** as canonical. — *confirm intended px.*
3. iPad Pro 13" portrait (1024px) renders three-pane — confirm that's desired vs. forcing single-column there.
