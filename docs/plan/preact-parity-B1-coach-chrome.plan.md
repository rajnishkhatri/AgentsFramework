---
title: 'Sprint B1 — Coach chrome (D1+D6 + D5a) · Plan + Tasks'
type: plan
status: Accepted
date: 2026-07-09
owner: Rajnish Khatri
epic: B
implements: docs/plan/preact-parity-B1-coach-chrome.spec.md
related:
  - docs/plan/preact-parity-epic-B.brainstorm.md
  - docs/plan/preact-parity-sprint-board-B.md
  - docs/adr/0025-coach-surface-vm.md
  - docs/adr/decisions.md
---

# Sprint B1 — Plan + Tasks

Implements [preact-parity-B1-coach-chrome.spec.md](preact-parity-B1-coach-chrome.spec.md).
Direction **D1+D6** + **D5a**; chips = immediate `onAsk` (C5). Clarify C1–C5 locked.
**⚠️ Ask first / G1:** [ADR-0025](../adr/0025-coach-surface-vm.md) (**Accepted** at implement
gate 2026-07-09). B0 docs co-land (FR-10).

**Integration premise (scout 2026-07-09):** coach stream stack already works
(messages-only run body). B1 adds **UI chrome only** — does not send `coach_context`
(B3). No new Zod wire entity; protocol remains ADR-0012 + open `RunCreateRequest.input`.

---

## 1. Architecture / approach

```
quiz/page.tsx (iPad)                    coach/page.tsx (standalone)
  │ pin: Qn · skill · phase→mode          │ pin: absent (C2)
  │ misses: skill-scoped (C1)             │ mode: default pre_submit
  └──────────────┬────────────────────────┘
                 ▼
        loadCoachSurfaceInputs (hook / async gather)
                 ▼
        toCoachSurfaceVM  (T1 — ADR-0025)
                 ▼
        CoachChrome (presentational: rail · item · history · modes · chips)
                 ▼
        CoachView (unchanged: log + Composer) ← onAsk / busy from useCoach
```

| Concern | Rule |
|---|---|
| Mode display | Host supplies derived `CoachMode` (quiz `phase`: answering→`pre_submit`, reviewing→`post_feedback`; standalone→`pre_submit`). Labels are badges, not controls (FR-2). |
| History | `attemptRepo.misses` → for each unique `question_id`, `questionRepo.get` → filter `skill_id === pin.skillId` → count. No pin / error / empty → omit line (FR-1). **No "of last 5" window.** |
| Chips | Static seeds from VM; click → `onAsk(seed)` when `!busy`. |
| Protocol | Unchanged. Do not extend `uiInputToAgentRequest` in B1. |

**Chip seed copy (prototype C-7):**
1. `Explain the rule simply`
2. `Give me a similar item`
3. `Show my comma pattern` — keep prototype wording as static seed (not history-aware);
   do not claim a real pattern analysis in B1.

---

## 2. File-level touchpoints

| # | File | Change | FR |
|---|---|---|---|
| T0a | [docs/adr/decisions.md](../adr/decisions.md) | B0: D5a + C-4 honesty (newest-first) | FR-10 |
| T0b | [preact-parity-epics.md](preact-parity-epics.md) + VISUAL report C-5/C-4 notes | Drop "free switcher" / fake-count framing | FR-10 |
| T0c | [docs/adr/0025-coach-surface-vm.md](../adr/0025-coach-surface-vm.md) + index + log | Already drafted Proposed; ratify + OKF entries if not complete | FR-11 |
| T1 | `frontend/lib/translators/coach_surface_vm.ts` (+ `.test.ts`) | New T1 VM + D5a mode map + history line builder | FR-1,3,6,7 |
| T2 | `frontend/components/coach/CoachChrome.tsx` (+ `.test.tsx`) | Shared presentational chrome | FR-2,4,5,8,9 |
| T3 | `frontend/components/coach/use_coach_surface.ts` (or page-local gather) | Async: misses + skill join; compose VM inputs | FR-6 |
| T4 | [CoachPanel.tsx](../../frontend/components/coach/CoachPanel.tsx) | Accept pin props; render `CoachChrome` above `CoachView` | FR-5,9 |
| T5 | [quiz/page.tsx](../../frontend/app/(coach)/learn/quiz/page.tsx) | Pass pin + phase-derived mode into `CoachPanel` | FR-5,7 |
| T6 | [coach/page.tsx](../../frontend/app/(coach)/learn/coach/page.tsx) | Compose `CoachChrome` + `CoachView`; no pin; load history only if skill known (else absent) | FR-3,4,9 |
| T7 | Existing coach tests | Keep green; extend Panel/View as needed | FR-12 |

