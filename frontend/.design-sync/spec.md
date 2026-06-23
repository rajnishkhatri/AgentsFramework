# AgentsFramework UI — Screen Layout Spec (the global layout contract)

> **What this is.** The single authoritative layout contract for the AgentsFramework chat surface,
> at the *screen* level (above the 14 component primitives). Every value here is **verified against
> the shipped app code** (`frontend/app/chat-shell.tsx`, `components/chat/Composer.tsx`,
> `components/tools/ToolCard.tsx`, `app/globals.css`) on 2026-06-23 — it is a description of what
> ships, not an aspiration. This is the `spec.md` the sync handbook §1.2 calls for.
>
> **Source of truth for values:** `frontend/design/tokens/` (colors/radius/type/space) — never
> hard-code; use `var(--*)`. **Root font = 16px** (no `html` override; the DesignSync previews use
> 17.5px — that is preview-only and does NOT apply here).
>
> **Companion docs:** `docs/plans/designsync_code_sync.handbook.md` (the sync model),
> `frontend/.design-sync/conventions.md` (design intent: terracotta-only, lucide-never-emoji).

---

## 0. Verification rule

Every value below is **literal and measurable** (px, rem, token, Tailwind class) so a test can
assert it. "Comfortable padding" is not a spec. When the app changes, update this file in the same
commit — a screen spec that lags the code is the silent-drift failure mode (the three-pane panel
that lived here for weeks while the app shipped two-pane).

---

## 1. App shell — the outer frame

**Root grid** (`chat-shell.tsx:428`):
```
min-h-dvh  grid  grid-rows-[auto_auto_1fr]
```
- Row 1 (`auto`): top bar (hamburger on mobile, sign-out, status).
- Row 2 (`auto`): secondary chrome row.
- Row 3 (`1fr`): the body (rail + chat), fills remaining height.
- `min-h-dvh` (dynamic viewport height) — correct on mobile where the URL bar collapses.

**Body grid** (`chat-shell.tsx:523`) — **two-pane**:
```
grid  lg:grid-cols-[auto_2px_1fr]   overflow-hidden
```
- `auto` = the recessed rail · `2px` = the etched groove · `1fr` = the chat column.
- Below `lg`, the columns collapse — single chat column; the rail moves into a Sheet (§3).
- **There is NO third (detail) pane.** A right-hand `w-80` detail/reasoning panel is a *deferred,
  not-built* feature (handbook §4). Do not spec it as shipped.

---

## 2. Breakpoints

| Token | Value | What flips |
|---|---|---|
| `lg` | **1024px** | Body grid becomes the 3-track two-pane (rail · groove · chat). Rail shows inline (`hidden lg:block`); the mobile Sheet trigger hides (`lg:hidden`). |
| `sm` | **640px** | Main padding `p-3` → `p-4` (`p-3 sm:p-4`); sign-out label appears (`hidden sm:inline`). |

Below `lg` the layout is **single-column chat**; the navigation rail is reached via a Sheet.

---

## 3. Navigation rail

- **Desktop (`≥lg`):** inline first column, `hidden lg:block overflow-y-auto bg-surface-sunken`
  (`chat-shell.tsx:527`). Recessed (sunken surface) — reads as carved into the frame.
- **Separator:** `separator-etched-v hidden lg:block` (`:551`) — the 2px etched groove between
  rail and chat. This is one of the shared tactile recipes (lives in `globals.css`).
- **Mobile (`<lg`):** the rail content moves into a Sheet, `w-[18rem] p-0 bg-surface-sunken lg:hidden`
  (`:499`), opened by the hamburger (§5).

---

## 4. Chat column

**Structure** (`chat-shell.tsx:555`): `grid grid-rows-[1fr_auto]` — message list (`1fr`) over the
pinned composer (`auto`).

- **Message list** (`:556`): `<main>` `overflow-y-auto p-3 sm:p-4`.
- **Content column width** (`:567`): `max-w-3xl mx-auto` — the answer/messages are capped at
  `max-w-3xl` (48rem = 768px) and centered. Same cap applies to the composer (§6).
- **User bubble** (`:570`): `bubble-user justify-self-end rounded-lg px-4 py-2 max-w-[80%]` —
  right-aligned, terracotta gradient (the `.bubble-user` tactile recipe), radius `lg`, max 80% width.
