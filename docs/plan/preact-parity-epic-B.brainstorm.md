---
type: brainstorm
title: 'Epic B — Coach surface build-out (C-2…C-7 · F-6 · F-4)'
status: 'Stage-1 CLOSED (2026-07-09) — gate: chrome=D1+D6; modes=D5a; feedback=D2; stream=D3 slip-capable; chips=onAsk seeds; ladder=B1→B2→B3 (+B0 docs)'
authored: 2026-07-09
---

# Brainstorm — Epic B Coach surface build-out

> **SDD Stage-1 artifact** (`brainstorm`). Premise audit + directions for Epic B
> ([sprint board](preact-parity-sprint-board-B.md)). Contains **no code**.
>
> **Status:** Stage-1 CLOSED — 2026-07-09 · **Owner:** Rajnish Khatri
> **Related:**
> - Board: [`preact-parity-sprint-board-B.md`](preact-parity-sprint-board-B.md)
> - Epics: [`preact-parity-epics.md`](preact-parity-epics.md)
> - Report: [`preact-ui-prototype-parity-VISUAL-gap-report.md`](preact-ui-prototype-parity-VISUAL-gap-report.md)
> - Prior epic pattern: [`preact-parity-epic-A.brainstorm.md`](preact-parity-epic-A.brainstorm.md)
> - Advance → B1: `preact-parity-B1-coach-chrome.spec.md` *(forthcoming)*

---

## 1. Intent (restated)

Turn `/learn/coach` from a title+composer shell into the prototype's **coaching
workspace**, and close the desktop Feedback→Coach bridge. Findings in scope:
`C-2…C-7` (rail, current-item, history trust line, mode surface, conversation,
chips) plus `F-6` / `F-4` (Ask-the-coach on desktop Feedback + green-span recap).

The deliverable after this gate is a **sprint board** whose sprints are each
independently testable, mergeable to `main`, and releasable alone — chrome
before live stream if the agent path is not ready.

---

## 2. Premise audit

Every load-bearing premise checked against the working tree (2026-07-09).
Canonical finding IDs are from the **VISUAL** gap report (not the superseded
gap-matrix, which renumbered Coach rows).

| # | Premise | Status | Evidence |
|---|---|---|---|
| P1 | `/learn/coach` is title + composer/log only (empty chrome) | **verified** | [page.tsx:28-36](../../frontend/app/(coach)/learn/coach/page.tsx); [CoachView.tsx:51-80](../../frontend/components/coach/CoachView.tsx) — log + `Composer`, no rail/modes/chips |
| P2 | Stream plumbing already exists (hook + BFF + mocked E2E) | **verified** | [use_coach.ts](../../frontend/components/coach/use_coach.ts); [route.ts](../../frontend/app/api/coach/run/stream/route.ts); [coach-mocked.spec.ts:22-53](../../frontend/e2e/learn/coach-mocked.spec.ts) |
| P3 | C-2…C-5, C-7 UI chrome is absent on standalone | **verified** | VISUAL report §4; no rail/history/modes/chips in `CoachView` / page |
| P4 | Derived coach mode exists server-side | **verified** | [coach_context_sanitizer.ts:20,28-31](../../frontend/lib/translators/coach_context_sanitizer.ts) — `pre_submit` \| `post_feedback` |
| P5 | Prototype/UI-spec "3 coach modes" == code's 2 derived modes | **refuted** | Prototype C-5: *In-drill Socratic / Post-answer deep-dive / Misconception summary* (3 selectable). Code: **2** marker-derived modes; client `mode` is **advisory and never trusted** (ADR-0012 / sanitizer header). A free learner switcher would fight the contract. |
| P6 | `askCoachContext` is ready for F-6 | **partial** | Built in [use_feedback.ts:19-23,46-49](../../frontend/components/feedback/use_feedback.ts); **never consumed** by `FeedbackView` or quiz page actions |
| P7 | "Ask the coach" exists on desktop Feedback | **refuted** | [quiz/page.tsx:64-69,294-302](../../frontend/app/(coach)/learn/quiz/page.tsx) — `coachRuntime` only when `surface === "ipad"`; Feedback actions are Next/Finish only |
| P8 | F-4 green-span recap is optional polish | **refuted** | UI [FR-E1](preact-english-coach-ui.spec.md) already requires sentence recap with success-colored span; [feedback_vm.ts:31-42](../../frontend/lib/translators/feedback_vm.ts) has no recap field |
| P9 | History line can ship with placeholder "3 of last 5" | **refuted** (trust) | Epic B gate + AP-6 honesty: no fabricated counts. Port exists: [attempt_repo.ts:40](../../frontend/lib/ports/engine/attempt_repo.ts) `misses()` — used by Dashboard, **not** coach |
| P10 | Client already sends `coach_context` / `misses_aggregate` | **refuted** | Scout: run body is messages-only; formatter ready in Python when context arrives |
| P11 | C-6 "empty" means stream route missing | **refuted** | Route + middleware coach graph exist; empty = no seed + no context payload + chrome gap. Live persona often mocked in E2E |
| P12 | Coach surface / rail VM already exists | **refuted** | Only [coach_message_vm.ts](../../frontend/lib/translators/coach_message_vm.ts) (bubbles). Design still TO-BUILD for rail regions |
| P13 | iPad `CoachPanel` already has full chrome | **refuted** | [CoachPanel.tsx:55-59](../../frontend/components/coach/CoachPanel.tsx) — mini-header "Socratic mode · watching this item" only; reuses bare `CoachView` |
| P14 | Epics' B1/B2/B3 split is still the right releasability cut | **verified (as hypothesis)** | Chrome vs Feedback bridge vs live stream touch different seams; B3 alone needs backend reachability |

