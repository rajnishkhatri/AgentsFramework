---
type: tasks
title: "Eng Coach WorkOS learner identity + fresh progress slate — tasks"
description: >-
  Stage 3 atomic tasks for eng-coach-workos-learner-identity. Measurability
  checklist + file-level pass/fail mapped 1:1 to FR-1…FR-11. Failure-path
  tasks first. Locked clarify: Q-C1=A Q-C2=A Q-C3=A Q-C4=A Q-C5=A.
status: "Stage 6 DONE 2026-07-14 — unit evidence green — await @t3 live + Stage 7/9"
authored: 2026-07-14
derives_from:
  - docs/plan/eng-coach-workos-learner-identity.spec.md
  - docs/plan/eng-coach-workos-learner-identity.plan.md
---

# Tasks — Eng Coach WorkOS learner identity + fresh progress slate

**Spec:** [eng-coach-workos-learner-identity.spec.md](eng-coach-workos-learner-identity.spec.md) ·
**Plan:** [eng-coach-workos-learner-identity.plan.md](eng-coach-workos-learner-identity.plan.md)

**Status:** Stage 6 DONE 2026-07-14 — unit evidence green — await `@t3` live stack + Stage 7 review / Stage 9 converge

**Stage 4 analyze (grounded):** all plan touchpoints exist on `origin/main` tip
(`layout.tsx`, `_dev_seed.ts`+test, `composition_engine_browser.ts`,
`engine-provider.tsx`, six learn pages + progress, `use_coach`/`CoachPanel`,
D3 pytest reject paths). No missing path / CRITICAL. Proceed to implement.

Convention: `T{n}` = task; `[P]` = parallelizable with other same-block `[P]`
tasks; `[red]` = watched failure first; each task names **Verifies** FR(s) and
explicit **Pass / Fail**.

**Branch posture:** implement on a feature branch off current product tip (or
`origin/main` if identity work should land clean). Do **not** weaken
`frontend/e2e/learn/**` oracles; bypass must keep Garvit demo.

---

## Checklist — every FR collapses to a measurable claim (Stage 3 gate)

| FR | Measurable claim | Oracle / evidence |
|----|------------------|-------------------|
| FR-1 | `resolveLearnIdentity(null, bypass=false)` does **not** return `learnerId === "Garvit"` (throws or typed unreachable) | Unit test fail→pass |
| FR-2 | `bypass=true` → `learnerId === DEV_LEARNER_ID`, `displayName === "Garvit"`, `seedMode === "demo"` | Unit test |
| FR-3 | Two distinct `learnerId`s → skill_state/miss reads do not cross-leak (repo already filters; unit with two seeded ids) | Unit test |
| FR-4 | Authenticated pages call engine with `learnerId === user.id` (mock identity context), not `"Garvit"` | Unit / RTL of page or hook |
| FR-5 | DisplayName = firstName → email local-part → `"Learner"`; greeting VM contains that name, never `"Garvit"` | Unit (`resolve` + greeting/dashboard) |
| FR-6 | Zero `const LEARNER_ID = "Garvit"` (or `LEARNER_DISPLAY_NAME`) under `frontend/app/(coach)/learn/**` and coach panel defaults | `rg` gate in unit/arch test or task DoD paste |
| FR-7 | `seedMode=fresh` path inserts skills + bank but **zero** rows from `DEV_SKILL_STATES` / accuracy sessions | Unit on composition/seed |
| FR-8 | Fresh learner + empty skill states → dashboard/progress honest empty (no demo 28% punc focus) | Unit / component |
| FR-9 | `e2e/learn/**` untouched; `@t3` authed: greeting ⊈ `"Garvit"`; demo focus slate absent | `git diff` + Playwright paste |
| FR-10 | Coach/engine path uses session `learnerId` (= WorkOS id); no hardcoded Garvit on send/assemble | Unit (`use_coach` / panel) |
| FR-11 | D3 verify-fail still 503; no code path substitutes `"Garvit"` to recover | Existing middleware test + assert no new fallback |

All eleven collapse to L1 unit/rg, existing pytest, or on-demand `@t3` → **no unmeasurable criterion**; proceed.

---

## Block 0 — Branch + decisions intent

