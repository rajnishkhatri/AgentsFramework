---
title: Native-wrap UI redesign — visual design spec
status: draft
created: 2026-06-22
owner: Rajnish Khatri
companion: native_wrap_ui_redesign.plan.md
preview: native_wrap_ui_redesign.visual.html
---

# Visual design spec — native-wrap UI redesign

Companion to [`native_wrap_ui_redesign.plan.md`](./native_wrap_ui_redesign.plan.md). This is the
**visual** half: current-state audit of the real frontend, the target desktop and phone layouts,
and the redesign deltas. Open `native_wrap_ui_redesign.visual.html` in a browser for the rendered
mockups; this markdown is the annotated spec the coding-agent handoff (plan §2.5d/e) reads.

> **Ground truth, not assumption.** Every "current state" claim below was read from the actual
> components on 2026-06-22 (`app/chat-shell.tsx`, `components/chat/SidebarPanel.tsx`,
> `components/chat/Composer.tsx`, `app/page.tsx`, `app/globals.css`).

## 1. Current-state audit (what exists today)

### Layout (from `app/chat-shell.tsx`)
- Root: `min-h-dvh grid grid-rows-[auto_1fr]` — a header row + a body row.
- **Header:** `ReAct Agent` title (left); eval badge + user email + sign-out link (right).
- **Body:** `grid lg:grid-cols-[auto_1fr]` — left `SidebarPanel` (`hidden lg:block`) + main column.
- **Main column:** `grid grid-rows-[1fr_auto]` — scrollable message area + composer.
  - Empty state: centered "What can I help you with?" (`text-2xl`).
  - Messages: `max-w-3xl mx-auto grid gap-4`.
  - User turn: `justify-self-end bg-accent text-white rounded-lg px-4 py-2 max-w-[80%]`.
  - Assistant turn: `justify-self-start max-w-[80%] w-full grid gap-1` — RunStatusLine
    (`aria-live`), streamed `StreamingMarkdown`, `ToolCard`s, reasoning `<details>`, RecallIndicator.
- **Right panel:** REMOVED in the UI refresh (chat-shell.tsx:418 comment). `MemoryPanel` now lives
  as a **tab inside the left rail** (`SidebarTabBar`: Chats | Memory).

### Sidebar (from `components/chat/SidebarPanel.tsx`)
- Width animates `w-64 ↔ w-12` (collapse), not the grid template.
- Affordances are **inline glyphs**, no icon set: `☰` (collapse), `🔍` (search), `+` (new chat).
- Rows: collapse toggle + `SidebarTabBar` · New chat · Search toggle/input · `ThreadSidebar` list.
- `prefers-reduced-motion` already respected (`motion-reduce:transition-none`).

### Composer (from `components/chat/Composer.tsx`)
- `<textarea>` with `field-sizing: content`, `min-h-[2.5rem] max-h-[12rem]` (~6 lines), `resize-y`.
- Enter submits; ⌘↩/Ctrl↩/Shift↩ = newline; IME-composition guard.
- Send button: `bg-accent text-white rounded-md px-4`, disabled when empty/busy.

### Tokens (from `app/globals.css`)
- `@theme`: `--color-bg/fg/muted/accent/accent-light/border/border-light/surface`,
  1.2 type scale with paired line-heights, Geist sans/mono, `--radius-sm/md`.
- Dark mode via `[data-theme="dark"]`.

### Identified gaps (the redesign targets)
| Gap | Evidence | Redesign delta |
|---|---|---|
| Mobile just **hides** the sidebar (no drawer) | `hidden lg:block` | sidebar → slide-in drawer (sheet) on phone |
| Right reasoning/tools area only as inline `<details>` | chat-shell turn render | desktop: collapsible right panel; phone: bottom sheet |
| **Glyph** affordances, inconsistent | `☰ 🔍 +` | a single icon set (Tabler-style) across affordances |
| Only **one primitive** (`ui/button.tsx`) | components/ui/ | shadcn primitive layer (plan §3) |
| No native chrome / safe-area | n/a | Tauri titlebar + drag region; iOS `env(safe-area-inset-*)` |
| Message actions absent | turn render | copy/regenerate (hover desktop, long-press mobile) |

## 2. Target — desktop (Tauri macOS window)

