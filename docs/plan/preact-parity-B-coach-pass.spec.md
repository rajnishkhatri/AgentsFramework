---
title: 'Epic B — Coach full pass (B1.5 + B2 + B3) · Spec'
type: spec
status: Accepted
date: 2026-07-09
owner: Rajnish Khatri
epic: B
derives_from:
  - docs/plan/preact-parity-sprint-board-B.md
  - docs/plan/preact-parity-epic-B.brainstorm.md
related:
  - docs/plan/preact-parity-B-coach-pass.plan.md          # plan + tasks (forthcoming)
  - docs/plan/preact-parity-B1-coach-chrome.spec.md       # B1 shipped — slots + VM
  - docs/adr/0025-coach-surface-vm.md                    # Accepted
  - docs/adr/0012-subject-coach-context-contract-hint-ladder.md
  - docs/adr/decisions.md
  - docs/plan/preact-english-coach-ui.spec.md             # FR-E1/E5, FR-F1–F6
  - docs/plan/assets/preact-parity-2026-07-09/parity-report.html
  - Eng-coach-ui-design/PreACT-English-Coach-Spec.md     # §5.4/§9 surface variants
  - Eng-coach-ui-design/English Coach - Flow (iPad).html # iPad flow artifact
  - PreAct/UI-Design/English Coach - Screens.dc.html
governs:
  - frontend/app/(coach)/learn/coach/page.tsx
  - frontend/app/(coach)/learn/quiz/page.tsx
  - frontend/components/coach/CoachChrome.tsx
  - frontend/components/coach/CoachView.tsx
  - frontend/components/coach/CoachPanel.tsx
  - frontend/components/coach/use_coach.ts
  - frontend/components/coach/coach_thread_store.ts
  - frontend/components/feedback/FeedbackView.tsx
  - frontend/lib/translators/feedback_vm.ts
  - frontend/lib/translators/coach_surface_vm.ts
  - frontend/lib/translators/ui_input_to_agent_request.ts
---

# Epic B — Coach full pass (layout · Feedback bridge · wire context)

> **What / why split.** This umbrella spec is the *what* for the Stage-5 replan
> (Option C). Intent debt for small choices → `decisions.md`; ADR-0012 / ADR-0025
> already cover mode contract and surface VM. New numbered ADR only if an
> ⚠️ Ask-first trigger fires (new abstraction / contract change).
>
> **Tracks inside one spec:** **B1.5** layout+C-1 · **B2** F-6/F-4 + pin · **B3**
> C-6 `coach_context` + honest opener. Implement in that order; each track stays
> independently mergeable.

**Status:** Accepted — 2026-07-09 · clarify C1–C5 locked · plan:
[`preact-parity-B-coach-pass.plan.md`](preact-parity-B-coach-pass.plan.md).
Do not implement until Stage-4 analyze is green and the human gates plan → tasks.

---

## 1. Goal

Make `/learn/coach` match the prototype **coaching workspace** from the parity
report: left context rail + right conversation, header Back / Wrap-up, Feedback→
Coach with a real item pin and green-span recap on Feedback, and a live
`coach_context` payload so the stream is history-aware — without fabricating
trust signals and without a free mode switcher.

## 2. Context

- **Parity report** ([parity-report.html](assets/preact-parity-2026-07-09/parity-report.html)
  §04): Coach still the largest gap vs prototype (`proto/04-coach.png`). App capture
  (`app/08-coach.png`) is pre-B1 empty shell; B1 shipped **slots** (rail copy, modes,
  chips) but **stacked**, not two-column; standalone still **no pin**; stream still
  messages-only (no client `coach_context`).
- **Already shipped (do not re-litigate):** B0 D5a + C-4 honesty; B1
  `CoachSurfaceVM` + `CoachChrome` + `countMissesOnSkill` + ADR-0025 (Accepted).
- **Seams ready:** `askCoachContext` built but unused
  ([use_feedback.ts](../../frontend/components/feedback/use_feedback.ts));
  BFF sanitizer already handles `coach_context`
  ([coach_context_sanitizer.ts](../../frontend/lib/translators/coach_context_sanitizer.ts));
  `sendCoachAsk` is messages-only today
  ([use_coach.ts](../../frontend/components/coach/use_coach.ts)).
- **UI FRs:** FR-E1 / FR-E5 · FR-F1…F6 ([preact-english-coach-ui.spec.md](preact-english-coach-ui.spec.md)).
- **Stage-5 bindings (proposed → lock in clarify):** layout = B1.5; B3 required this
  pass; cold open = honest absent C-3/C-4; C-5 stays D5a.