**Explicitly untouched:** `use_coach.ts`, `coach_thread_store.ts`, `coach_message_vm.ts`,
`coach_context_sanitizer.ts`, `ui_input_to_agent_request.ts`, stream route, Python
`coach_context.py`, Feedback stack (B2).

---

## 3. Migration / sequencing

1. **B1-0** — B0 docs + ADR-0025 OKF (FR-10, FR-11).
2. **B1-1** — `coach_surface_vm` tests → **red first** → implement (FR-1,3,6,7).
3. **B1-2** — `CoachChrome` tests → **red first** → implement (FR-2,4,5,8).
4. **B1-3** — Wire gather hook + Panel + pages (FR-5,6,7,9).
5. **B1-4** — Green gate; paste evidence (DoD).

---

## 4. Constitution check

- Invariants #1–#8: frontend-only; no new service/node/dep.
- F-R1 / T1 / F-R2: leaf presentational; VM pure; no SDK in components.
- ADR-0012: display mode never trusted into sanitizer.
- Ask-first: **ADR-0025** covers G1 surface VM.
- AP-6: C-4 honesty (FR-1/FR-6).
- G8: adds tests only.

---

## 5. Task list (atomic, 1:1 to EARS)

### Task B1-0 — B0 docs + ADR-0025 OKF  `[FR-10, FR-11]`
- **Do:**
  1. Prepend `decisions.md`: D5a (3 labels → 2 derived modes, display-only; cite
     ADR-0012 + sanitizer); C-4 honesty (real skill-scoped misses or absent; never
     placeholder "3 of last 5").
  2. Patch epics Epic B + VISUAL report §4 C-5/C-4 notes so they no longer claim a free
     switcher / imply fake counts.
  3. Ensure ADR-0025 is in `docs/adr/index.md` + newest-first `log.md` line; status
     Proposed until implement gate.
- **Verify:** `head` of `decisions.md` shows B0; grep epics/report for corrected framing;
  ADR file + index/log present.
- **Pass/fail:** FR-10/11 docs complete; no `.tsx` required in this task.

### Task B1-1 — Author + implement `coach_surface_vm` (red first)  `[FR-1, FR-3, FR-6, FR-7, FR-12]`
- **Do:** Add `coach_surface_vm.ts` exporting `CoachSurfaceVM` + `toCoachSurfaceVM(inputs)`:
  - Inputs: `mode: CoachMode`, `pin: { questionId, skillId, label } | null`,
    `missesOnSkill: number | null` (null = absent), `chipSeeds: readonly string[]`.
  - Outputs: rail copy constants, `currentItemLine: string | null`, `historyLine: string | null`,
    `modes: { id, label, active }[]` (C4 map), `chips`.
  - History copy when count known: `Sees your history: N misses on <skillLabel>` (skill
    name preferred; skillId fallback). Never emit "of last 5".
  - Mode map: `pre_submit` → Socratic `active`; `post_feedback` → deep-dive `active`;
    Misconception always `active: false`.
- **Verify (red then green):** vitest on translator — absent pin/history; both modes;
  never contains `of last 5`. **Paste red.**
- **Pass/fail:** FR-1/3/6/7 covered at T1; pure (no React/I/O).

