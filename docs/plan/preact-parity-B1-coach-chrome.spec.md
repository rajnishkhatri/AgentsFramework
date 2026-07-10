---
title: 'Sprint B1 — Coach chrome (shared standalone + iPad) · Spec'
type: spec
status: Accepted
date: 2026-07-09
owner: Rajnish Khatri
epic: B
derives_from:
  - docs/plan/preact-parity-sprint-board-B.md
  - docs/plan/preact-parity-epic-B.brainstorm.md
related:
  - docs/plan/preact-parity-B1-coach-chrome.plan.md    # plan + tasks
  - docs/plan/preact-parity-epics.md
  - docs/plan/preact-english-coach-ui.spec.md           # FR-F1 (rail / modes / chips)
  - docs/adr/0012-subject-coach-context-contract-hint-ladder.md  # client mode advisory
  - docs/adr/0025-coach-surface-vm.md                  # G1 surface VM (Proposed → ratify at implement)
  - docs/adr/decisions.md                              # B0 D5a + C-4 honesty (co-land)
  - PreAct/UI-Design/English Coach - Screens.dc.html   # C-2…C-5 / C-7 visual anchors
governs:
  - frontend/app/(coach)/learn/coach/page.tsx
  - frontend/components/coach/CoachView.tsx
  - frontend/components/coach/CoachPanel.tsx
  - frontend/components/coach/CoachChrome.tsx           # forthcoming
  - frontend/lib/translators/coach_surface_vm.ts       # forthcoming (T1)
  - docs/adr/0025-coach-surface-vm.md
---

# Sprint B1 — Coach chrome (shared standalone + iPad)

> **What / why split.** This spec is the *what*. Intent debt for the new coach
> **surface VM** lands in [ADR-0025](../adr/0025-coach-surface-vm.md) (G1 / ⚠️ Ask first).
> Mode taxonomy (**D5a**) and C-4 honesty land in `decisions.md` as **B0** (docs-only;
> co-lands with B1). Direction chosen at Stage-1 gate:
> [`preact-parity-epic-B.brainstorm.md`](preact-parity-epic-B.brainstorm.md) →
> **D1+D6** + **D5a**; chips = `onAsk` seeds.

**Status:** Accepted — 2026-07-09 · clarify C1–C5 locked · plan:
[`preact-parity-B1-coach-chrome.plan.md`](preact-parity-B1-coach-chrome.plan.md).
Do not implement until Stage-4 analyze is green and the human gates plan → tasks.

---

## 1. Goal

Turn `/learn/coach` and the iPad `CoachPanel` from a title+composer / mini-header
shell into the prototype's **coaching workspace chrome**: context rail, current-item
line, honest history trust line, display-only mode surface, and quick-reply chips —
shared so the two surfaces do not drift. Stream depth and Feedback→Coach navigation
stay out of scope (B3 / B2).

## 2. Context

- **Findings:** `C-2` rail · `C-3` current-item · `C-4` history trust line · `C-5`
  mode surface · `C-7` chips ([VISUAL report](preact-ui-prototype-parity-VISUAL-gap-report.md) §4).
- **Today:** [page.tsx](../../frontend/app/(coach)/learn/coach/page.tsx) = title +
  `CoachView`; [CoachView.tsx](../../frontend/components/coach/CoachView.tsx) = log +
  `Composer` only; [CoachPanel.tsx](../../frontend/components/coach/CoachPanel.tsx) =
  copy-only mini-header ("Socratic mode · watching this item") + bare `CoachView`.
  No `CoachChrome` / rail / chips components exist.
- **Mode contract (ADR-0012):** runtime has **two** marker-derived modes
  (`pre_submit` \| `post_feedback`); client-sent `mode` is advisory and never trusted
  ([coach_context_sanitizer.ts](../../frontend/lib/translators/coach_context_sanitizer.ts)).
  Prototype shows **three** labels — B1 ships **D5a** display-only mapping, not a
  free switcher.
- **History honesty (AP-6):** C-4 is a trust signal — real `AttemptRepo.misses()`
  aggregate **or honestly absent**; never placeholder "3 of last 5".
- **Pattern to mirror:** Dashboard `use_dashboard` → T1 translators → presentational
  view. Bubble projection stays in `coach_message_vm.ts` (unchanged; B3 owns stream
  depth).
- **B0 prerequisite:** D5a + C-4 honesty are **not yet** in `decisions.md`. B1
  co-lands B0 as docs-first tasks (same pattern as A0/A1).

### 2.1 Clarify (locked 2026-07-09)