### 2.1 Clarify (locked 2026-07-09)

| # | Ambiguity | Recommended default | Status |
|---|---|---|---|
| C1 | Feedback→Coach **pin transport** | **Enlarge `coach_thread_store`** with a UI pin (same tab heap as transcript — FR-J3 one-thread). Ask-the-coach / quiz panel write pin; Coach page + B3 assembly read it. URL params and `sessionStorage` rejected. Schema hashed in §4.1. | **accepted (option C)** |
| C1a | Pin depth / wire extras / reset | **(1)** Pin = `{questionId, skillId, label}` only — full `Question` loaded at ask via `QuestionRepo.get`. **(2)** Omit `misses_aggregate.window` this pass (no fake “of last 5”). **(3)** Include `mastery_snapshot` on B3 wire when honest skill mastery is available from `LearnerReadRepo`. **(4)** `resetCoachThread` clears pin too. | **accepted** |
| C2 | **← Back** / **Wrap up session** destinations | Back → `router.back()` with fallback `/learn/quiz`; Wrap up → `/learn/summary` (append `?session=` when a live quiz session id is known). Always-visible controls. | **accepted** |
| C3 | **Layout composition** | Grounded in [PreACT-English-Coach-Spec §5.4 / §9](../../Eng-coach-ui-design/PreACT-English-Coach-Spec.md) + iPad flow artifact: **(Desktop `/learn/coach`)** left context rail + right conversation/chips/composer. **(iPad standalone Coach)** context in a **header strip** (not a full left rail) + chips + composer — screens centered ≤600px. **(iPad Quiz `CoachPanel`)** keep landscape **split** right panel (nudges + chips + composer stacked in the panel; same thread). Chips live with the composer, not as rail-only controls. | **accepted** |
| C4 | **Seeded opener (C-6)** | **Option A:** one honest opener **only if** pin + real misses count exist and transcript is empty — copy may cite `N`, never “of last 5”. No pin / no misses → empty until first ask. Mocked E2E remains valid sign-off. | **accepted** |
| C5 | **Green-span recap source (F-4)** | **Option A:** recap = `context_html` with `<u>` restyled to success (FR-A7); IF no `<u>` THEN show plain sentence/stem **without** inventing a highlight. | **accepted** |

---

## 3. Functional requirements (EARS)

Failure paths first. Grouped by track; FRs are globally numbered.

### B1.5 — Layout + header (C-1, visual C-2)

- **FR-1** (failure / iPad). IF the surface is the iPad quiz **CoachPanel** (landscape
  split right pane) THEN THE SYSTEM SHALL keep chrome **stacked inside the panel**
  (identity / pin / history / modes above nudges+chat) and SHALL NOT force a
  desktop-style left rail that steals the item column. IF the surface is iPad
  standalone `/learn/coach` THEN THE SYSTEM SHALL use a **header-strip** context
  (pin / history / modes) above the conversation — not a persistent left rail
  ([PreACT-English-Coach-Spec §5.4 iPad variant](../../Eng-coach-ui-design/PreACT-English-Coach-Spec.md)).
- **FR-2** (C-1). THE SYSTEM SHALL render coach workspace header actions **"← Back"**
  and **"Wrap up session →"** on standalone `/learn/coach` (destinations per clarify C2).
- **FR-3** (visual C-2 · desktop). ON standalone `/learn/coach` at **desktop** width
  THE SYSTEM SHALL present coach chrome as a **left context rail** and
  conversation/composer (with chips beside the composer) as the **primary right
  column**, matching the prototype desktop workspace ([parity `proto/04-coach`](assets/preact-parity-2026-07-09/proto/04-coach.png); Spec §5.4 / §9).

### B2 — Feedback bridge + green-span (F-6, F-4) + pin fill

- **FR-4** (failure / trust). IF `coach_thread_store.pin` is **null** (cold open /
  reset) THEN THE SYSTEM SHALL keep honest-absent current-item and history lines
  (B1 FR-1/FR-3) — no fabricated "Q4 · …" or "3 of last 5".
- **FR-5** (F-6 / FR-E5). WHEN Feedback is present on **desktop** THE SYSTEM SHALL
  provide **"Ask the coach"** that writes a store pin (from `askCoachContext` +
  label) and navigates to `/learn/coach`.