- **T0.1** — Create/confirm feature branch for this increment.
  - Cmd: `git status -sb`; branch e.g. `feat/eng-coach-workos-learner-identity` from agreed tip.
  - Verifies: clean implement home.
  - Pass: branch recorded. Fail: implement on dirty unrelated WIP without park.
  - deps: none.

- **T0.2 [P]** — Append `docs/adr/decisions.md` intent (2–4 lines).
  - Content: RSC `LearnIdentityProvider` + `seedMode` gate; FE `learnerId` = WorkOS `user.id`; registry binding = align to JWT sub + existing D3 (no new registry service); Q-C3/Q-C5 locked.
  - Verifies: Ask-first auth-boundary debt captured.
  - Pass: entry present. Fail: silent ship with no intent note.
  - deps: T0.1.

---

## Block 1 — Identity resolver (failure paths first) `[red]`

- **T1.1 [red]** — `resolve_learn_identity` pure helper + tests.
  - File **NEW:** `frontend/lib/learn/resolve_learn_identity.ts`
  - File **NEW:** `frontend/lib/learn/resolve_learn_identity.test.ts`
  - API sketch:
    ```ts
    type SeedMode = "demo" | "fresh";
    type LearnIdentity = {
      learnerId: string;
      displayName: string;
      seedMode: SeedMode;
    };
    // WorkOS-shaped minimal user: { id, firstName?, email? }
    resolveLearnIdentity(args: {
      bypass: boolean;
      user: { id: string; firstName?: string | null; email?: string | null } | null;
    }): LearnIdentity
    ```
  - Behaviors:
    1. `bypass === true` → `{ learnerId: DEV_LEARNER_ID, displayName: "Garvit", seedMode: "demo" }` (ignore user).
    2. `bypass === false` && `user == null` → **throw** (or return never) — MUST NOT invent Garvit (**FR-1**).
    3. `bypass === false` && user → `learnerId: user.id`, `seedMode: "fresh"`, `displayName`: non-empty `firstName` else email local-part else `"Learner"`.
  - Red first: write FR-1/FR-2/FR-5 cases; watch FR-1 fail before implement.
  - Verifies: **FR-1, FR-2, FR-5**.
  - Pass: vitest green with pasted fail→pass evidence. Fail: authed-null returns Garvit.
  - deps: T0.1.

---

## Block 2 — Provider + layout bridge

- **T2.1** — `LearnIdentityProvider` + `useLearnIdentity`.
  - File **NEW:** `frontend/components/learn/LearnIdentityProvider.tsx` (+ `.test.tsx`)
  - Client context; `useLearnIdentity()` throws outside provider.
  - Verifies: **FR-6** seam.
  - Pass: render test with value; outside-provider throws. Fail: silent null default to Garvit.
  - deps: T1.1.

- **T2.2** — Wire `(coach)/layout.tsx` RSC → provider.
  - File: `frontend/app/(coach)/layout.tsx`
  - Bypass: `resolveLearnIdentity({ bypass: true, user: null })`.
  - Else: `const { user } = await withAuth({ ensureSignedIn: true })`; resolve with that user.
  - Wrap `children` in `<LearnIdentityProvider value={identity}>`.
  - Update `layout.test.tsx`: mock user with `id`/`firstName`; assert provider receives resolved identity (or snapshot call to resolve). Keep D0 `ensureSignedIn` assert.
  - Verifies: **FR-4, FR-5, FR-6**.
  - Pass: layout test green; no discarded `withAuth` user. Fail: still `await withAuth` without using user under non-bypass.
  - deps: T2.1.

---

## Block 3 — Seed split + composition gate `[red]`

- **T3.1 [red]** — Split taxonomy vs full demo corpus.
  - File: `frontend/lib/adapters/engine/_dev_seed.ts` (+ extend `_dev_seed.test.ts` if present, else new tests)
  - Add `seedDevTaxonomy(db)` → skills only (`DEV_SKILLS`).
  - `seedDevCorpus(db)` → call taxonomy + mastery + accuracy sessions (unchanged behavior for bypass/tests).
  - Verifies: **FR-7**.
  - Pass: taxonomy-only leaves skill_states empty for Garvit; full corpus still seeds states. Fail: taxonomy inserts `DEV_SKILL_STATES`.
  - deps: T0.1.

