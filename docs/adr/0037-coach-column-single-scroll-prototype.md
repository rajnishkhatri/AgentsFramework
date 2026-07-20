---
type: decision-record
title: 'ADR-0037: Coach column = single-scroll prototype layout; pin only composer + action buttons (supersedes ADR-0036 zone contract)'
status: proposed
created: 2026-07-20
updated: 2026-07-20
owner: Rajnish Khatri
related: 0036-wide-layout-coach-panel-parity.md, preact-wide-layout-coach-panel.spec.md, commit-first-coach.visual-gap-register.md, gen2-proto-handoff/03-ears-spec-gen2-coach-v3.md
tags: [decision-record]
---

# ADR-0037: Coach column = single-scroll prototype layout; pin only composer + action buttons

**Status:** Proposed — 2026-07-20. **Supersedes ADR-0036** on the coach-column
internal layout only (FR-11, FR-12, and the Direction-2b Zone A/B/C contract).
Retains ADR-0036's surface-routing machinery (`coachMode`, `CoachDrawer`,
`CoachTriggerPill`, 64px rail, `shell_layout_store`, iPhone fullscreen route) —
re-hosted around the new column, not deleted.
**Related:** [ADR-0036](0036-wide-layout-coach-panel-parity.md) · [wide-layout spec](../plan/preact-wide-layout-coach-panel.spec.md) · [visual gap register M7](../plan/commit-first-coach.visual-gap-register.md) · [v3 prototype EARS](../plan/gen2-proto-handoff/03-ears-spec-gen2-coach-v3.md)
**Audience:** anyone reconsidering the coach panel's scroll structure, the
composer/chip pinning, or the Zone A/B/C model.

---

## Context

ADR-0036 (Direction 2b lock) gave the coach panel a **three-zone** internal
structure: Zone A fixed header, Zone B the single vertical scroll (ladder rail +
conversation), Zone C a **pinned footer** holding the "One more nudge" control,
the quick-action chip row, and the composer (FR-12 / Q-C1). It also required the
item column and coach log to scroll independently with no window scroll (FR-11).

In practice on the live build (measured against the running app, `coach-panel-inline`
399×672 desktop panel, M7 in the visual gap register), that structure produces a
**"scroll within scroll"** the human flagged as unacceptable:

- **Two horizontal-scroll strips clip their content.** The mode-chip row
  (`coach-modes`) scrolls `scrollWidth 489 > clientWidth 323` — its 3rd chip
  ("Misconception summary") is clipped mid-word. The pinned quick-action row
  (`coach-chips`) scrolls `540 > 367` — its last chip is clipped. Both are a
  by-product of packing a too-wide row into a fixed-width zone.
- **Fixed chrome starves the transcript.** Zone A (188px) + Zone C (256px) =
  **444 of the 672px** panel is fixed; the conversation (Zone B) is crushed into
  a **226px** window, so the transcript scrolls inside a sliver between two
  clipping chip strips.

ADR-0036 itself flagged the underlying "Safari `dvh` + nested `min-h-0` height
chain" as an **accepted risk pending an L6 device spike before DoD** — the crushed
transcript is that deferred risk coming due. The v3 prototype
([03-ears-spec-gen2-coach-v3.md](../plan/gen2-proto-handoff/03-ears-spec-gen2-coach-v3.md))
does not have this problem: its coach column is a single scrolling column with a
flat inline mode indicator and a light pinned composer. (Caveat: the prototype is
**desktop-only** — PKG-3, "min-width 1280 layout; no mobile/iPad variant" — so it
never specified the responsive drawer, iPhone route, or focus-trap a11y that
ADR-0036 added. Those are ADR-0036's contributions, not the prototype's.)

The human reviewed both readings (P1 refine-within-lock vs P2 adopt-prototype) and
chose **P2: revert the coach-column layout to the prototype**, then further scoped
the pinned region to **only the composer + action buttons** — everything else
scrolls.

---

## Decision

**Replace the coach column's internal structure with the prototype's single-scroll
flat column**, and **pin only the bottom action region** — the composer
(text entry) plus the actionable buttons (the wrong-pick loop controls: "Let me
try again" / "Show me more →" / "Walk me through it", and the send affordance).

Concretely:

1. **One scroll region for the column body.** The mode indicator, the
   PUMP/HINT/PROMPT ladder rail, the conversation/transcript, **and the
   quick-action chips** ("Explain the rule simply", …) all live in a single
   vertically-scrolling region. No zone scrolls horizontally; there is no separate
   Zone A / Zone B split for scroll purposes.
2. **Pin only composer + action buttons.** A single pinned bottom region holds the
   composer and the current-state action buttons. The quick-action chips are
   **not** pinned (that pinning is what forced their H-scroll under FR-12).
3. **Flatten the mode indicator.** Replace the horizontally-scrolling mode-chip
   row with the prototype's flat, non-scrolling mode presentation (no clipped
   chip). The always-inert "Misconception summary" chip is dropped (it never
   activated — M1 in the register).