| # | Ambiguity | Recommended default | Status |
|---|---|---|---|
| C1 | C-4 aggregate shape when misses exist | **Skill-scoped count when a current item (with `skillId`) is pinned**; copy like `Sees your history: N misses on this skill` (or skill name). **No fabricated window** ("of last 5") unless a real window is computed. When no pin or misses load fails → honest absent (omit line or explicit empty copy — not fake counts). | **accepted** |
| C2 | Standalone `/learn/coach` current-item pin before B2 | **Honest absent on standalone**; iPad panel receives item label props from quiz page. B1 defines the chrome **slot + VM fields**; B2 fills the pin via Ask-the-coach. | **accepted** |
| C3 | Surface VM vs props bag | **New T1 `coach_surface_vm.ts` + numbered ADR** (G1). Views take a `CoachSurfaceVM`; hooks/pages assemble inputs. | **accepted** |
| C4 | Misconception label under D5a | **Three labels always rendered**; exactly one marked active from derived mode. Map: In-drill Socratic → `pre_submit`; Post-answer deep-dive → `post_feedback` (primary); Misconception summary → also `post_feedback` but **not independently selectable** — visually secondary / inactive unless we later add D5b. Prefer: deep-dive active when `post_feedback`; misconception never "active" alone in B1. | **accepted** |
| C5 | Chip activation | **Immediate `onAsk(seed)`** (matches UI FR-F2 chip → send). Not composer-fill-only. Busy → chips non-actionable. | **accepted** |

---

## 3. Functional requirements (EARS)

Failure paths first.

