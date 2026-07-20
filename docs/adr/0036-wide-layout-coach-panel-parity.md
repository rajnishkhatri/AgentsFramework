---
type: decision-record
title: 'ADR-0036: Wide-layout CoachPanel parity — shell store, expandable list, coachMode + CoachDrawer'
status: accepted
created: 2026-07-16
updated: 2026-07-16
owner: Rajnish Khatri
related: preact-wide-layout-coach-panel.spec.md, preact-wide-layout-coach-panel.plan.md, PreACT-English-Coach-LOCKED-Spec.md
tags: [decision-record]
---

# ADR-0036: Wide-layout CoachPanel parity — shell store, expandable list, coachMode + CoachDrawer

**Status:** Accepted — 2026-07-16; **amended 2026-07-16** for Direction 2b lock
(supersedes the same-day draft decisions: 56px rail, session pin, Sheet drawer,
`use_collapsible_thread`). **PARTIALLY SUPERSEDED 2026-07-20 by
[ADR-0037](0037-coach-column-single-scroll-prototype.md)** — the coach-column
internal layout (FR-11 dual independent scroll, FR-12 pinned chip row, the Zone
A/B/C contract) is replaced by a single-scroll prototype column pinning only the
composer + action buttons. This ADR REMAINS canonical for everything else:
`coachMode` surface routing, `CoachDrawer`/`CoachTriggerPill`, the 64px rail,
`shell_layout_store`, iPhone fullscreen, and the a11y FRs (FR-1..10, 13..20),
which re-attach to the new column.
**Related:** [preact-wide-layout-coach-panel.spec.md](../plan/preact-wide-layout-coach-panel.spec.md),
[plan](../plan/preact-wide-layout-coach-panel.plan.md),
[tasks](../plan/preact-wide-layout-coach-panel.tasks.md),
locked artifacts under
[`docs/width-design-ui-session-artifacts/locked-spec-artifacts/`](../width-design-ui-session-artifacts/locked-spec-artifacts/).
**Audience:** anyone reconsidering desktop quiz+coach split gating, sidebar
collapse shape, or the coach overlay chrome.

---

## Context

The PreACT Direction **2b** locked spec requires desktop/iPad quiz+coach under
one content-width rule (`coachMode`), a **64px** icon rail on content screens
(no session pin), a hint-ladder + conversation coach column, and a dedicated
`CoachDrawer` + trigger pill when content width &lt; 900px. iPhone stays
fullscreen-only.

A same-day draft Stage 6 landed a partial approximation (56px rail,
`sidebarUserPinned`, Sheet + edge tab, bubble nudges, `use_collapsible_thread`).
The lock **supersedes** that draft where they disagree. Widening the live split
and the G1 abstractions remain Ask-first; this amendment records the revised
machinery.

---

## Decision

1. **Widen the live split** with `isWideSurface(s) = s !== "iphone"` /
   `useIsWide()` for nav helpers; **quiz layout decisions use**
   `coachMode(surface, viewportWidth, sidebarWidth)` →
   `fullscreen` | `inline` | `drawer` (900px content-width threshold;
   `RAIL_COLLAPSED = 64`, `RAIL_EXPANDED = 224`). Keep three Surface labels and
   `surfaceForWidth` unchanged for nav/focus semantics.
2. **Ship these frontend abstractions** (G1):
   - `shell_layout_store` — Home/Progress `localStorage["preact.shell.sidebar"]`
     + `panelDismissed` session key. **No** `sidebarUserPinned`. Content-screen
     collapse is layout-local (always mount collapsed).
   - `use_expandable_list` — one generic hook for ladder **and** conversation
     (replaces `use_collapsible_thread`).
   - `CollapsibleCoachAnswer` — presentational answer row (no timestamp).
   - `HintLadderList` — expandable hint ladder UI.
   - `CoachDrawer` + `CoachTriggerPill` — overlay chrome per lock §5 (not Sheet
     product chrome; may reuse in-tree focus-trap primitives).
3. **Collapsed sidebar = 64px icon rail** (38×38 circular items); content
   screens always mount collapsed; mid-session expand is in-memory only;
   Home/Progress alone persist preference.
4. **Inline dismiss** uses `panelDismissed`; thread stays in `coach_thread_store`
   (reachable via Coach nav). Drawer mode uses the floating pill, not an edge tab.
5. **Wide Feedback bridge** pins + focuses composer (inline) or opens drawer then
   focuses after transition; no route change. iPhone keeps navigate.

---

## Options considered & rejected

| Option | Why not |
|---|---|
| Keep `surface === "ipad"` gate; desktop stays panel-less | Contradicts locked wide-parity goal |
| Full-hide sidebar when collapsed | Traps ThemeToggle / nav |
| 56px rail + session user-pin | Superseded by lock §2.1 / FR-9 |
| Always-inline panel at every iPad width | Contradicts mid-width drawer lock |
| Navigate on wide Feedback ("Ask the coach") | Breaks in-place bridge |
| Keep Sheet as the product drawer | Lock §5/§9 require CoachDrawer + pill; Sheet path retired |
| Two hooks (`use_collapsible_thread` + ladder state) | Lock §8: one `use_expandable_list` |
| Props-only shell state with no Home/Progress persistence | Cannot satisfy Home/Progress preference |

---

## Rationale

`coachMode` is the smallest continuous rule that explains desktop inline, iPad
landscape inline (1024−64≥900), and iPad portrait drawer without a separate
orientation branch. The store/hook/component set is the least machinery that keeps
persistence, dual-list expand rules, and overlay a11y separately testable. The
lock’s dedicated drawer chrome is accepted over Sheet reuse because the product
contract (pill, dimensions, motion, focus return) is specific enough that wrapping
Sheet would still be a second surface API — better one named component.

---

## Consequences

- **Accepted:** desktop and iPad share live panel paths via `coachMode`; mid-width
  opens `CoachDrawer`; content screens always 64px rail; new/changed keys under
  `preact.shell.*` (pin key removed).
- **Accepted risk:** Safari `dvh` + nested `min-h-0` height chain — mitigated by
  L6 device spike before DoD; Home/Progress get explicit per-route scroll policy.
- **Follow-on:** Stage 3 L-track tasks + Stage 4 analyze → `sdd-implement`;
  retire Sheet/edge-tab/`use_collapsible_thread`/56px code paths; locked-spec
  folder remains Related, not OKF home.
- **Out of scope:** iPhone chrome redesign beyond FR-18, backend/engine, new npm deps.

---

## Supersedes / related

Amends (does not renumber) the 2026-07-16 draft of this same ADR. Does not
supersede prior ADRs. Extends the coach UI surface established by ADR-0025
(Coach surface VM) with shell/layout physics only — no wire/protocol change to
ADR-0012. Lightweight note: [`decisions.md`](decisions.md) (Direction 2b
supersession).