- **FR-6** (C-3/C-4 fill). WHEN the store holds a valid pin THE SYSTEM SHALL show the
  current-item line and, WHEN skill-scoped misses are available, the honest history
  line (reuse `countMissesOnSkill` / B1 rules).
- **FR-7** (F-4 / FR-E1 / FR-A7). THE SYSTEM SHALL render a Feedback sentence recap from
  `context_html`, restyling an existing `<u>` span to success coloring when present
  (clarify C5 option A); IF no `<u>` THEN THE SYSTEM SHALL show a plain sentence/stem
  without inventing a highlight.
- **FR-8.** THE SYSTEM SHALL keep desktop Feedback **Next / Finish** behavior unchanged
  aside from adding Ask-the-coach; iPad live panel SHALL NOT regress.

### B3 — Wire context + opener (C-6)

- **FR-9** (failure / trust). IF no honest pin or aggregate exists THEN THE SYSTEM
  SHALL NOT send fabricated `misses_aggregate` / `mastery_snapshot` / history claims
  on the wire or in a seed bubble. Omit optional fields rather than invent values;
  NEVER invent `misses_aggregate.window`.
- **FR-10** (C-6). WHEN the learner sends a coach ask (composer or chip) AND a pin is
  present THE SYSTEM SHALL include a client `input.coach_context` on the run body
  per §4.2 (question identity + advisory mode + `question` from `QuestionRepo.get` +
  optional honest `misses_aggregate` + optional honest `mastery_snapshot`). Plain
  asks without pin MAY remain messages-only.
- **FR-11.** THE SYSTEM SHALL NOT trust client `coach_context.mode` — BFF continues to
  overwrite via `deriveCoachMode` (ADR-0012).
- **FR-12** (optional seed · clarify C4). WHERE an honest opener is enabled AND
  transcript is empty AND pin+misses exist THEN THE SYSTEM MAY show one coach opener
  that references only real counts; OTHERWISE THE SYSTEM SHALL leave the log empty
  until the first ask.
- **FR-13.** THE SYSTEM SHALL prove B3 with mocked stream E2E and/or L1 tests that
  assert run-body shape — no live LLM required for DoD.

### Cross-cutting (already decided)

- **FR-14.** THE SYSTEM SHALL keep C-5 **display-only** (D5a); chips remain `onAsk`
  seeds (B1). No free mode switcher (D5b out of scope).

## 4. Data model / contracts

### 4.1 Store pin (client UI · clarify C1 / C1a) — not the wire shape

Extend existing [`coach_thread_store`](../../frontend/components/coach/coach_thread_store.ts)
(not a new store / not a new G1 abstraction):

```ts
interface CoachSurfacePin {
  questionId: string;
  skillId: string;
  label: string;           // chrome C-3 only — never pasted into the prompt
}

interface CoachThreadState {
  threadId: string | null;
  turns: ReadonlyArray<ChatTurn>;
  busy: boolean;
  pin: CoachSurfacePin | null;   // NEW — null = honest absent
}
```

