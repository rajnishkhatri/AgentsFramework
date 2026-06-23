# AgentsFramework Design Conventions

This file is read by the design agent before composing any screen or layout.
All designs MUST adhere to these constraints — they are not preferences, they are the contract.

## Token source

- Light tokens: `design/tokens/color.tokens.json`
- Dark tokens: `design/tokens/color.dark.tokens.json`
- Radius tokens: `design/tokens/radius.tokens.json`
- CSS bundle: `_ds_bundle/styles.css` (custom properties on `:root`, dark via `[data-theme="dark"]`)

Never hard-code hex values — always use `var(--color-*)` or `var(--radius-*)` tokens.

## §2.6 Cursor warm-neutral aesthetic (the design target)

Every screen MUST look like this:

- **Canvas**: warm off-white `var(--color-bg)` (#f9f7f5 light, #1f1e1d dark). Not cool-gray, not pure white.
- **One rationed accent**: `var(--color-accent)` (#c2704e light, #d98b6a dark) — terracotta. Used ONLY for the single primary CTA per screen. Everything else is neutral.
- **Hairline borders**: `var(--color-border)` (12% fg opacity). Dividers are a whisper, not a wall.
- **Recessed sidebar**: `var(--color-surface-sunken)` — one step darker than surface. The Cursor sidebar rail look.
- **Soft chrome**: radius-lg for cards/dialogs/sheets/message bubbles. Radius-md for inputs/buttons. Radius-sm for chips/badges.
- **Pill composer**: message input = rounded-lg textarea with hairline border, auto-grows with content.
- **No ambient shadows**: shadows only on floating/overlay elements (dialogs, sheets, dropdowns, toasts).

## Primitive library (14 components)

| Component | Group | Key usage |
|---|---|---|
| Button | Actions | Primary CTA (default), secondary (outline), icon-only (ghost+icon) |
| Badge | Actions | Status chips, eval labels, phase indicators |
| Input | Forms | Search, text fields |
| Textarea | Forms | Pill composer base, multi-line input |
| Card | Surfaces | Message bubble, panel, eval result card |
| Separator | Surfaces | Section dividers in sidebar + settings |
| Skeleton | Surfaces | Streaming placeholders (§6 streaming states) |
| ScrollArea | Surfaces | Message list, sidebar thread list |
| Tabs | Navigation | SidebarTabBar (Chats \| Memory) |
| Dialog | Overlays | Confirm modals, settings panel |
| Sheet | Overlays | Mobile thread-list drawer (left), reasoning panel (bottom) |
| DropdownMenu | Overlays | Per-message actions on desktop |
| Tooltip | Overlays | Desktop-only — gate with `@media (hover: hover)` |
| Toast | Feedback | Errors, cancel, run-complete notifications |

Source: `frontend/components/ui/*.tsx`. Use ONLY these — do not introduce new components without a PS1 extension cycle.

## Layout targets (plan §5)

1. **Desktop three-pane**: `[sidebar-sunken 260px] | [main-chat flex-1] | [detail-panel 320px collapsible]`
2. **Phone single-column**: sidebar hidden → left Sheet drawer on hamburger; detail panel → bottom Sheet; pill composer pinned to safe-area bottom.

## Component conventions

- Client-side React + Radix UI primitives.
- `asChild` prop on Button and Badge for polymorphic rendering.
- Animations respect `prefers-reduced-motion` via `motion-reduce:animate-none`.
- Safe-area padding (`env(safe-area-inset-*)`) applied at layout level, not inside primitives.
- Tooltip never renders on touch — gate at the call site.

## Sync metadata

- Project ID: `f8ce5c07-a053-4017-a4c0-b0602a2fc3e8`
- Sync method: manual (raw `mcp__claude_design__*` tools)
- Incremental anchor: `.design-sync/_ds_sync.json`
- Re-sync: edit `frontend/components/ui/`, update `ui_kits/agentsframework/`, finalize_plan + write_files.
