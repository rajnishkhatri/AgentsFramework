# PreACT English Coach — Wide-Layout & Coach-Panel Parity

**Implementation spec (SDD / EARS) — for a coding agent.**
Derived 1:1 from the UX Decision Record (`English Coach - Wide Layout UX Decision.dc.html`).
Surface: the `(coach)` route group at `/learn/*`. Frontend only — shell + quiz + coach UI.

---

## 0. Intent & guardrails

Bring the **desktop** surface to parity with the iPad-landscape quiz+coach split, add a
**collapsible left nav**, and make the **coach column stay usable as conversations grow**
(scroll only the log, pin the affordances, collapse old answers).

**Do NOT** change: backend/engine, coach LLM behavior, hint-rung pedagogy, the item/hint bank,
auth/WorkOS, iPhone tab bar / focus mode. **No new npm dependencies.** Preserve: one shared coach
thread (panel ↔ `/learn/coach`), the reviewed hint ladder, non-reveal nudges.

Success = all acceptance criteria in §7 pass, existing quiz/coach tests stay green, and the
iPhone surface is byte-for-byte unchanged.

---

## 1. Core seam — `isWide`

The split, the collapsible sidebar, and the coach-column physics all key off one derived predicate.

- **File:** `frontend/components/shell/use_surface.ts`
- Add a pure helper next to `surfaceForWidth`:
  ```ts
  /** Wide = the quiz+coach split surface (desktop or iPad landscape). */
  export function isWideSurface(s: Surface): boolean { return s !== "iphone"; }
  export function useIsWide(): boolean { return isWideSurface(useSurface()); }
  ```
- Keep the three `Surface` labels (`iphone`/`ipad`/`desktop`) and `surfaceForWidth` **unchanged** —
  nav membership and focus-screen semantics still depend on them (Decision **A1**).
- Add a **content-width** helper for the degrade ladder (Decision **A2**):
  ```ts
  export const SPLIT_MIN_CONTENT_WIDTH = 900; // px of space left after the sidebar
  ```

---

## 2. Shell — sidebar collapse + height chain

**File:** `frontend/app/(coach)/learn/layout.tsx` (`CoachShell`).

### 2.1 Height chain (physics prerequisite — Decisions C1, E3)

The window must not scroll on wide surfaces; each region owns its own scroll. Establish an unbroken
chain **viewport → shell → main → split row → column → scroll region**:

- Root shell wrapper: `h-dvh` (not `min-h-dvh`) + `flex`, `overflow-hidden`.
- `<main>`: `min-h-0 min-w-0 flex-1 overflow-hidden` (drop `overflow-y-auto` on wide; keep the
  current scroll on iPhone).
- Every intermediate flex child that must cede height carries `min-h-0`.
- Actual scrolling happens only on: the quiz item column, the coach log (Zone B), and (iPhone) `main`.

> **Risk (spike first):** `100dvh` + nested `min-h-0` + `overflow-y-auto` on iOS Safari. Validate on
> a real device before locking. See §8.

### 2.2 Sidebar collapse (Decisions B1–B5, F1)

- "Collapsed" = a **56px icon rail**, never a full hide. Expanded stays `w-56`.
- Render the rail vs full list in `AppNav` (§3); the shell owns the width + toggle.
- **Auto-collapse** on entering a **content-heavy** screen — `quiz`, `coach`, `skill`, `test` — unless
  the user explicitly expanded this session. `dashboard` and `progress` stay expanded (**B1/B2**).
- **Toggle:** a `SidebarToggle` chevron button at the rail top; `aria-label` "Expand sidebar" /
  "Collapse sidebar"; global `[` keydown toggles it (ignore when focus is in an input/textarea).
- **ThemeToggle** moves to the **rail bottom** as an icon-only control so it is reachable in both
  states (**B4**) — never trapped.
- Motion: `transition: width 180ms ease-out`; under `prefers-reduced-motion: reduce`, no transition (**F1**).

### 2.3 State source

Read/write sidebar + panel state from a new module store (§5.1), hydrated from storage. On a
content-screen mount, apply the auto-collapse rule (write `collapsed=true` unless `userPinned`).

---

## 3. `AppNav` — icon-rail variant

**File:** `frontend/components/shell/AppNav.tsx`.

- Add a `collapsed?: boolean` prop (desktop/iPad only; ignored for the iPhone tab bar).
- **Collapsed:** render each item as an icon-only `<Link>` (or disabled `<span>`), `min-h-11 min-w-11`,
  centered, with a hover/focus **tooltip** showing the label, and the existing
  `data-[active=true]` treatment (**B3**). Keep `aria-current`, `data-screen`, and the FR-B5
  coming-soon `<span>` mechanism intact.