- **FR-1** (failure-path / trust · C-4). IF misses data is unavailable OR no honest
  aggregate can be derived THEN THE SYSTEM SHALL omit fabricated history counts and
  SHALL render an honest absent state for the history line (no placeholder "3 of last
  5", no invented denominators).
- **FR-2** (failure-path / mode · C-5 / D5a). THE SYSTEM SHALL NOT let the learner
  override the marker-derived coach mode. Mode UI is display-only; activating a
  non-authoritative label SHALL NOT change derived mode, run-body `mode`, or BFF
  sanitizer behavior (ADR-0012 holds).
- **FR-3** (failure-path / current-item · C-3). IF no item is pinned THEN THE SYSTEM
  SHALL render an honest absent state for the current-item line (no fake "Q4 · …").
- **FR-4** (C-2). THE SYSTEM SHALL render shared coach chrome that includes a context
  rail / header region conveying "Your Coach" and an adaptive / always-on status
  affordance consistent with the prototype rail intent (UI FR-F1 header+rail).
- **FR-5** (C-3). WHEN an item is pinned (label + optional skill/question identity
  supplied by the host) THE SYSTEM SHALL show a current-item line in the shared chrome.
- **FR-6** (C-4). WHEN an honest misses aggregate is available THE SYSTEM SHALL show a
  history-awareness line derived only from real `AttemptRepo.misses()` (and host-supplied
  skill scope per clarify C1) — never from hardcoded demo counts.
- **FR-7** (C-5 / D5a). THE SYSTEM SHALL surface three prototype mode labels (In-drill
  Socratic / Post-answer deep-dive / Misconception summary) with exactly one
  authoritative active state driven by `deriveCoachMode` (or an equivalent host-supplied
  derived `CoachMode`), per clarify C4 mapping.
- **FR-8** (C-7). WHEN the learner activates a quick-reply chip THE SYSTEM SHALL seed
  the coach turn via the existing `onAsk` path (clarify C5); chips SHALL NOT invent
  local canned coach replies.
- **FR-9** (D6). THE SYSTEM SHALL extract shared presentational chrome used by both
  `/learn/coach` and `CoachPanel` so the two surfaces do not maintain divergent rail /
  mode / chip markup.
- **FR-10** (B0 docs). THE SYSTEM SHALL record in `docs/adr/decisions.md` (newest-first):
  **D5a** display-only 3→2 mode map (cite ADR-0012 + sanitizer); **C-4** honesty rule
  (real misses or absent). Epics Epic B / VISUAL report C-5 framing SHALL no longer
  claim a free learner switcher.
- **FR-11** (G1 ADR). THE SYSTEM SHALL append a numbered ADR for the coach **surface VM**
  (new T1 abstraction): Context / Decision / Options / Rationale / Consequences; index +
  log entries per OKF.
- **FR-12.** THE SYSTEM SHALL prove FR-1…FR-9 with L1 tests that were **seen to fail
  first** (chrome structure, honest absent, display-only modes, chip→`onAsk`; fixture
  misses for C-4). No live agent required for B1 sign-off.

## 4. Data model / contracts

No trust-kernel / wire schema / pyproject changes. No change to ADR-0012 run-body
sanitizer contract (B3 owns `coach_context` assembly).

| Surface | Change |
|---|---|
| `CoachSurfaceVM` (new T1) | Pure view-model for rail / current-item / history / mode display / chip seeds. Inputs: derived `CoachMode`, optional pinned item, optional misses aggregate, static chip copy. |
| `coach_message_vm.ts` | **Unchanged** (bubbles only). |
| `CoachMode` / `deriveCoachMode` | **Reused**; display map is UI-only (D5a). |
| `AttemptRepo.misses` | **Reused** (no new engine port). Aggregate shape per clarify C1. |
| `CoachView` / `CoachPanel` / coach `page.tsx` | Compose shared chrome + existing log/composer; panel gains item-label props when quiz supplies them. |
| `decisions.md` | B0 entries (FR-10). |
| Numbered ADR | Surface VM (FR-11). |

**Out of scope contracts:** Feedback `askCoachContext` consumption (B2); client
`coach_context` / `misses_aggregate` on the run body (B3); third derived mode (D5b).

## 5. Invariants & security boundaries

- **Frontend F-R1:** chrome views presentational — render `CoachSurfaceVM` + callbacks;
  no engine I/O in the leaf.
- **T1:** `coach_surface_vm` imports `wire/` (and existing coach types) only; pure; no
  React / SDK.
- **F-R2:** SDK stays in `lib/adapters/`; B1 does not add SDK imports to components.
- **ADR-0012:** display mode never trusted into sanitizer; no client override path.
- **Architecture invariants #1–#8:** frontend-only; no new service / graph node /
  upward import.
- **⚠️ Ask first / G1:** new surface VM → **ADR required** (FR-11).
- **AP-6 / trust:** C-4 never fabricates counts (FR-1, FR-6).
- **G8:** adds tests; does not weaken existing coach assertions.

## 6. Edge cases

- **Misses `[]`:** honest empty / absent — not "0 of last 5" unless product copy
  explicitly wants a true zero from real data (prefer absent or "No recent misses"
  without a fake window).
- **Misses load error:** treat as unavailable → FR-1 absent (do not show stale demo).
- **Standalone with no pin:** C-3 absent; modes still show from derived default
  (`pre_submit` when no marker / no item).
- **iPad panel without new props (transitional):** keep honest absent for C-3 until
  quiz page passes label; do not hardcode "Q4".
- **Busy stream + chip:** chips non-actionable while `busy` (mirror composer).
- **Mode click:** no-op or non-button semantics (text/badge) — must not dispatch mode
  change (FR-2).
- **Chip copy:** static seeds only in B1; no history-aware chip text that claims
  misses the rail does not honestly show.

## 7. Non-functional requirements

- Deterministic L1 unit / RTL tests in the frontend vitest suite (`make check` path).
- No live LLM for B1 DoD. No new npm/py dependency.
- Reversible: shared chrome extract + VM + docs/ADR; stream behavior unchanged.
- Shared chrome must fit iPad panel width constraints (no desktop-only layout that
  breaks the split).

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | Surface VM / chrome — no history line (or absent copy) when aggregate missing; never renders placeholder "3 of last 5" | L1 | yes |
| FR-2 | Mode labels not buttons that change mode; derived mode drives `aria-current` / active class only | L1 | yes |
| FR-3 | No pin → current-item absent | L1 | yes |
| FR-4 | Rail / "Your Coach" region present on shared chrome | L1 | yes |
| FR-5 | Pin supplied → current-item line shows label | L1 | yes |
| FR-6 | Fixture misses → history line matches aggregate rule (C1) | L1 | yes |
| FR-7 | `pre_submit` → Socratic active; `post_feedback` → deep-dive active (per C4) | L1 | yes |
| FR-8 | Chip click calls `onAsk` with seed; no local reply bubble invented by chrome | L1 | yes |
| FR-9 | `CoachPanel` + coach page both render shared chrome testid / structure | L1 | yes |
| FR-10 | Manual: `decisions.md` + epics/report framing | doc | no |
| FR-11 | Manual: ADR file + index/log | doc | no |
| FR-12 | Red-first process for chrome tests | process | — |

## 9. Definition of Done

- [ ] B0: D5a + C-4 honesty in `decisions.md`; epics/report C-5 framing corrected (FR-10).
- [ ] Shared chrome on `/learn/coach` and `CoachPanel` for C-2…C-5/C-7 (FR-4…FR-9).
- [ ] C-4 never fabricates counts; C-5 display-only (FR-1, FR-2, FR-6, FR-7).
- [ ] Chips call `onAsk` only (FR-8).
- [ ] Surface VM ADR merged / recorded (FR-11).
- [ ] L1 tests authored, **seen red first**, then green (FR-12).
- [ ] `make check` + `tests/architecture/` green; evidence pasted.
- [ ] Mergeable without B2/B3.

---

## 10. Explicitly out of scope

- Desktop Ask-the-coach + green-span recap (**B2**).
- Client `coach_context` payload, seeded opener, stream depth (**B3**).
- Free mode switcher / third derived mode (**D5b**).
- Offline canned chip replies (**D4**).
- Changing ADR-0012 sanitizer / marker contract.