**Corrected framing after audit (P5/P8/P9/P11 re-pose):**

1. **C-5 is not "wire a free 3-way switcher."** It is: *surface the authoritative
   derived mode honestly*, and separately decide whether the third prototype
   "Misconception summary" mode is (a) display copy over `post_feedback`,
   (b) a new derived mode requiring an ADR amendment to ADR-0012, or (c)
   deferred. A clickable switcher that overrides the marker store is out of
   bounds without an ADR.
2. **F-4 is a FR-E1 gap**, not optional polish — pairs with F-6 but is
   independently shippable on Feedback alone.
3. **C-4 history line is a trust signal** — real `AttemptRepo.misses()` (or
   honestly absent), never placeholder copy.
4. **C-6 is not "build the stream."** Stream exists. C-6 work is seed/opener +
   `coach_context` assembly + (optionally) live reachability — and can slip
   without blocking chrome.

**D0 (blocking hygiene)?** No live "present but lies" control in Epic B scope
comparable to Epic A's `Q-6`. Closest: FR-E5 mandates Ask-the-coach and desktop
lacks it (**absent**, not lying). Treat as B2 scope, not a docs-only D0.
Stale gap-matrix ID drift is a docs note for the board, not a blocker.

---

## 3. Directions (six)

### High-probability (follow existing repo patterns)

- **D1 — Chrome-first workspace (B1)** *(implementation lead for coach screen)* —
  Add a coach **surface VM** + presentational rail/header/chips on
  `/learn/coach` (and optionally shared into `CoachPanel`): C-2 rail, C-3
  current-item (honest absent when no item), C-4 history from `misses()` or
  absent, C-5 **derived-mode display** (not free switcher), C-7 chips as
  composer prefixes that call existing `onAsk`. Pattern: Dashboard
  `use_dashboard` → translator → view; keep SDK in `lib/adapters/`.
  **Stresses:** G1 new abstraction (surface VM) → likely ADR; trust honesty on C-4.
  **Releasable alone:** yes — RTL/fixture tests; no live agent.