### Task B1-2 — Author + implement `CoachChrome` (red first)  `[FR-2, FR-4, FR-5, FR-8, FR-12]`
- **Do:** Presentational leaf: renders VM regions with stable `data-testid`s
  (`coach-chrome`, `coach-rail`, `coach-current-item`, `coach-history`, `coach-modes`,
  `coach-chip`). Mode labels are non-interactive (or `aria-disabled` / no `onClick` that
  changes mode). Chips call `onAsk(seed)` when enabled; disabled when `busy`.
- **Verify (red then green):** RTL — structure; pin absent/present; chip calls `onAsk`
  once; mode click does not invoke a mode-change spy. **Paste red.**
- **Pass/fail:** FR-2/4/5/8 green.

### Task B1-3 — Wire gather + Panel + pages  `[FR-5, FR-6, FR-7, FR-9]`
- **Do:**
  1. Gather helper (in `use_coach_surface.ts` or beside it): given ports +
     `{ subject, learnerId, skillId? }` → `missesOnSkill: number | null` via
     `misses()` + `questionRepo.get` join; swallow errors → `null` (FR-1).
  2. `CoachPanel`: new props `pin?`, `mode: CoachMode`, optional `skillLabel`; compose
     `CoachChrome` + existing nudge header/ladder + `CoachView`.
  3. `quiz/page.tsx`: when rendering `CoachPanel`, pass
     `pin` from `item` + `progressVm.position` label, `mode` from `state.phase`.
  4. `coach/page.tsx`: replace thin h1 with `CoachChrome` (no pin; default mode
     `pre_submit`); keep `CoachView` below.
- **Verify:** Panel + page tests show shared `coach-chrome`; quiz panel shows current-item
  when item loaded; standalone omits current-item.
- **Pass/fail:** FR-5/6/7/9; existing Panel nudge tests still green.

### Task B1-4 — Green the gate  `[DoD]`
- **Do:** frontend vitest for new + existing coach tests; `make check`;
  `pytest tests/architecture/ -q`.
- **Verify (pasted):** all green.
- **Log line:** "B1 shipped shared CoachChrome + surface VM; C-4 honest; C-5 display-only; chips→onAsk; no coach_context on wire."

---

## 6. Parallelization

- **B1-0** parallel with B1-1 authoring (docs vs code).
- **B1-1 before B1-2** (VM type feeds chrome props).
- **B1-2 before B1-3** (leaf before hosts).
- **B1-4** barrier.
- B2/B3 must not start until B1 merges (program: one epic sprint in flight preferred).

## 7. What is explicitly NOT in B1

- `coach_context` / `misses_aggregate` on run body (**B3**).
- Desktop Ask-the-coach / green-span (**B2**).
- Free mode switcher / D5b.
- Canned offline chip replies (**D4**).
- New Zod `CoachContext` in `lib/wire/`.
- Changing ADR-0012 sanitizer or marker store.

---

## 8. Stage-4 Analyze (spec ↔ plan ↔ tasks ↔ constitution)

Cross-artifact check before implementation. Grounding: 2026-07-09 (integration scout).

| Check | Result |
|---|---|
| Every FR has a task | **OK** — FR-1/3/6/7→B1-1; FR-2/4/5/8→B1-2; FR-5/6/7/9→B1-3; FR-10/11→B1-0; FR-12→B1-1/2 red-first + B1-4 |
| Every plan path exists or is explicitly forthcoming | **OK** — existing coach/quiz/page/panel/ports; new files named in plan |
| Protocol cited correctly | **OK** — no Zod coach_context; open `RunCreateRequest.input`; B3 owns payload |
| Attempt has no skill_id | **OK** — plan uses `questionRepo.get` join (C1) |
| Ask-first / ADR | **OK** — ADR-0025 drafted; index/log must land in B1-0 |
| Invariant stress | **OK** — F-R1/T1/F-R2; ADR-0012 display-only |
| Zero-coverage FR | **OK** — none |
| B0 not yet in decisions.md | **NOTE** — B1-0 lands it (same as A0/A1 co-land) |
| Baseline green before impl | **PENDING** — run `make check` + arch tests at implement start; paste |

**CRITICAL:** none blocking plan acceptance.

**Human gate:** accept this plan → then **sdd-implement** (B1-0…B1-4).