```
┌─ ⠿ titlebar (traffic-light inset · data-tauri-drag-region) ──────────────┐
│  ● ● ●                                                       user · ⚙   │
├──────────────┬───────────────────────────────┬───────────────────────────┤
│ ☰ Chats Mem  │            messages           │  REASONING / TOOLS        │
│ + New chat   │   ┌─ user bubble ───────────►  │  ▸ step 1 · plan          │
│ 🔍 Search    │   ◄ assistant answer          │  ▸ tool: search           │
│ Today        │     [copy] [regenerate]       │  ─────────                │
│ · thread one │                               │  TaskUnderstanding        │
│ · thread two │                               │  Recalled memory          │
│              ├───────────────────────────────┤  (collapsible →)          │
│              │ [ Send a message…       ] [↑] │                           │
└──────────────┴───────────────────────────────┴───────────────────────────┘
```

- **New:** custom titlebar with traffic-light inset + draggable region (`data-tauri-drag-region`).
- **New:** the reasoning/tools column **returns** as a collapsible right panel (desktop has room;
  it was folded away only because the old fixed column was cramped). Houses ToolCards,
  TaskUnderstandingCard, RecalledMemories — consolidating today's inline `<details>`.
- **New:** per-message actions (copy/regenerate) on hover, gated `@media (hover: hover)`.
- **Keep:** three-pane proportions, `max-w-3xl` answer column, the accent send affordance.

## 3. Target — phone (Capacitor iOS)

```
┌─ safe-area top (notch / Dynamic Island) ──┐
│ ☰        ReAct Agent              ⋯       │
├───────────────────────────────────────────┤
│              ┌─ user msg ─►                │
│   ◄ assistant answer (full width)         │
│     (long-press → actions)                │
│                                           │
├───────────────────────────────────────────┤
│ [ Message…                        ] ( ↑ ) │  ← pinned above keyboard
└─ safe-area bottom (home indicator) ───────┘
   ☰ → thread drawer (sheet)
   ⋯ → reasoning/tools bottom sheet
```

- **New:** `☰` opens the thread list as a slide-in **drawer** (sheet) — replaces today's
  hidden-on-mobile sidebar.
- **New:** `⋯` opens reasoning/tools as a **bottom sheet** (the desktop right panel's phone form).
- **New:** `env(safe-area-inset-*)` top + bottom; input bar pinned above keyboard
  (`@capacitor-community/safe-area`); round send button; **44pt** tap targets.
- **New:** long-press for message actions (no hover on touch).
- **Keep:** single-column message flow, user-bubble/assistant-full-width contrast.

## 4. Responsive rule (plan §5)

- **Viewport queries → page structure:** `lg:` shows the three-pane; below `lg`, collapse left rail
  to drawer and right panel to bottom sheet.
- **Container queries (`@container`) → component internals:** Composer, ToolCard,
  TaskUnderstandingCard adapt to their slot, so they render correctly in a wide Mac window and a
  narrow phone alike.

## 5. Token & component mapping (handoff contract)

The redesign **recomposes the existing component tree** — it does not rewrite it. Mapping for the
agent handoff:

| Current component | Redesign role | Notes |
|---|---|---|
| `SidebarPanel` | left rail (desktop) / drawer (phone) | same props; wrap in shadcn `sheet` on phone |
| `SidebarTabBar` | Chats \| Memory tabs | → shadcn `tabs` |
| `ThreadSidebar` | thread list | unchanged data; restyle rows |
| `Composer` | input bar | keep autosize/IME; round button on phone, pin above keyboard |
| `StreamingMarkdown` | answer body | keep streaming buffer; add `aria-live` per plan §6 |
| `ToolCard` / `TaskUnderstandingCard` / `RecalledMemories` | right panel (desktop) / bottom sheet (phone) | consolidate from inline `<details>` |
| `RunControls` / RunStatusLine | status + stop/regenerate | wire stop → `/api/run/cancel` |
| `ThemeToggle` | drive `[data-theme]` + `prefers-color-scheme` | keep |
| `ui/button.tsx` | reconcile into shadcn primitive set | plan §3 |

All visuals consume `@theme` tokens (plan §2) — **no hardcoded colors**. New icons replace the
`☰ 🔍 +` glyphs with one consistent set.

## 6. States to capture as Storybook stories (= the spec, plan §1)

idle / empty · connecting · thinking (step N) · using tools · writing (streaming) · complete ·
error · with-reasoning-expanded · with-recalled-memory · long-thread-scroll · drawer-open (phone) ·
bottom-sheet-open (phone) · collapsed-sidebar (desktop) · dark mode (each of the above).
