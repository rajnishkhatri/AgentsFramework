---
title: 'Epic B — Coach surface build-out · Sprint Board'
type: sprint-board
epic: B
date: 2026-07-09
status: Draft
derives_from: docs/plan/preact-parity-epics.md
report: docs/plan/preact-ui-prototype-parity-VISUAL-gap-report.md
governs:
  - docs/plan/preact-parity-epic-B.brainstorm.md   # Stage-1 CLOSED 2026-07-09
  - docs/plan/preact-parity-B1-coach-chrome.spec.md      # Accepted 2026-07-09 · implemented
  - docs/plan/preact-parity-B1-coach-chrome.plan.md      # Accepted — implemented 2026-07-09
  - docs/adr/0025-coach-surface-vm.md                   # Accepted (G1)
  - docs/plan/preact-parity-B-coach-pass.spec.md        # Umbrella Accepted 2026-07-09 (B1.5+B2+B3)
  - docs/plan/preact-parity-B-coach-pass.plan.md         # Accepted 2026-07-09 — implementing
method: SDD lifecycle — umbrella Coach-pass spec for remaining work; implement by track (B1.5→B2→B3)
---

# Epic B — Coach surface build-out · **Sprint Board**

**Epic goal** (from [epics doc](preact-parity-epics.md#epic-b--coach-surface-build-out-)): turn
`/learn/coach` from a title+composer shell into the prototype's **coaching workspace**, and close
the desktop Feedback→Coach bridge. Flagship *within-screen* parity increment.

**Findings in scope:** `C-2…C-7`, `F-6`, `F-4`, plus layout/`C-1`.

> **Stage-1 CLOSED** ([brainstorm](preact-parity-epic-B.brainstorm.md)) — binding:
> **D1+D6** shared chrome · **D5a** display-only 3→2 modes · **D2** Feedback bridge+recap ·
> **D3** stream context · chips = `onAsk` seeds · original ladder **B0 → B1 → B2 → B3**.
>
> **Stage-5 replan (2026-07-09):** user chose **Option C — full Coach pass** vs parity
> report prototype. Remaining work uses **one umbrella spec**
> ([`preact-parity-B-coach-pass.spec.md`](preact-parity-B-coach-pass.spec.md)) covering
> **B1.5 → B2 → B3**. B3 is **in-scope** for this pass (no longer slip-default). B0/B1 stay
> shipped; Do not re-open D5a / C-4 honesty / ADR-0025.
>
> Stage-1 framing (still binding):
>
> - **`C-5` is not a free 3-way switcher.** Display-only **D5a** (ADR-0012).
> - **`C-4` is a trust signal.** Real misses **or honestly absent** — never placeholder.
> - **`C-6` is not "build the stream."** Stream exists; pass closes `coach_context` + opener.
> - **`F-4` is FR-E1**, paired with F-6.

---

## Sprint ladder (release order within the epic)

| Sprint | Title | Findings | Type | Releasable alone? | Blocks |
|--------|-------|----------|------|-------------------|--------|
| **B0** | Mode taxonomy + honesty rules (docs) | `C-5` framing, `C-4` honesty | Docs-only | ✅ yes | B1 |
| **B1** | Coach chrome slots (shared standalone + iPad) | `C-2`…`C-5`, `C-7` data/slots | **D1+D6** + **D5a** | ✅ yes | B1.5 / B2 |
| **B1.5** | Two-column workspace layout + header actions | Visual `C-2`, `C-1` | Layout / composition | ✅ yes | — |
| **B2** | Feedback→Coach desktop + green-span recap | `F-6`, `F-4` (+ pin fills C-3/C-4) | **D2** | ✅ yes | B3 (pin for context) |
| **B3** | Live context + conversation depth | `C-6` (+ `coach_context`) | **D3** — **required this pass** | ✅ yes | — |

**Independence rule (program §4):** each track may merge to `main` alone. B1.5 may ship
without B2 (empty pin OK). B2 may ship without B3 (chrome+pin without wire context). B3
completes the prototype conversation depth for this pass.

```
B0 ──► B1 ──► B1.5 (layout) ──► B2 (bridge+recap) ──► B3 (coach_context)
                 └──────── umbrella Coach-pass spec ────────┘
```

---

## Sprint B0 — Mode taxonomy + honesty rules  🟦 *(docs-only)*

**Origin:** Stage-1 premise audit **refuted** "C-5 = wire a free 3-mode switcher" and forbade
fabricated history counts. Per the brainstorm hardening rule, record the corrected space before
B1 implements UI.

**Decisions to land (no production code):**

1. **`decisions.md` — D5a (C-5).** Prototype shows three mode *labels*; runtime has two
   derived modes (`pre_submit` / `post_feedback`). Epic B ships a **display-only** mapping
   (e.g. In-drill Socratic → `pre_submit`; Post-answer deep-dive + Misconception summary →
   `post_feedback` presentation variants, or Misconception as copy under deep-dive). Learner
   cannot override the marker-derived mode. Cite ADR-0012 +
   [coach_context_sanitizer.ts](../../frontend/lib/translators/coach_context_sanitizer.ts).
2. **`decisions.md` — C-4 honesty.** History line uses real `AttemptRepo.misses()` (windowed
   aggregate) or renders an honest absent state; never placeholder counts (AP-6 / epic gate).
3. **Back-propagate framing** to [preact-parity-epics.md](preact-parity-epics.md) Epic B
   (`C-5` row + Gates) and a short note in the VISUAL report §4 C-5/C-4 if still claiming a
   free switcher / implied fake counts.
4. **ADR intent note for B1.** Flag that B1's coach **surface VM** is the likely `⚠️ Ask first`
   (G1 new abstraction) — B0 does not author the ADR; B1's `sdd-spec` does when the VM shape
   is chosen. D5a itself is `decisions.md` weight (no new derived mode).

**Definition of Done (B0):** D5a + C-4 honesty recorded in `decisions.md`; epics (and report if
needed) no longer say "free switcher"; B1 framing = display-only modes + honest history.
**No `.tsx` / reducer / VM change.**

**Gates:** No ADR in B0. No `⚠️ Ask first` for docs.

**Releasable alone:** ✅ — docs PR; unblocks B1.

---

## Sprint B1 — Coach chrome (shared standalone + iPad)  🟧

**Report findings:** `C-2` context rail · `C-3` current-item · `C-4` history trust line ·
`C-5` mode surface (display) · `C-7` quick-reply chips.

**Direction:** **D1+D6** — shared presentational chrome used by `/learn/coach` and
`CoachPanel`, fed by a coach **surface VM** (new) + existing engine reads. Chips = **`onAsk`
seeds** only (no local canned coach).

**Visual / seam anchors (pre-B1):**

| Seam | Today | Target |
|------|-------|--------|
| Standalone page | [page.tsx](../../frontend/app/(coach)/learn/coach/page.tsx) — title + `CoachView` | + shared chrome (rail / modes / chips) |
| `CoachView` | [CoachView.tsx](../../frontend/components/coach/CoachView.tsx) — log + composer | Accept chrome props **or** compose beside shared `CoachChrome` |
| iPad panel | [CoachPanel.tsx](../../frontend/components/coach/CoachPanel.tsx) — mini-header only | Same chrome leaf (D6) |
| Mode derive | [coach_context_sanitizer.ts](../../frontend/lib/translators/coach_context_sanitizer.ts) | **Display** D5a map; do not trust client override |
| History data | [attempt_repo.ts `misses()`](../../frontend/lib/ports/engine/attempt_repo.ts) | Wire into coach hook/VM; honest absent OK |
| Bubble VM | [coach_message_vm.ts](../../frontend/lib/translators/coach_message_vm.ts) | Unchanged (B3 owns stream depth) |

**In scope:**

- Context rail: "Your Coach / Adaptive · always on" + status affordance (`C-2`).
- Current-item line when an item is pinned; honest absent when not (`C-3`).
- History line from real misses aggregate or absent (`C-4`).
- Mode surface: three labels, display-only, driven by derived mode (`C-5` / D5a).
- Quick-reply chips that seed the composer / call `onAsk` (`C-7`).
- Extract shared chrome so standalone and iPad panel do not drift (`D6`).

**Out of scope (other sprints):** desktop Ask-the-coach / green-span (`B2`); client
`coach_context` payload + seeded opener (`B3`); free mode switcher (deferred D5b); offline
canned chip replies (deferred D4).

**Likely seams (spec will pin):**

| Layer | Pattern to follow |
|-------|-------------------|
| Hook | `use_dashboard` / page composition — engine read in hook, not in view |
| Translator | pure T1 surface VM (new) — G1 → **ADR at spec time** |
| View | presentational leaf (F-R1); SDK stays in `lib/adapters/` |
| Tests | L1 RTL/jsdom for chrome structure; fixture misses for C-4; no live agent required |

**Definition of Done:** `/learn/coach` and iPad `CoachPanel` render shared chrome for
C-2…C-5/C-7; C-4 never fabricates counts; C-5 is non-overriding display; chips call `onAsk`;
ADR (if surface VM is new abstraction) + `make check` + arch-tests green; mergeable without B2/B3.

**Gates:** **Likely ADR** — coach surface VM / mode display surface (`⚠️ Ask first` G1). Confirm
in B1 `sdd-spec`. Frontend Ring F-R1 / T1 / adapter boundary.

**Releasable alone:** ✅ — chrome ships with empty or mocked transcript; stream already works
as today.

**Spec:** [`preact-parity-B1-coach-chrome.spec.md`](preact-parity-B1-coach-chrome.spec.md) *(Accepted)* ·
**Plan:** [`preact-parity-B1-coach-chrome.plan.md`](preact-parity-B1-coach-chrome.plan.md) *(Accepted — implemented)*.
**ADR:** [`0025-coach-surface-vm.md`](../adr/0025-coach-surface-vm.md) *(Proposed)*.

---

## Sprint B1.5 — Two-column workspace + header  🟧 *(umbrella track)*

**Report findings:** visual `C-2` (left rail composition) · `C-1` Back / Wrap up.

**Direction:** compose B1 chrome into prototype **left rail + right chat** on standalone
desktop; add header actions. Narrow `CoachPanel` stays stacked.

**Umbrella:** [`preact-parity-B-coach-pass.spec.md`](preact-parity-B-coach-pass.spec.md) FRs 1–3.

**Definition of Done:** desktop `/learn/coach` reads as two-column workspace; Back + Wrap-up
present; panel unregressed; L1 tests green. Mergeable without B2/B3.

---

## Sprint B2 — Feedback→Coach desktop + green-span recap  🟧

**Report findings:** `F-6` Ask-the-coach on desktop Feedback · `F-4` green-span sentence recap.

**Direction:** **D2** — consume existing `askCoachContext`; add FR-E1 recap to Feedback VM/view.

**Why after B1/B1.5:** brainstorm H6 — bridge should pin **current item** into the chrome C-3 slot.
**Umbrella:** [`preact-parity-B-coach-pass.spec.md`](preact-parity-B-coach-pass.spec.md) FRs 4–8.

**Seam anchors (pre-B2):**

| Seam | Today | Target |
|------|-------|--------|
| Context built | [use_feedback.ts](../../frontend/components/feedback/use_feedback.ts) `askCoachContext` | **Consumed** by Feedback action |
| Desktop Feedback actions | quiz page Next/Finish only; coach runtime **iPad-only** | "Ask the coach" on desktop → Coach with item in context (FR-E5) |
| Feedback VM | [feedback_vm.ts](../../frontend/lib/translators/feedback_vm.ts) — no recap field | Sentence recap + success-colored span (FR-E1 / FR-A7) |
| Quiz context HTML | `quiz_item_vm` `contextHtml` | Reuse / adapt for post-answer success coloring |

**In scope:** F-6 desktop control + navigation/pin into coach; F-4 recap block on Feedback.

**Out of scope:** full coach chrome (B1); stream/`coach_context` body (B3); iPad panel already
has live coach — do not regress it.

**Definition of Done:** desktop Feedback shows working "Ask the coach" that lands on Coach with
item context; Feedback shows green-span recap; L1 + (optional) e2e; `make check` green; ships
without B3.

**Gates:** Unlikely new ADR if only VM field + action wiring. Record FR-E5 closure in
`decisions.md` if useful. No fabricated coach replies on the bridge path.

**Releasable alone:** ✅ — after B1 preferred; coherent even if B3 deferred.

**Spec:** umbrella [`preact-parity-B-coach-pass.spec.md`](preact-parity-B-coach-pass.spec.md) + [`preact-parity-B-coach-pass.plan.md`](preact-parity-B-coach-pass.plan.md) *(Accepted)*.

---

## Sprint B3 — Live context + conversation depth  🟧 *(required this pass)*

**Report finding:** `C-6` seeded / live conversation (re-posed: not "missing stream route").

**Direction:** **D3** — assemble client `coach_context` (incl. honest misses aggregate when
data exists), optional seeded opener, prove depth with mocked stream. **Required** under the
2026-07-09 Option C replan (no longer slip-default for Epic B exit of this pass).

**Seam anchors:**

| Seam | Today | Target |
|------|-------|--------|
| Stream client | [use_coach.ts](../../frontend/components/coach/use_coach.ts) | Pass structured context into run body |
| BFF | [run/stream/route.ts](../../frontend/app/api/coach/run/stream/route.ts) + sanitizer | Already sanitizes when `coach_context` present |
| Run body | messages-only today | `coach_context` + aggregate aligned with C-4 assembly |
| Seed | `coach_thread_store` starts `turns: []` | Optional honest opener (no fake history claims) |
| E2E | [coach-mocked.spec.ts](../../frontend/e2e/learn/coach-mocked.spec.ts) | Extend for context-aware / seeded cases |

**In scope:** context payload wiring; optional seed; tests proving chrome+context without
requiring prod persona if env lacks it (mocked path remains valid sign-off for slip).

**Out of scope:** redesigning ADR-0012 marker/mode contract; third derived mode (D5b);
canned offline coach (D4).

**Definition of Done (when not slipped):** client sends sanitized-ready `coach_context`;
history aggregate shared with C-4 honesty rules; seeded state (if any) does not invent misses;
mocked E2E green; live probe documented if environment allows. **If slipped:** board + epics
exit note "B3 deferred"; B1/B2 still count as Epic B chrome+bridge release.

**Gates:** Prefer amend/extend ADR-0012 only if contract changes; else `decisions.md`. Calendar
risk = live middleware/auth for sign-off — keep mocked path as the releasability backstop.

**Releasable alone:** ✅ — and **deferrable** without blocking Epic B's chrome/bridge value.

**Spec:** umbrella [`preact-parity-B-coach-pass.spec.md`](preact-parity-B-coach-pass.spec.md) FRs 9–13 *(Accepted)*.

---

## Epic-B exit criteria (what "released" means)

- [x] **B0 shipped:** D5a + C-4 honesty in `decisions.md`; epics/report C-5 framing corrected.
- [x] **B1 shipped:** shared chrome for C-2…C-5/C-7; honest C-4; display-only modes; ADR-0025.
  *Log (2026-07-09): B1 shipped shared CoachChrome + surface VM; C-4 honest; C-5 display-only; chips→onAsk; no coach_context on wire.* (merge to `main` still pending.)
- [x] **B1.5 shipped:** two-column standalone + Back/Wrap-up (C-1 / visual C-2).
- [x] **B2 shipped:** desktop Ask-the-coach (F-6) + green-span recap (F-4); pin fills C-3/C-4.
- [x] **B3 shipped:** client `coach_context` + honest opener rules (C-6) — **required this pass**.
- [ ] Umbrella Coach-pass spec Accepted + plan green; parity report Coach findings updated.
- [ ] **Gate to Epic C:** after B1.5+B2+B3 on `main` (or explicit human waiver). One epic in flight.

---

## Notes carried back to the parity report / epics

Stage-1 (2026-07-09) corrections to fold into the VISUAL report and epics Epic B section:

1. **C-5** — "mode switcher" → **derived-mode display** (D5a); free override deferred.
2. **C-4** — trust signal; real misses or absent — call out explicitly in report notes.
3. **C-6** — stream plumbing exists; gap is context/seed/chrome, not missing route.
4. **F-4** — FR-E1 gap paired with F-6 in B2.
5. **ID drift** — superseded gap-matrix renumbered Coach rows; canonical IDs remain VISUAL
   report C-2…C-7 / F-4 / F-6.