4. **Retain surface routing, re-host the column.** `coachMode` (inline / drawer /
   fullscreen), `CoachDrawer` + `CoachTriggerPill`, the 64px rail, and the iPhone
   fullscreen route stay — they now wrap the **new** single-scroll column. The
   focus-trap, reduced-motion, streaming-force-expand, and error-expand a11y
   guarantees (ADR-0036 FR-2/3/4/7/8) re-attach to the new column; they are
   re-verified, not dropped.

This **supersedes ADR-0036's FR-11, FR-12, and the Zone A/B/C contract**; all
other ADR-0036 requirements (FR-1..10, 13..20) survive, some re-expressed against
the new column in the spec revision.

---

## Options considered & rejected

| Option | Why not |
|---|---|
| **P1 — refine within ADR-0036** (de-scroll chips + rebalance zone heights + close the `min-h-0` spike; no supersession) | Keeps the three-zone model and the pinned chip row. Fixes the clip but leaves a tall fixed footer still eating transcript height; the human judged the whole zone model, not just its overflow, to be the problem. |
| **Full literal prototype adoption — desktop-only, drop responsive** | The prototype is PKG-3 desktop-only; taking it literally deletes the working drawer, iPhone-fullscreen, and iPad paths ADR-0036 built. Regresses solved responsive/a11y behavior to fix a scroll bug. Rejected. |
| **Keep chips pinned but wrap to multiple lines** | Least change, but a multi-line pinned footer is *taller*, starving the transcript further — the opposite of the goal. |
| **Everything scrolls, nothing pinned (prototype-literal footer)** | The composer can scroll out of view on a long transcript; the learner loses the always-reachable text entry. The human explicitly chose to keep the bottom action region pinned. |
| **This decision — single-scroll body + pin only composer/actions, retain routing** | Kills both H-scroll strips and returns the transcript's vertical real estate, keeps the composer always reachable, and preserves the responsive/a11y machinery by re-hosting rather than deleting it. |

---

## Rationale

The measured defects all trace to one cause: **fixed-width, fixed-height zones
packing content that doesn't fit.** Collapsing the body to one scroll region
removes the horizontal overflow entirely (a scrolling column is width-constrained
but its rows wrap/stack, not clip) and gives the transcript the height the fixed
footer was taking. Pinning **only** the composer + actions is the minimum pin that
keeps the two things a learner must always reach (type to the coach; act on the
current state) visible, without a heavy footer. The quick-action chips are
convenience shortcuts, not must-reach controls, so scrolling them with the body is
the right trade.

Retaining `coachMode`/drawer/rail/iPhone routing is deliberate: those solve a
different problem (which surface hosts the coach at which width) that the prototype
never addressed. Reverting them would re-open solved, tested problems to fix a
layout bug — so the ADR reverts the **column internals** and re-hosts them.

---

## Consequences

- **Accepted:** FR-11, FR-12, and the Zone A/B/C contract are superseded. The
  spec revision re-derives the coach column's structure and re-maps the surviving
  a11y FRs onto the new single-scroll column.
- **Accepted:** the quick-action chips now scroll away with the transcript rather
  than staying pinned — a deliberate downgrade of their reachability in exchange
  for killing the H-scroll clip and reclaiming transcript height.
- **Accepted risk:** re-hosting the new column inside the drawer + iPhone
  fullscreen must re-verify the focus-trap, reduced-motion, and streaming-expand
  guarantees against the new DOM — covered by re-running the ADR-0036 e2e/RTL
  tests that assert them (they are not deleted; they retarget the new column).
- **Follow-on:** spec revision of `preact-wide-layout-coach-panel.spec.md`
  (supersede FR-11/12 + Zone contract; add single-scroll + no-H-scroll +
  transcript-min-height layout-invariant FRs), then Phase-4 implementation tasks
  in `commit-first-coach.tasks.md`. G8: any ADR-0036 test whose assertion the new
  layout invalidates (e.g. "Zone C tops unchanged on log scroll") is rewritten
  with a justification, not silently weakened.
- **Out of scope:** the coach's live-LLM wiring (M2 in the register — separate
  deploy/config concern); engine/backend; new npm deps; the item column's own
  layout.

---

## Supersedes / related

Supersedes **ADR-0036** on the coach-column internal layout (FR-11, FR-12, Zone
A/B/C contract) only; ADR-0036 remains canonical for `coachMode` surface routing,
`CoachDrawer`/`CoachTriggerPill`, the 64px rail, `shell_layout_store`, and iPhone
fullscreen. Adopts the coach-column structure from the v3 prototype
([03-ears-spec-gen2-coach-v3.md](../plan/gen2-proto-handoff/03-ears-spec-gen2-coach-v3.md),
PKG-3 desktop-only — responsive hosting is this repo's addition). Diagnosis and
measurements in [commit-first-coach.visual-gap-register.md](../plan/commit-first-coach.visual-gap-register.md)
(M7). Realizes the revised [preact-wide-layout-coach-panel.spec.md](../plan/preact-wide-layout-coach-panel.spec.md).