- **Expanded:** unchanged from today.
- Icons: use the existing icon set already in the app; do not add an icon dependency. If no icon
  exists for a screen, use its first initial in a rounded square (no emoji).
- Touch targets ≥44px in the rail (`min-h-11`).

---

## 4. Quiz split + coach column

### 4.1 `quiz/page.tsx` — gate the split on `isWide`

**File:** `frontend/app/(coach)/learn/quiz/page.tsx`.

- Replace `surface === "ipad"` gating of `coachRuntime` / `CoachPanel` with `useIsWide()` (**A1/A8**).
  Build `coachRuntime` whenever wide; keep it `null` on iPhone.
- Wrap the split row in the height-locked container:
  ```
  <div className="flex min-h-0 flex-1 items-stretch gap-6">
    <div className="min-w-0 flex-1 overflow-y-auto"> {framed} </div>   {/* item column scrolls */}
    <CoachPanel … />                                                   {/* Zone B scrolls */}
  </div>
  ```
  Both columns scroll independently; the window does not (**E3/AC-9**).
- **Panel dismiss (A3/AC-13):** when `panelDismissed`, replace `CoachPanel` with a thin, full-height
  edge tab (`aria-label="Show coach"`) that clears the flag. Dismissing preserves the thread
  (it lives in `coach_thread_store`).
- **Degrade ladder (A2/AC-1,2):** compute available content width (viewport − open-sidebar width).
  - `< 900` and sidebar expanded → force sidebar to the icon rail first.
  - `< 900` and sidebar already collapsed → hide the inline panel; show a "Coach" button that opens
    the panel as an **overlay drawer** (focus-trapped, returns focus to the trigger on close).
  - **Never** stack the coach below the item.
- **Feedback bridge (E1/AC-14):** on wide, drop the `router.push(screen("coach").route)` in
  `onAskCoach`; instead pin the item context (`setCoachPin`) and focus the panel composer
  (imperative focus via a ref/callback passed to `CoachPanel`). Keep the navigate on iPhone.

### 4.2 `CoachPanel.tsx` — 3-zone model

**File:** `frontend/components/coach/CoachPanel.tsx`. Restructure the `<aside>` into three zones
(Decision **C1**), keeping `useCoach`/ladder-as-props (F-R1):

```
<aside class="flex min-h-0 flex-col …">            width: clamp(340px,32%,460px) desktop / w-80 iPad (F3)
  ── Zone A · FIXED ──  CoachChrome (title, status, current-item line, mode pills)
  ── Zone B · SCROLL ── role="log" aria-live="polite"; flex-1 min-h-0 overflow-y-auto
        opener → revealed nudge bodies (as coach-style bubbles, tagged "Nudge N") → turns
  ── Zone C · PINNED ── [One more nudge] + CoachChips + Composer   (shrink-0)
</aside>
```

- **Move revealed nudge bodies INTO Zone B** (Decision **C3**) — render them as coach bubbles inside
  the log, not as a growing block above it. This is the fix for the height-competition problem.
- **Pin** the "One more nudge" button, chip row, and composer in Zone C (**C4**); they never scroll (**AC-10**).
- Exhausted ladder → disable "One more nudge" with its explanatory title; composer stays put (**AC-5**).
- Panel width: `style={{ width: "clamp(340px,32%,460px)" }}` on desktop, `w-80`/≈360px on iPad (**F3**);
  add `min-w-0` and wrap/break on markdown so long tokens don't overflow (see §8).
- Add an `onComposerFocusRef` (or imperative handle) so the Feedback bridge can focus the composer.

### 4.3 `CoachView.tsx` — collapsible answers

**File:** `frontend/components/coach/CoachView.tsx`.

- Keep the `role="log" aria-live="polite"` scroll region and the `Composer` sibling (already pinned).
- Render each turn through the new `CollapsibleCoachAnswer` (§4.5). **User question bubbles always
  stay visible** (Decision **D3**); only the coach answer body collapses.
- Expanded set comes from `use_collapsible_thread` (§4.6).

### 4.4 `CoachWorkspace.tsx` + `CoachChrome.tsx` — same zones, surface chrome only

**Files:** `frontend/components/coach/CoachWorkspace.tsx`, `CoachChrome.tsx`.

- Apply the **same** Zone B/C physics (Decision **C2/C5**): fixed chrome, scroll log, pinned
  chips+composer, height chain.
  - **Desktop `rail`:** fixed Back/Wrap-up header + fixed left context rail + right column
    (scroll log over pinned chips+composer).
  - **iPad `strip`:** identical, chrome is a top strip instead of a left rail.
- **No "One more nudge"** on standalone (no per-item ladder off quiz). Keep the history line.
- `CoachChrome`: cold-state copy (Decision **E2**) — status "Ready when you are", omit the
  current-item line when no pin; **no layout change** between warm/cold.