- **API:** `setCoachPin(pin | null)`; `resetCoachThread()` clears **pin + turns +
  threadId** (C1a #4).
- **Writers:** desktop Ask-the-coach; quiz `CoachPanel` (keep pin aligned with live item).
- **Readers:** chrome surface VM; B3 ask assembly.
- Full `Question` is **not** stored — load via `QuestionRepo.get(questionId)` at ask.

### 4.2 Wire `input.coach_context` (B3 · design §4.1 / subject-coach-agent.spec §4)

```ts
input.coach_context = {
  mode: "pre_submit" | "post_feedback",  // ADVISORY — BFF overwrites (ADR-0012)
  question_id: string,
  skill_id: string,
  question: Question,                    // BFF strips 4 answer fields if pre_submit
  misses_aggregate?: {                   // omit entire object if no honest count
    skill_id: string,
    missed: number,
    // window: OMIT this pass (C1a #2) — no fake "of last 5"
  },
  mastery_snapshot?: Record<string, number>,  // skill_id → mastery_pct when available
}
```

| Field | Source | Honesty |
|---|---|---|
| `question_id` / `skill_id` | store pin | required when pin present |
| `question` | `QuestionRepo.get` | omit whole `coach_context` if load fails |
| `mode` | host-derived advisory | never trusted by BFF |
| `misses_aggregate` | `countMissesOnSkill` | omit if `null`; **no `window`** |
| `mastery_snapshot` | `LearnerReadRepo` for pinned skill (and optional others) | omit if unavailable; never invent pct |

Python formatter may not render aggregate/mastery yet — still ship on the wire this
pass (G9: structured numbers only; no client prose into the prompt).

### 4.3 Other surfaces

| Surface | Change |
|---|---|
| `CoachSurfaceVM` / ADR-0025 | Reused (pin feeds existing fields) |
| `FeedbackVM` | Add recap fields (sentence + optional success span) |
| `FeedbackView` / quiz page | Ask the coach → `setCoachPin` + navigate; Next/Finish unchanged |
| `uiInputToAgentRequest` / `sendCoachAsk` | Optional `coach_context` beside messages |
| BFF sanitizer | **Unchanged** strip/mode rules |
| ADR-0012 | No mode-taxonomy change |

**⚠️ Ask first:** none expected — store extension is the same FR-J3 singleton (C1), not a
new abstraction. Record C1a in `decisions.md`.

## 5. Invariants & security boundaries

- Frontend F-R1 / T1 / F-R2 hold (presentational views; pure translators; SDK in adapters).
- ADR-0012: client mode advisory; answer-bearing strip on `pre_submit` unchanged.
- AP-6: no fabricated history on rail, seed, or wire.
- Architecture #1–#8: frontend-only; no new graph node / horizontal service.
- G8: do not weaken existing Feedback / coach stream tests.

## 6. Edge cases

- Cold `/learn/coach`: `pin === null` → empty rail slots; modes default `pre_submit`.
- `resetCoachThread`: clears pin (FR-4 path again).
- Question load failure at ask: no `coach_context` (messages-only) — do not send partial identity pretending a full question.
- Ask-the-coach before verdict: control only when Feedback present.
- Busy stream + Ask-the-coach: navigate still allowed; chips stay disabled while busy.
- iPad: Ask-the-coach optional/redundant if panel already watching the item — prefer not duplicating navigation.
- Opener + existing transcript: never re-seed.
- Recap with no markable span: clarify C5.

## 7. Non-functional requirements

- L1 vitest / RTL primary; mocked Playwright for Coach/Feedback where valuable.
- No live LLM in CI; mocked coach stream remains valid B3 sign-off.
- No new npm/py dependency.
- Desktop-first two-column; `CoachPanel` stacked.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | CoachPanel stacked; iPad standalone uses header-strip (no left rail) | L1 | yes |
| FR-2 | Back + Wrap-up present on coach page | L1 | yes |
| FR-3 | Desktop coach page left rail + right chat/chips | L1 | yes |
| FR-4 | `pin === null` → absent current-item/history | L1 | yes |
| FR-5 | Ask-the-coach → `setCoachPin` + navigate to `/learn/coach` | L1 (+ optional e2e) | yes |
| FR-6 | Pin → current-item; fixture misses → history | L1 | yes |
| FR-7 | FeedbackVM/view recap + success span when markable | L1 | yes |
| FR-8 | Next/Finish still work; panel unregressed | L1 | yes |
| FR-9 | No pin → no fake aggregate on ask body | L1 | yes |
| FR-10 | Pin present → run body has `coach_context` | L1 | yes |
| FR-11 | Advisory mode still overwritten in sanitizer tests (existing) | L1 | yes |
| FR-12 | Opener only when honest; never fake window | L1 | yes |
| FR-13 | Mocked e2e or body assert | L1 / e2e | yes / e2e |
| FR-14 | Modes remain non-overriding; chips → onAsk | L1 | yes |

## 9. Definition of Done

- [x] Clarify C1–C5 locked; plan + tasks accepted; Stage-4 analyze green.
- [x] B1.5: two-column standalone + Back/Wrap-up (FR-2, FR-3); panel FR-1 holds.
- [x] B2: desktop Ask-the-coach + green-span; pin fills C-3/C-4 (FR-4…FR-8).
- [x] B3: `coach_context` on ask when pinned; honest opener rules (FR-9…FR-13).
- [x] D5a / chip behavior unchanged (FR-14).
- [x] L1 tests seen red first then green; `make check` + architecture green; evidence pasted.
- [x] Board exit: B1.5/B2/B3 checked; parity report Coach findings updated.

## 10. Explicitly out of scope

- Re-opening B0/B1 decisions (D5a, C-4 aggregate shape, ADR-0025).
- Free mode switcher (**D5b**).
- Offline canned chip replies (**D4**).
- Dashboard rail / Summary / Skill / Progress (Epics C+).
- Changing sanitizer strip rules or inventing a third derived mode.