- **T3.2** — Gate `browserEngineAdapters` / `EngineProvider` on `seedMode`.
  - Files: `frontend/lib/composition_engine_browser.ts`, `frontend/app/engine-provider.tsx`
  - Mechanism (pick simplest that passes tests — plan latch or explicit `seedMode` arg before singleton):
    - `demo` → `seedDevCorpus` + bank + hints + lessons (current non-prod default for bypass).
    - `fresh` → `seedDevTaxonomy` + bank + hints + lessons (**no** mastery/accuracy).
    - `production` → empty substrate (unchanged).
  - `EngineProvider` reads `useLearnIdentity().seedMode` when `bag` omitted; must set latch **before** first `browserEngineAdapters()` call.
  - Export test-only `resetBrowserEngineSingleton()` if needed.
  - Verifies: **FR-2, FR-7, FR-8**.
  - Pass: unit proves fresh path has 0 `DEV_SKILL_STATES` rows; demo path retains them. Fail: authenticated/fresh still loads Garvit mastery.
  - deps: T3.1, T2.1.

- **T3.3 [P]** — Honest empty slate VM smoke.
  - File: extend `use_dashboard.test.ts` and/or progress translator test with empty skill states + real `learnerId`.
  - Assert: no fabricated 28% punctuation focus from missing states (honest empty / no-focus path per existing translators).
  - Verifies: **FR-8**.
  - Pass: empty corpus → empty/honest UI contract. Fail: test invents demo focus.
  - deps: T3.1.

---

## Block 4 — Rewire all live `/learn` + coach call sites

- **T4.1** — Replace page-level Garvit constants.
  - Files:
    - `frontend/app/(coach)/learn/page.tsx`
    - `frontend/app/(coach)/learn/skill/page.tsx`
    - `frontend/app/(coach)/learn/quiz/page.tsx`
    - `frontend/app/(coach)/learn/coach/page.tsx`
    - `frontend/app/(coach)/learn/summary/page.tsx`
    - `frontend/app/(coach)/learn/progress/page.tsx`
  - Pattern: `const { learnerId, displayName } = useLearnIdentity();` pass into loaders.
  - Verifies: **FR-4, FR-5, FR-6**.
  - Pass: `rg 'LEARNER_ID = "Garvit"|LEARNER_DISPLAY_NAME = "Garvit"' frontend/app/(coach)/learn` → 0 matches. Fail: any page still hardcodes.
  - deps: T2.2, T3.2.

- **T4.2** — Coach hook + panel.
  - Files: `frontend/components/coach/use_coach.ts`, `frontend/components/coach/CoachPanel.tsx`
  - Remove module-level `const LEARNER_ID = "Garvit"`; default from `useLearnIdentity()` or require explicit `learnerId` from parent page (page already has identity).
  - Verifies: **FR-4, FR-6, FR-10**.
  - Pass: coach tests updated; no Garvit default in production path. Fail: `opts.learnerId ?? "Garvit"`.
  - deps: T4.1.

- **T4.3 [P]** — FR-3 cross-learner isolation smoke (if not already covered by repo tests).
  - Seed two learners’ skill states; assert reads by id B never return A’s mastery.
  - Verifies: **FR-3**.
  - Pass: unit green. Fail: global/unscoped read.
  - deps: T3.1.

---

## Block 5 — Registry binding regression (FR-10 / FR-11)

- **T5.1 [P]** — Frontend: coach path never substitutes Garvit when identity present.
  - Extend `use_coach.test.ts` / surface test: mock identity `learnerId: "user_workos_1"`; assert assemble/send uses that id.
  - Verifies: **FR-10**.
  - Pass: expect called with `user_workos_1`. Fail: still `"Garvit"`.
  - deps: T4.2.

- **T5.2 [P]** — Middleware/BFF: confirm D3 fail-closed + no Garvit recovery.
  - Prefer **reuse** existing D3 pytest (verify false → 503). Add assert only if missing: reject path must not rewrite owner/learner to `"Garvit"`.
  - BFF marker/stream tests already use server `sub` — add one expect that subject ≠ client-supplied Garvit when session is `user_workos_1` (may already exist; strengthen if weak).
  - Verifies: **FR-11** (+ FR-10 server side).
  - Pass: pytest/vitest green; pasted output. Fail: new fallback to demo learner.
  - deps: T0.1.

---

## Block 6 — Authenticated @t3 + learn-e2e integrity