### 4.5 NEW — `CollapsibleCoachAnswer.tsx` (presentational)

**File:** `frontend/components/coach/CollapsibleCoachAnswer.tsx`. The only substantial new component.

- Props: `{ turn: CoachTurn; expanded: boolean; onToggle(): void; onRetry?(): void }`.
- **Collapsed (Decision D1):** one summary row — "Coach" label + first sentence (truncated, ellipsis)
  + relative timestamp + chevron `▸`. Whole row is a `<button aria-expanded={false} aria-controls={bodyId}>`.
- **Expanded:** the full `StreamingMarkdown` body (current bubble markup) with chevron `▾`.
- **Force-expanded & non-collapsible** while `coach.pending` (streaming) or `coach.error` (**D4/AC-3,4**);
  the Retry control lives in the expanded body and stays reachable.
- **a11y (D5/AC-7):** collapsed body uses `hidden` (removed from AX tree). Toggling does **not** move
  focus and does **not** write to the live region. Newest turn stays expanded so streamed tokens still
  announce.

### 4.6 NEW — `use_collapsible_thread.ts` (pure hook)

**File:** `frontend/components/coach/use_collapsible_thread.ts`. Node-testable like the existing
reducer seams (F-R1).

- Input: `turns`. Output: `{ isExpanded(id): boolean; toggle(id): void }`.
- Rules (Decision **D2**): when a reply **completes**, all prior **non-error** answers collapse; the
  newest stays expanded; streaming stays expanded. A **manual** toggle is stored per-turn in
  `manualTurnOverride` and always wins.
- Derivation order per turn: `pending || error` → expanded (forced) ; else `manualOverride` if set ;
  else `id === newestCompletedId` → expanded ; else collapsed.

---

## 5. State model (all client; no backend, no new library)

### 5.1 NEW — `shell_layout_store.ts`

**File:** `frontend/components/shell/shell_layout_store.ts`. Mirror the existing
`coach_thread_store` module-store + `useSyncExternalStore` pattern (no new dep).

| State | Type | Persistence | Notes |
|---|---|---|---|
| `sidebarCollapsed` | `boolean` | `localStorage["preact.shell.sidebar"]` (`"expanded"\|"collapsed"`) | default expanded; survives reload |
| `sidebarUserPinned` | `boolean` | `sessionStorage["preact.shell.sidebarPinned"]` | set on explicit expand; blocks auto-collapse this session |
| `panelDismissed` | `boolean` | `sessionStorage["preact.shell.panelDismissed"]` | per session, wide only |

**Precedence (B5):** on entering a content screen, auto-collapse writes `collapsed` **unless**
`sidebarUserPinned` is set this session.

### 5.2 Existing / ephemeral

