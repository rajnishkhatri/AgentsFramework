---
type: plan
title: 'UI — Left Panel Refresh & Right Panel Removal'
description: 'grid lg:grid-cols-auto_1fr_auto → left ThreadSidebar · center chat ·'
tags: [plan]
---

# UI — Left Panel Refresh & Right Panel Removal

> **Status:** IMPLEMENTED (2026-06-19). All phases 0–5 landed; 751 frontend
> unit tests + 86 architecture tests + the new sidebar e2e suite (8 specs) +
> a11y sweep all green; typecheck clean. Front-end only; no backend/wire changes.
> **Companion:** [`ui_left_panel_refresh.design.md`](ui_left_panel_refresh.design.md)
> — visual layouts (before/after, panel states), component tree, the collapse
> animation spec, and the `data-testid` test contract.
> **Origin:** Manual UI review of the live chat shell screenshot. Two reference
> points: (1) the current `ChatShell` three-column layout, (2) Claude desktop's
> left rail (top tab bar → New chat → Projects/Artifacts → Recents).
> **One-line:** Drop the right "What I remember" column, and turn the left rail
> into a real navigation panel — top tab bar (Chat only for now), a **New chat**
> button, an inline **Search** over Recents, the **Recents** list, and a
> show/hide collapse with animation.
> **Owner:** frontend (me). **Validation:** Playwright (unit `.test.tsx` +
> `e2e/*.spec.ts`), reusing the existing `data-testid` conventions.
> **Constraint:** Reuse the existing architecture seams. Panels stay dumb
> (F-R1) — `useChatSidebars` / a new `useSidebarChrome` hook own all state; the
> theme tokens in `globals.css` are the only color source (no new palette, no
> new dependency, no icon library — inline SVG/unicode like `✎ ✕ ✓` today).

---

## 1. Current state (verified)

- **Layout** lives in `frontend/app/chat-shell.tsx`. Body is
  `grid lg:grid-cols-[auto_1fr_auto]` → **left `ThreadSidebar`** · center chat ·
  **right `MemoryPanel`** (chat-shell.tsx:345, :420). A full-width header sits
  above (`grid-rows-[auto_1fr]`).
- **Left rail** = `frontend/components/chat/ThreadSidebar.tsx`: a `<nav
  aria-label="Chat history">`, threads grouped Today / Yesterday / Previous 7
  days / Older via the pure `groupThreadsByTime`. Per-row rename/delete on
  hover. **No** New-chat button, **no** search, **no** tab bar, **no** collapse.