- **D2 — Feedback bridge + recap (B2)** — Wire FR-E5 "Ask the coach" on desktop
  Feedback using existing `askCoachContext`; add F-4 green-span recap to
  `FeedbackVM` / `FeedbackView` per FR-E1/FR-A7. Pattern: `buildFeedback` already
  returns context; quiz page only needs an action + navigation into coach with
  item pinned. **Releasable alone:** yes — independent of B1 chrome completeness
  (bridge can land on today's thin Coach page).

- **D3 — Live context + conversation depth (B3)** — Assemble client
  `coach_context` (incl. `misses_aggregate` when data exists), optional seeded
  opener, prove stream with real or mocked backend. Pattern: ADR-0012 BFF
  sanitizer already waits for context bodies. **`gated-on-data` / backend
  reachability** — may defer without blocking B1/B2. **Releasable alone:** yes
  if chrome already honest; else ship behind feature flag / mocked E2E only.

### Exploratory (different abstraction / demand-side / class-level)

- **D4 — Demand-side chips (local first)** — Quick-reply chips resolve to
  **deterministic local replies** (or composer-fill only) when stream is down;
  live agent is fallback. Mirrors router/guardrail cascade: expensive call not
  required for chrome demo. Prototype E2E already expects chip→reply routing.
  **Tradeoff:** risks a second "canned coach" personality vs live Socratic agent;
  keep chips as **message seeds** (fill composer / `onAsk`) unless product wants
  offline coaching. **What breaks:** if chips invent history-aware answers →
  trust bug class of C-4.

- **D5 — Mode taxonomy ADR (class over instance)** — Explicitly decide the
  3-prototype vs 2-derived mismatch in an ADR amending or sitting beside
  ADR-0012: (a) **display-only** mapping of 3 labels onto 2 modes, (b) add a
  third derived mode with a new marker/signal, (c) drop third mode from UI
  parity. **Do regardless of chrome pick** if C-5 ships — otherwise C-5 will
  re-litigate mid-sprint. **Ask-first:** yes if (b).

- **D6 — Shared CoachChrome across standalone + iPad panel** — Extract chrome
  so `CoachPanel` and `/learn/coach` share one rail/mode/chips surface (class
  fix for "standalone empty, panel thinner"). Pattern: presentational leaf +
  props from page/panel hooks. **Tradeoff:** larger B1 blast radius; iPad layout
  constraints. **What breaks:** shipping standalone-only chrome recreates the
  dual-surface drift Epic B is meant to close.

- **D7 — Under-used signals first (minimal B2)** *(orthogonal track)* —
  Smallest ship: consume `askCoachContext` + enable desktop Ask-the-coach
  **without** green-span or full rail. Uses signal already computed and wasted.
  Can be a thin B2a if B2 is too fat; F-4 stays B2b.

---

## 4. Hypotheses for leading direction (D1 + D2 parallel)

| H | Claim | Result |
|---|---|---|
| H1 | Stream route need not block chrome | **validated** — P2/P11; epics doc already splits B3 |
| H2 | C-5 free switcher would violate ADR-0012 | **validated** — sanitizer: client mode advisory; marker derives mode |
| H3 | `AttemptRepo.misses()` can feed C-4 without new engine port | **validated** — port + Dashboard usage; coach hook just doesn't call it yet |
| H4 | F-6 is mostly wiring, not new data | **validated** — P6 `askCoachContext` already built |
| H5 | F-4 needs FeedbackVM field + markup (FR-E1) | **validated** — P8; quiz already has `contextHtml` on item VM |
| H6 | B1/B2/B3 are parallelizable with zero shared merge conflict | **rejected as "trivial"** — B2 navigation may want C-3 current-item slot from B1; prefer **B1 then B2** or B2 with "item via query/store" interim. B3 after B1 so history line and aggregate share one assembly |
| H7 | New coach surface VM triggers ADR | **likely validated** — epics gate; G1; no existing rail VM (P12) |

---

## 5. Dependency map (before naming a lead)

```
do-regardless (hygiene):
  • Record C-5 mode-taxonomy decision (D5) in decisions.md or ADR before C-5 UI
  • C-4 honesty rule (real or absent) — non-negotiable

capability tracks (pick priority):
  B-chrome (D1 ± D6) ──┬──► B-stream (D3)   [B3 needs chrome honesty + context assembly]
  B-feedback (D2 ± D7) ─┘   [independent of B3; weakly wants B1 for current-item pin]

deferred behind epic exit:
  • Full offline canned coach (D4 beyond composer-fill)
  • Third derived mode (D5 option b) unless chosen now
```

**Engineering vs calendar:** B1/B2 are engineering-bound. B3's load-bearing cost
may be **calendar** (live middleware/auth in the environment used for sign-off)
even if code is small — keep B3 slip-capable.

---

## 6. Gate decision (binding on sprint board + sdd-spec)

**CLOSED 2026-07-09** — user confirmed the suggested binding.

| Axis | Choice | Id |
|---|---|---|
| Chrome | Shared CoachChrome across standalone + iPad panel | **D1+D6** |
| Modes | Display-only map of 3 prototype labels → 2 derived modes | **D5a** |
| Feedback | Ask-the-coach desktop + green-span recap | **D2** |
| Stream | In-epic last; may slip without blocking B1/B2 | **D3** |
| Chips | Composer-fill / `onAsk` seeds only (no local canned coach) | **onAsk** |
| Ladder | Docs hygiene → chrome → feedback → stream | **B0 → B1 → B2 → B3** |

**Deferred behind Epic B exit:** D4 (offline canned replies), D5b (third derived mode), D7 (split F-6/F-4).

Advance → **sprint board** [`preact-parity-sprint-board-B.md`](preact-parity-sprint-board-B.md), then
**sdd-spec** for B1 (`preact-parity-B1-coach-chrome.spec.md`).