| State | Type | Lives in | Persistence |
|---|---|---|---|
| `revealed` (nudge #) | `number` | `CoachPanel` local (exists) | none — resets per item (keyed by question id) |
| `expandedTurnIds` | derived `Set<id>` | `use_collapsible_thread` | none — re-derived on reload (newest expanded) |
| `manualTurnOverride` | `Map<id,state>` | `use_collapsible_thread` | none |
| thread · pin · mode | store snapshot | `coach_thread_store` (exists) | unchanged |

---

## 6. Component inventory (fewest new abstractions)

**Changed:** `learn/layout.tsx`, `shell/AppNav.tsx`, `shell/use_surface.ts`, `quiz/page.tsx`,
`coach/CoachPanel.tsx`, `coach/CoachView.tsx`, `coach/CoachWorkspace.tsx`, `coach/CoachChrome.tsx`,
`feedback/FeedbackView.tsx` (Ask-coach bridge on wide only).

**New:** `coach/CollapsibleCoachAnswer.tsx` (presentational), `coach/use_collapsible_thread.ts`
(pure hook), `shell/SidebarToggle.tsx` (tiny; may fold into `AppNav`),
`shell/shell_layout_store.ts` (module store).

**Not a component:** the height-chain is a className contract (`h-dvh` + `min-h-0` + `overflow-y-auto`
on Zone B) — document it, don't abstract it.

---

## 7. Acceptance criteria (EARS)

**Failure & edge paths first.**

- **AC-1** — IF content width is below 900px, THEN THE SYSTEM SHALL collapse the sidebar to the icon
  rail before hiding the coach panel, and shall never stack the coach below the quiz item.
- **AC-2** — IF content width stays below 900px with the sidebar already collapsed, THEN THE SYSTEM
  SHALL hide the inline panel and present a "Coach" control that opens it as an overlay drawer without
  navigating away.
- **AC-3** — WHILE a coach reply is streaming, THE SYSTEM SHALL keep that turn expanded and prevent it
  from being collapsed, manually or automatically.
- **AC-4** — IF a coach turn is in an error state, THEN THE SYSTEM SHALL keep it expanded and its Retry
  control reachable, excluding it from auto-collapse.
- **AC-5** — WHEN the last available ladder rung has been revealed, THE SYSTEM SHALL disable "One more
  nudge" with an explanation and shall not hide or displace the composer.
- **AC-6** — WHILE the sidebar is collapsed, THE SYSTEM SHALL keep the theme toggle reachable within the
  icon rail.
- **AC-7** — WHEN the learner collapses or expands a coach answer, THE SYSTEM SHALL not move keyboard
  focus and shall not re-announce prior content through the live region.

**Nominal behavior.**

- **AC-8** — WHERE the surface is wide (desktop or iPad), THE SYSTEM SHALL render the quiz item and the
  live coach panel side-by-side sharing one coach thread.
- **AC-9** — WHILE on a wide Quiz surface, THE SYSTEM SHALL scroll the item column and the coach log
  independently and shall not scroll the browser window.
- **AC-10** — THE SYSTEM SHALL keep the composer, chip row, and "One more nudge" control pinned and
  visible regardless of coach-log scroll position.
- **AC-11** — WHEN a new coach reply completes, THE SYSTEM SHALL collapse all prior non-error coach
  answers and keep the newest expanded.
- **AC-12** — WHEN the learner enters a content screen (Quiz / Coach / Skill / Test), THE SYSTEM SHALL
  auto-collapse the sidebar unless the learner explicitly expanded it this session; Home and Progress
  shall stay expanded.
- **AC-13** — WHEN the learner dismisses the coach panel on wide Quiz, THE SYSTEM SHALL preserve the
  coach thread and keep it reachable from the Coach nav item.
- **AC-14** — WHEN the learner activates "Ask the coach about this" on wide Feedback, THE SYSTEM SHALL
  pin the item context and move focus to the coach composer without navigating.
- **AC-15** — WHERE prefers-reduced-motion is set, THE SYSTEM SHALL apply sidebar and answer collapse
  changes instantly, with no transition; otherwise the sidebar preference persists across reloads via
  localStorage.

---

## 8. Open risks (spike before / during)

1. **Height chain on mobile/iPad Safari** — `100dvh` toolbar behavior + nested `min-h-0` flex +
   `overflow-y-auto` can collapse the scroll region. **Device-test before committing.**
2. **Pinned composer inside an overflow/transform ancestor** — `position: sticky` can fail; prefer a
   flex bottom cluster (`shrink-0` sibling of the `flex-1` scroll region). Verify with long content.
3. **Nested / dual-column scroll chaining** — add `overscroll-behavior: contain` to Zone B, the item
   column, and the drawer.
4. **Auto-collapse × aria-live** — confirm no double announcement across browsers/SRs; confirm `hidden`
   removes bodies from the AX tree without breaking `role="log"` semantics.
5. **Drawer focus trap + return focus** at the narrow width (a11y).
6. **Panel width vs long tokens** — `min-w-0` + word-break on coach markdown so URLs/code don't overflow
   the clamped panel.

---

## 9. Test plan

- **Unit (node, no React):** `use_collapsible_thread` derivation table (streaming, error, newest,
  manual override, completion→collapse-prior); `isWideSurface`; storage precedence in
  `shell_layout_store`.
- **Component:** `CollapsibleCoachAnswer` (collapsed summary content, `aria-expanded`/`aria-controls`,
  force-expand on pending/error); `AppNav` collapsed rail (tooltips, active state, ≥44px, FR-B5 span);
  `CoachPanel` zone structure + pinned cluster.
- **E2E (Playwright, desktop + iPad viewports; iPhone unchanged as regression):** AC-1,2 degrade
  ladder; AC-3,4 streaming/error stay expanded; AC-6 theme reachable when collapsed; AC-9 window does
  not scroll; AC-11 auto-collapse on completion; AC-12 per-screen collapse rule; AC-13 dismiss keeps
  thread; AC-14 Feedback focus bridge (no route change). Assert the iPhone quiz/coach snapshots are
  identical to `main`.
- **a11y:** extend the existing axe pass to the collapsed rail + collapsed answers + drawer.

---

## 10. Non-goals

iPhone tab bar & focus-mode chrome; question/hint bank content; hint-rung pedagogy; the non-reveal
guarantee; coach LLM behavior/prompts/mode semantics; auth/WorkOS; backend/engine; any new npm
dependency; Dashboard/Summary/Skill/Progress/Test screen internals (only their shell chrome + sidebar
behavior change); theme tokens/palette.