- **Right rail** = `frontend/components/memory/MemoryPanel.tsx` ("What I
  remember" / "Memory off" / "Add something to remember…"). This is the panel
  we are removing from the chat layout.
- **State seam** = `frontend/components/chat/use_chat_sidebars.ts`
  (`useChatSidebars`) owns threads + memory list/mutation lifecycle. `ChatShell`
  only renders and forwards callbacks (F-R1).
- **New chat is already cheap:** `useAgentRun` lazily mints a `threadId` via
  `crypto.randomUUID()` on first `send` (use_agent_run.ts:181). A "New chat" is
  therefore a **client reset** (clear turns + drop the thread-id ref), not a
  mandatory BFF round-trip — `POST /api/threads` exists
  (`app/api/threads/route.ts:18`) but creation can stay lazy.
- **Tests already probe for these affordances and skip today.**
  `e2e/thread-sidebar.spec.ts` looks for `[data-testid='new-thread']`,
  `button:has-text('New chat')`, and `nav[aria-label='Threads']` — all currently
  absent, so those assertions `test.skip`. This plan makes them pass.
- **No icon dependency** (`lucide` etc. not installed). Keep the inline-glyph
  convention. **CopilotKit** is a dependency (`@copilotkit/react-ui`) but the
  shell is hand-built; we are **not** adopting `<CopilotSidebar>` — see §6.

---

## 2. Target layout

```
┌───────────────────────────────────────────────────────────────┐
│ Header:  ReAct Agent            user@…   [Dark]   Sign out     │  ← unchanged
├──────────────┬────────────────────────────────────────────────┤
│ ☰  [Chat]    │                                                 │  ← NEW tab bar + collapse toggle
│ + New chat   │                                                 │
│ 🔍 Search    │              chat column (now 1fr,              │
│ ─ Search box─│               wider — right column gone)        │
│ RECENTS      │                                                 │
│  Today       │                                                 │
│   • Thread…  │                                                 │
│  Yesterday   │                                                 │
│   • Thread…  │                                                 │
└──────────────┴────────────────────────────────────────────────┘
```

Body grid changes from `lg:grid-cols-[auto_1fr_auto]` to
**`lg:grid-cols-[auto_1fr]`** (right column deleted). When the left panel is
collapsed, the column animates to a thin rail showing only the `☰` toggle, and
the chat column reclaims the width.

---

## 3. Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Right "What I remember" panel | **Hide from chat layout, keep the code.** Remove `MemoryPanel` from `ChatShell`'s render + drop the right grid column. Leave `MemoryPanel.tsx` and the memory half of `useChatSidebars` (`memories`, `addMemory`, `deleteMemory`, `memoryEnabled`) intact and tested — reversible, backend untouched, `/api/memory` routes keep a consumer in tests. |
| D2 | Search behavior | **Inline client-side filter of Recents.** The Search button reveals a text input that filters the already-loaded thread list by title (case-insensitive substring). No new BFF route. |
| D3 | New chat | **Client reset** (clear turns, drop thread-id ref, clear active selection). Lazy thread creation stays as-is. |
| D4 | Tab bar | **Chat tab only**, rendered as a tab group so adding Cowork/Code later is a data change, not a rewrite. Chat is `aria-selected`/active; the structure is the deliverable, not extra tabs. |
| D5 | Collapse | Header-level `☰` toggle + persisted state. Width transition animated via CSS `grid-template-columns` / `transform`, honoring `prefers-reduced-motion`. |
| D6 | State ownership | A new `useSidebarChrome` hook owns chrome state (collapsed, searchOpen, searchQuery, activeTab). Thread data stays in `useChatSidebars`. New-chat reset needs a new `startNewChat` on `useAgentRun`. |

---

## 4. Phases

### Phase 0 — Remove the right panel (smallest, unblocks width)
- In `chat-shell.tsx`: delete the right `<div className="hidden lg:grid …">
  <MemoryPanel … /></div>` block (chat-shell.tsx:420-428) and change the body
  grid to `grid lg:grid-cols-[auto_1fr]`.
- Remove the now-unused `MemoryPanel` / `RecallIndicator`-for-panel imports **if**
  they become unused (RecallIndicator is also used inline per-turn at
  chat-shell.tsx:383 — **keep that**; only the panel import goes).
- Leave `useChatSidebars` memory fields untouched (D1). `MemoryPanel.tsx` and its
  test stay on disk.
- **Test:** update/relax `chat-shell.test.tsx` so it no longer asserts the memory
  panel renders in the shell; assert it is **absent**.

### Phase 1 — Sidebar chrome hook + collapse (animated show/hide)
- New `frontend/components/chat/use_sidebar_chrome.ts` exposing
  `{ collapsed, toggleCollapsed, searchOpen, toggleSearch, searchQuery,
  setSearchQuery, activeTab, setActiveTab }`. `collapsed` persisted to
  `localStorage` (key `sidebar:collapsed`), SSR-safe (default expanded; read in
  an effect to avoid hydration mismatch — mirror `ThemeToggle`'s `mounted`
  guard).
- New `frontend/components/chat/SidebarPanel.tsx` — the **chrome wrapper** that
  composes: collapse toggle, `TabBar`, `New chat`, `Search`, then the existing
  `ThreadSidebar` (passed as children / props). `ThreadSidebar` stays the pure
  list renderer; the wrapper owns the new affordances. This preserves F-R1 (dumb
  leaf list, chrome holds the new state via the hook).
- **Animation:** wrap the column so width animates. Use a CSS transition on the
  grid (`transition-[grid-template-columns]` is unreliable cross-browser →
  instead animate the **panel's own width / translate**: expanded `w-64`,
  collapsed `w-12`, `transition-[width] duration-200 ease-out`, content fades
  with `opacity`/`transition-opacity`). Guard with
  `motion-reduce:transition-none`.
- Collapsed state: show only the `☰` toggle (and optionally a `+` mini New-chat);
  `aria-expanded` on the toggle, `aria-hidden` on the collapsed content.
- **Tests:**
  - `use_sidebar_chrome.test.ts` — pure hook: toggle flips, persistence round-trip
    (inject a fake storage), search query setter.
  - `SidebarPanel.test.tsx` — collapse toggle changes `aria-expanded`; content
    hidden when collapsed.
  - `e2e` collapse spec — click `[data-testid='sidebar-toggle']`, assert the
    panel width/aria changes and the chat column is still usable.

### Phase 2 — Top tab bar (Chat only)
- `frontend/components/chat/SidebarTabBar.tsx`: a `role="tablist"` with one
  `role="tab"` (Chat, `aria-selected="true"`). Data-driven from a
  `const TABS = [{ id: "chat", label: "Chat" }]` so future tabs are additive.
- `data-testid="sidebar-tab-chat"`. Inactive/future tabs render disabled when
  added; for now only Chat exists.
- **Test:** `SidebarTabBar.test.tsx` — renders the Chat tab, it is selected,
  `tablist`/`tab` roles present (a11y).

### Phase 3 — New chat button
- Button in `SidebarPanel`: `data-testid="new-thread"` (matches the existing
  `e2e/thread-sidebar.spec.ts` selector) + visible text `+ New chat`.
- Add `startNewChat()` to `useAgentRun` (clears `turns`, resets
  `threadIdRef.current = null`, clears paused/edit state). `ChatShell` wires the
  button → `startNewChat()` **and** clears `activeThreadId` (so no Recents row
  shows `aria-current`).
- Creation stays lazy (D3); we do **not** POST on click. (The existing E2E test's
  POST assertion is `test.skip`-guarded "if not wired", so lazy creation does not
  fail it — but document this so the test's skip branch is intentional.)
- **Tests:**
  - `use_agent_run.test.ts` — `startNewChat` empties turns + nulls the thread id;
    a subsequent `send` mints a **fresh** id.
  - `chat-shell.test.tsx` — clicking New chat returns the empty-state hero ("What
    can I help you with?") and clears the active thread highlight.

### Phase 4 — Inline search over Recents
- Search toggle button `data-testid="sidebar-search-toggle"` (glyph `🔍` /
  inline SVG) → reveals an `<input data-testid="sidebar-search-input"
  aria-label="Search conversations">` bound to `searchQuery` from the chrome
  hook.
- Filtering is **pure**: add `filterThreadsByTitle(threads, query)` to
  `frontend/lib/thread_grouping.ts` (sibling of `groupThreadsByTime`), then group
  the filtered result. Case-insensitive substring on `title`. Empty query → all.
- Pass the filtered list into `ThreadSidebar`. When the filter yields nothing,
  `ThreadSidebar` already renders its empty state — add a distinct
  `data-testid="thread-search-empty"` message ("No conversations match.") vs the
  existing `thread-empty` ("No conversations yet.").
- **Tests:**
  - `thread_grouping.test.ts` — extend with `filterThreadsByTitle` cases
    (match/no-match/empty-query/case-insensitive).
  - `e2e` search spec — type a query, assert only matching rows show; clear →
    all return; no-match shows the search-empty message.

### Phase 5 — Polish & a11y sweep
- Keyboard: toggle/search/new-chat reachable by Tab, Enter/Space activate;
  search input `Escape` closes + clears (chrome hook).
- `prefers-reduced-motion` verified on collapse animation.
- Run `@axe-core/playwright` (already a devDep) against the shell to confirm no
  new a11y violations from the tab/collapse roles.

---

## 5. File-by-file change map

| File | Change |
|------|--------|
| `frontend/app/chat-shell.tsx` | Remove right column + `MemoryPanel`; body grid → `lg:grid-cols-[auto_1fr]`; render `SidebarPanel` (wrapping `ThreadSidebar`) instead of bare `ThreadSidebar`; wire New-chat → `startNewChat` + clear active thread; pass `searchQuery`-filtered threads. |
| `frontend/components/chat/use_sidebar_chrome.ts` | **NEW** — chrome state hook (collapsed/search/tab) + localStorage persistence. |
| `frontend/components/chat/SidebarPanel.tsx` | **NEW** — chrome wrapper: collapse toggle, `SidebarTabBar`, New chat, Search input, then `ThreadSidebar`. |
| `frontend/components/chat/SidebarTabBar.tsx` | **NEW** — tablist with the Chat tab. |
| `frontend/components/chat/ThreadSidebar.tsx` | Accept already-filtered threads (no internal filtering); add `thread-search-empty` empty-state variant via a prop (`emptyVariant`/`isFiltered`). Keep `aria-label`; **add** `aria-label="Threads"` alias OR keep "Chat history" (the e2e selector accepts `[data-testid='thread-sidebar']`, so no rename needed — leave label, rely on testid). |
| `frontend/components/chat/use_agent_run.ts` | Add `startNewChat()` to the returned API. |
| `frontend/lib/thread_grouping.ts` | Add pure `filterThreadsByTitle`. |
| `frontend/components/memory/MemoryPanel.tsx` | **Untouched** (kept per D1). |
| Tests | New: `use_sidebar_chrome.test.ts`, `SidebarPanel.test.tsx`, `SidebarTabBar.test.tsx`. Extended: `thread_grouping.test.ts`, `use_agent_run.test.ts`, `chat-shell.test.tsx`. E2E: extend `e2e/thread-sidebar.spec.ts` (collapse + search + new-chat now real, drop the skips). |

---

## 6. CopilotKit review (why we keep building custom)

`@copilotkit/react-ui` ships `<CopilotSidebar>` / `<CopilotChat>`, but:
- The shell already implements streaming, trace chips, eval-mode freeze,
  understanding-edit, recall indicators, and the run-view reducer — none of which
  CopilotKit's prebuilt sidebar exposes. Swapping it in would **lose** those.
- CopilotKit's sidebar is a *chat* drawer, not a *navigation* rail; it doesn't
  give us the tab-bar/Recents/search layout we want.
- **What we borrow (patterns, not code):** the collapsible-rail interaction model
  and the "header actions row above a scrollable list" structure. Implemented
  with our own tokens/components to stay consistent and dependency-light.

Net: **no CopilotKit components adopted in this plan.** Revisit only if we later
want their generative-UI action rendering — orthogonal to this layout work.

---

## 7. Validation plan (Playwright)

**Unit (`*.test.tsx`, jsdom):** hook logic (collapse/persist/search/startNewChat),
each new component's roles + testids, the pure `filterThreadsByTitle`.

**E2E (`frontend/e2e/*.spec.ts`, mocked `/api/threads`):** extend the existing
`thread-sidebar.spec.ts` (its `new-thread`/sidebar selectors already match our
testids) and add:
- `sidebar collapse` — toggle hides/shows, `aria-expanded` flips, chat stays
  usable, reduced-motion path renders.
- `sidebar search` — filter narrows Recents, clear restores, no-match message.
- `new chat` — empties the transcript to the hero, clears active highlight.

Run via the repo's `agentsframework-playwright` skill commands; **chromium-only
smoke locally** (per the "T1 tier too slow" guidance — never the full 5-browser
matrix locally), full matrix in CI.

**Acceptance:** right panel gone; left panel collapses with animation; tab bar
(Chat) + New chat + Search + Recents all present and wired; all new + existing
unit and chromium e2e specs green; no new axe violations.

---

## 8. Out of scope / follow-ups

- Additional tabs (Cowork/Code) — structure is ready (D4); content is a separate
  effort.
- Command-palette (⌘K) search overlay — D2 chose inline filter; the palette is a
  future upgrade.
- Surfacing memory behind a settings route now that it's off the chat layout —
  follow-up (`/settings/memory`), the code is retained for it.
- Server-side thread search / pagination of Recents — current scope filters only
  the already-loaded list.