- **Assistant turn** (`:573`): `justify-self-start max-w-[80%] w-full grid gap-1` — left-aligned,
  uncarded prose (the answer is NOT in a card; tool/understanding cards are).

---

## 5. Top bar / chrome

- **Hamburger** (`chat-shell.tsx:447`): `lg:hidden -ml-2 size-11 …` — **44×44pt** tap target,
  mobile only, opens the rail Sheet.
- **Sign-out** (`:472`): `inline-flex min-h-11 items-center px-2 …` — **44pt-tall** tap target
  (height floored by `min-h-11`, width by padding). Label `hidden sm:inline`.

---

## 6. Composer (pinned, bottom of chat column)

**Container** (`Composer.tsx:78`):
```
@container/composer  grid gap-2 p-3
rounded-lg  border border-border  bg-surface-sunken
```
- Pill-ish recessed panel, radius `lg`, sunken surface, its own **container-query context**
  (`@container/composer`) — the toolbar adapts to the *composer's* width, not the viewport.
- **Width cap** (`chat-shell.tsx:634`): `max-w-3xl mx-auto w-full` — matches the message column.
- **Safe-area padding** (`:634`):
  `p-2 pb-[max(0.5rem,var(--safe-bottom))] pl-[max(0.5rem,var(--safe-left))] pr-[max(0.5rem,var(--safe-right))]`
  — floors to 0.5rem off-device, expands to the device inset on iOS (notch / home indicator).

**Textarea** (`Composer.tsx:18`): `min-h-[2.5rem]` (40px) … `max-h-[12rem]` (~6 lines) autosize
bracket. **This 40px is a text field min-height, NOT a tap-target floor** — do not "fix" it to 44.

**Toolbar controls:**
- **Add button** (`:112`): `flex size-11 … rounded-full` — **44×44pt**, glyph stays `size-4`.
- **Model picker** (`:126`): `inline-flex min-h-11 … rounded-sm px-2 py-1` — **44pt-tall**; label
  hides under the container threshold (next row).
- **Send button** (`:144`): `btn-shine ml-auto flex size-11 … rounded-full` — **44×44pt**,
  terracotta `.btn-shine` puck, arrow glyph `size-5`.

---

## 7. Container-query thresholds (component-local, not viewport)

These adapt to the component's own slot width, measured in rem at 16px root.

| Context | Threshold | Behavior |
|---|---|---|
| `@container/composer` | `@[20rem]` = **320px** | Model-picker label shows ≥320px (`hidden @[20rem]/composer:inline`), hides below (`Composer.tsx:133`). |
| `@container/tool` | `@[22rem]` = **352px** | ToolCard subtitle shows ≥352px (`hidden @[22rem]/tool:inline`), hides below (`ToolCard.tsx:90`). |
| `@container/understanding` | (context only) | TaskUnderstandingCard establishes the context (`TaskUnderstandingCard.tsx:107,203`); no hide threshold currently. |

---

## 8. Touch-target floor — ALWAYS-ON

Every interactive control meets **≥44pt**, encoded always-on via Tailwind `size-11` (44×44) or
`min-h-11` (44 tall), **not** gated behind `@media (pointer: coarse)`. Verified occurrences:
hamburger, sign-out, composer Add / model-picker / Send. The textarea's `min-h-[2.5rem]` is the one
intentional exception (text field, not a tap target).

---

## 9. Safe areas (native wrap)

`globals.css:38-41` defines `--safe-top/right/bottom/left` = `env(safe-area-inset-*, 0px)`. They
resolve to **0 off-device** (web/desktop unaffected) and expand inside the iOS WKWebView. Applied at
the **layout level** (composer padding), never inside primitives — so a Button is identical on web
and iOS, and only the screen frame respects the notch/home-indicator.

---

## 10. Typography

The type system has two parts: a **font strategy** (which font) and a **semantic role table**
(which size/weight a given piece of text uses). Values come from `frontend/design/tokens/`
(`font.tokens.json`, `type.tokens.json`) — never hard-code. Root = 16px (px below at 16px root).

### 10a. Font strategy — frozen (v12), preserve verbatim

One sans family, one mono. From `font.tokens.json`:

- **`--font-sans`** = `-apple-system, BlinkMacSystemFont, var(--font-geist-sans), system-ui,
  "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
  - `-apple-system` / `BlinkMacSystemFont` → **San Francisco** on macOS / iOS / Safari (the native look).
  - `var(--font-geist-sans)` → **Geist**, self-hosted via `next/font` (the `geist` package set on
    `<html>` in `app/layout.tsx`) — the cross-platform fallback for non-Apple devices.
  - then the OS system stack as last resort.
- **`--font-mono`** = `var(--font-geist-mono), "JetBrains Mono", ui-monospace, SFMono-Regular,
  Menlo, Monaco, monospace` — code / inline-code only.

Applied document-wide via `font-sans` on `html, body` (`globals.css`). **This stack is frozen — do
not swap, reorder, or add web-font `@import`s in the app** (the preview bundle imports Geist from
Google Fonts only so it renders standalone; the app self-hosts).

### 10b. Semantic role table — the contract over existing utilities

Pick a role by intent; the role maps to a Tailwind utility + weight. New UI MUST use a role, not an
ad-hoc size. (Existing inline usage already conforms — no refactor required.)

| Semantic role | Utility (+ weight) | Size (16px root) | Line-height | Where it shows |
|---|---|---|---|---|
| **Display** | `text-2xl` | 1.625rem / 26px | 1.2 | empty-state hero (`chat-shell.tsx:560`) |
| **Heading 1** | `text-2xl font-semibold` | 1.625rem / 26px | 1.2 | markdown `h1` (`StreamingMarkdown.tsx:41`) |
| **Heading 2** | `text-xl font-semibold` | 1.375rem / 22px | 1.3 | markdown `h2` (`:42`); section headers in answers |
| **Heading 3** | `text-lg font-semibold` | 1.125rem / 18px | 1.5 | markdown `h3` (`:43`); dialog/sheet titles |
| **Title (UI)** | `text-base font-semibold` | 1rem / 16px | 1.6 | CardTitle (`card.tsx:46`) |
| **Body** | `text-base` | 1rem / 16px | 1.6 | the answer / markdown `p` |
| **Body Small** | `text-sm` | 0.875rem / 14px | 1.5 | tool I/O, task list, reasoning |
| **Label / Meta** | `text-xs font-medium` | 0.75rem / 12px | 1.4 | metadata, trace, step, badges |
| **Mono / Code** | `font-mono text-sm` | 0.875rem / 14px | normal | code blocks, inline code |

Source line-heights are the paired `--text-*--line-height` values from `type.tokens.json`
(`xs` 1.4 · `sm` 1.5 · `base` 1.6 · `lg` 1.5 · `xl` 1.3 · `2xl` 1.2). `text-*` utilities apply the
size **and** its paired line-height automatically (Tailwind v4 `@theme`).

### 10c. Rules

- **Emphasis = weight, not extra size.** Headings/titles → **semibold (600)**; secondary emphasis →
  **medium (500)**. **Never `bold` (700)** — unused by design.
- **Accent colour for links/CTAs only**, never body text. Links: `text-accent underline`.
- **One scale, all devices** — the type scale does not change per device (web / macOS / iOS share it).
- The **answer is uncarded Body prose**; tool/understanding output is carded Body Small.

---

## 11. Responsive screen variants (visual refs)

Existing export refs (reference only — values above are the contract):
`docs/design/native_wrap_ui_redesign/screens/`: `Mobile Chat.html`, `iPad Chat.html`,
`All Surfaces.html`. Frozen: `frozen/Mobile Chat.v12-type.html`, `frozen/iPad Chat.v12-type.html`.

- **Desktop (≥1024px):** two-pane (rail · groove · chat), content capped `max-w-3xl` centered.
- **iPad:** same two-pane above `lg`; below it, single column + Sheet rail.
- **Mobile (<1024px):** single chat column, hamburger → Sheet rail, safe-area composer padding live.

---

## 12. Deliberately NOT in this spec (deferred / not built)

- Right-hand `w-80` three-pane detail panel + bottom-Sheet reasoning panel — a real future feature,
  unbuilt (handbook §4). The app is two-pane.
- Pixel-exact screenshots / visual-regression baselines — out of scope; this spec drives DOM/CSS
  assertions, not pixel diffs.