- **T6.1** — Extend `coach-workos-local.spec.ts`.
  - File: `frontend/e2e/full-stack/coach-workos-local.spec.ts`
  - New test(s) under existing skip gates (`BYPASS` / `MOCK_MW` / `!AUTHENTICATED`):
    1. `/learn` greeting (`dashboard-greeting` or equivalent) **does not** contain `"Garvit"`.
    2. Demo slate absent: e.g. no focus copy that only the 28% Garvit seed would produce — prefer asserting mastery/focus empty-state **or** that punctuation focus banner is absent when no attempts (match FR-8 UI). Keep structural, not LLM.
  - Verifies: **FR-9** (Q-C4-A).
  - Pass: test authored; run under `E2E_AUTHENTICATED=1` when stack up (paste). Fail: asserts exact WorkOS firstName (fragile) without ≠Garvit.
  - deps: T4.1, T3.2.

- **T6.2 [P]** — FR-9 learn-e2e non-touch proof.
  - Cmd: `git diff origin/main -- frontend/e2e/learn` (or merge-base) → empty / docs-only.
  - Spot-check bypass still documents Garvit in `_dev_seed` for learn-e2e.
  - Verifies: **FR-9**.
  - Pass: 0 byte product diff under `e2e/learn`. Fail: suite rewritten to require WorkOS.
  - deps: T4.1.

---

## Block 7 — Gate + DoD evidence

- **T7.1** — Frontend unit gate for touched files.
  - Cmd: vitest on new/changed tests (`resolve_learn_identity`, provider, seed, layout, coach, dashboard).
  - Verifies: FR-1…FR-8, FR-10 unit slice.
  - Pass: pasted green output (and earlier red for T1.1/T3.1). Fail: skip without `G8-OK`/`env-gated`.
  - deps: T1–T5.

- **T7.2** — Architecture / `make check` as applicable.
  - At minimum: frontend typecheck/lint for touched files; `pytest tests/architecture/ -q` if any Python touched (T5.2).
  - Verifies: constitution.
  - Pass: green paste. Fail: invariant break.
  - deps: T7.1.

- **T7.3** — Manual smoke (operator).
  - WorkOS sign-in → `/learn`: name ≠ Garvit; progress not demo 28% focus.
  - `E2E_BYPASS_AUTH=1` → Garvit demo still works.
  - Verifies: FR-4,5,7,8 end-to-end.
  - Pass: checklist ticks in PR/notes. Fail: signed-in still Garvit.
  - deps: T4.1, T3.2.

- **T7.4** — Status hygiene on spec/plan/tasks → Stage 6 DONE when evidence pasted.
  - deps: T6.1, T7.1–T7.3.

---

## Task order (dependencies)

```
T0.1 ─┬─ T0.2[P]
      ├─ T1.1[red] → T2.1 → T2.2 ─┐
      ├─ T3.1[red] → T3.2 ────────┼─ T4.1 → T4.2 → T5.1[P]
      │            └─ T3.3[P] ────┤         └─ T6.1 → T7.*
      └─ T5.2[P] ─────────────────┘
         T4.3[P] (after T3.1)
         T6.2[P] (after T4.1)
```

**Parallel:** T0.2 ∥ T1.1; T3.1 ∥ T1.1; T3.3 ∥ T3.2 (after T3.1); T5.1 ∥ T5.2; T6.2 ∥ T6.1 after pages.

---

## Definition of Done

- [x] All tasks Pass criteria met; red-first evidence for T1.1 and T3.1 pasted
  - T1.1 red: `Cannot find module './resolve_learn_identity'` → green 5/5
  - T3.1: `_dev_seed.test.ts` taxonomy-empty / corpus-full green
- [x] `rg` shows no live-page Garvit `LEARNER_ID` under `(coach)/learn` (+ gate test)
- [x] Fresh seed has no `DEV_SKILL_STATES` / accuracy sessions (`seedmode.test.ts`)
- [x] `@t3` greeting ≠ Garvit authored in `coach-workos-local.spec.ts` (env-gated; run with live stack)
- [x] `decisions.md` entry present (2026-07-14 learn-identity RSC bridge)
- [x] learn-e2e path untouched (`git diff origin/main -- frontend/e2e/learn` = 0 bytes)
- [x] Stage 4 analyze CRITICAL=0 before claiming implement-ready

---

**Next gate:** Stage 7 **code-review** · optional live `@t3` / manual smoke · Stage 9 **sdd-converge**.
