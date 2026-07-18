---
type: spec
title: "Eng Coach WorkOS learner identity + fresh progress slate"
description: >-
  EARS spec for deriving learnerId/displayName from the signed-in WorkOS user
  on /learn/* (replacing hardcoded Garvit), and seeding taxonomy/bank without
  Garvit mastery/accuracy so each signed-in user starts on a fresh slate.
  Clarify pass OPEN. Builds on D0 page guard (eng-coach-workos-auth) and parked
  follow-up F5 (preact-learn-followups.notes.md).
status: "Stage 6 DONE 2026-07-14 — unit evidence green — await @t3 live + Stage 7/9"
authored: 2026-07-14
---

# Spec — Eng Coach WorkOS learner identity + fresh progress slate

**Status:** Stage 6 DONE 2026-07-14 — unit evidence green — await `@t3` live + Stage 7/9
**Owner:** Rajnish Khatri
**Related:**
- [preact-learn-followups.notes.md](preact-learn-followups.notes.md) §F5 (parked identity work)
- [eng-coach-workos-auth.spec.md](eng-coach-workos-auth.spec.md) (D0 page guard — CONVERGED)
- [eng-coach-workos-manual-walkthrough.md](eng-coach-workos-manual-walkthrough.md) (manual findings that triggered this)

**Clarify decisions:**
- **Q-C1 — Agent registry:** **A — IN SCOPE.** This increment includes learner↔coach
  AgentFacts / registry binding FRs (not deferred). Identity + fresh slate still
  ship; registry is an additional FR block, not a substitute.
- **Q-C2 — Display name:** **A — RSC bridge.** `(coach)` layout reads
  `withAuth().user`, derives `displayName` as `firstName` → email local-part →
  `"Learner"`, and passes `{ learnerId: user.id, displayName }` into a
  learn-identity context. `IdentityClaim` stays unchanged (no `firstName`).
- **Q-C3 — Persistence:** **A — in-memory only.** Authenticated path seeds
  taxonomy + bank (no Garvit mastery/accuracy). Progress remains ephemeral
  for the tab/session (existing `InMemoryEngineDb`). Durable per-user store
  is out of scope.
- **Q-C4 — Authenticated Playwright:** **A — add `@t3`.** Extend the WorkOS
  local suite (`E2E_AUTHENTICATED=1`) to assert greeting ≠ `"Garvit"` and
  that the demo punctuation-at-28% focus slate is absent for the signed-in user.
- **Q-C5 — Signed-in demo seed:** **A — no opt-in.** Authenticated ⇒ always
  fresh slate (taxonomy+bank only). Garvit demo corpus only under
  `E2E_BYPASS_AUTH=1` / e2e seed override. No `SEED_GARVIT=1`.

**Clarify pass:** CLOSED 2026-07-14 (Q-C1…Q-C5). Plan APPROVED. Stage 3 tasks drafted.

---

## 1. Goal

After WorkOS sign-in, every `/learn/*` surface SHALL greet and key progress to
**the signed-in user**, not the hardcoded demo learner `"Garvit"`. A newly
signed-in learner SHALL see a **fresh progress slate** (no demo mastery bars /
fake accuracy history). Demo seed remains available only for unauthenticated
dev/bypass and seeded learn-e2e.

## 2. Context

**Confirmed defects (manual validation 2026-07-14 + code audit):**

1. **Hardcoded identity.** Seven+ `/learn` entry points set
   `const LEARNER_ID = "Garvit"` and (on the dashboard)
   `LEARNER_DISPLAY_NAME = "Garvit"` —
   e.g. [`learn/page.tsx`](../../frontend/app/(coach)/learn/page.tsx).
2. **Guard discards user.** `(coach)/layout.tsx` awaits
   `withAuth({ ensureSignedIn: true })` but does not pass `user` into the
   tree; chat landing already uses `user.firstName` /
   `user.email` ([`app/page.tsx`](../../frontend/app/page.tsx)).
3. **Demo progress seed.** Non-prod `browserEngineAdapters()` calls
   `seedDevCorpus()` which writes Garvit mastery + ≥6 accuracy sessions
   ([`_dev_seed.ts`](../../frontend/lib/adapters/engine/_dev_seed.ts),
   [`composition_engine_browser.ts`](../../frontend/lib/composition_engine_browser.ts)).
   Reads under `"Garvit"` therefore always show that slate — even after a
   real WorkOS login.

**Prior parking:** F5 in follow-ups notes called this out as cross-cutting
(shared seam + Ask-first auth boundary + optional agent-registry second
deliverable). D0 shipped the page guard only; identity consumption was deferred.
This spec is the F5 *learner-identity + fresh-slate* slice; agent-registry
binding is a clarify question (Q-C1).

**Constraints:**
- No new pyproject dependency expected.
- `IdentityClaim` today is `{ sub, org_id, roles, email }` — no `firstName`.
  Display-name source is a clarify question (Q-C2).
- Engine substrate in browser remains `InMemoryEngineDb` for this increment
  (durable per-user SQLite/Neon is out of scope unless clarify expands it).
- learn-e2e (`E2E_BYPASS_AUTH=1`) must keep a deterministic Garvit/seeded path.

## 3. Functional requirements (EARS)

**Failure paths first**

- **FR-1.** IF a `/learn/*` page would render learner-keyed UI **without** a
  resolvable learner identity (no WorkOS session and bypass not active) THEN
  THE SYSTEM SHALL NOT fabricate `"Garvit"` as that identity; the existing D0
  redirect / bypass rules SHALL apply instead.
- **FR-2.** IF `E2E_BYPASS_AUTH=1` (non-production) THEN THE SYSTEM SHALL
  continue to use the demo learner identity (`DEV_LEARNER_ID` / `"Garvit"`)
  and the demo progress corpus so seeded learn-e2e stays deterministic.
- **FR-3.** IF two different WorkOS users sign in on the same browser profile
  in sequence (same in-memory engine process) THEN THE SYSTEM SHALL NOT show
  user A's mastery/attempts under user B's greeting (reads SHALL key by the
  active `learnerId`).

**Identity**

- **FR-4.** WHEN an authenticated WorkOS session is present on a `/learn/*`
  page THEN THE SYSTEM SHALL use a stable learner id derived from the WorkOS
  user subject (`user.id` / claim `sub`) for all engine reads/writes on that
  page (dashboard, skill, quiz, coach, summary, progress, coach panel).
- **FR-5.** WHEN an authenticated WorkOS session is present THEN THE SYSTEM
  SHALL render the dashboard greeting `displayName` from WorkOS
  `user.firstName`, falling back to the email local-part, then `"Learner"` —
  never the literal `"Garvit"`. Source is the RSC learn-identity bridge
  (Q-C2-A); `IdentityClaim` is not widened.
- **FR-6.** THE SYSTEM SHALL resolve learner identity through **one shared
  seam** (not seven independent `const LEARNER_ID = "Garvit"` copies) so all
  `/learn/*` surfaces cannot drift.

**Fresh slate**

- **FR-7.** WHEN an authenticated WorkOS user (not bypass) loads the browser
  engine THEN THE SYSTEM SHALL seed **taxonomy + governed item bank** (and
  lesson/hint banks as today) but SHALL NOT seed Garvit demo mastery rows or
  Garvit demo accuracy sessions for that user.
- **FR-8.** WHEN an authenticated WorkOS user with no prior attempts views
  dashboard / progress THEN THE SYSTEM SHALL present an honest empty / zero
  progress state (no fake focus from demo punctuation-at-28%), until real
  practice writes skill state.

**Integrity / non-goals (this increment)**

- **FR-9.** THE SYSTEM SHALL leave `frontend/e2e/learn/**` oracle behavior
  intact under bypass (no wholesale rewrite of learn-e2e to WorkOS subjects
  in this increment). WHERE `E2E_AUTHENTICATED=1` THE SYSTEM SHALL also
  provide `@t3` coverage that the authenticated greeting is not `"Garvit"`
  and the demo Garvit mastery focus slate is absent (Q-C4-A).
- **FR-10.** WHEN an authenticated learner starts a coach run THEN THE SYSTEM
  SHALL bind the run to the registered subject-coach AgentFacts identity
  (existing `subject-coach-english` card / verify-before-execute path) such that
  the learner subject from WorkOS and the coach agent id are both present on
  the audited run identity — no anonymous or Garvit-substituted learner on the
  coach path.
- **FR-11.** IF the coach AgentFacts card is missing / non-ACTIVE / fails
  verify THEN THE SYSTEM SHALL fail closed (existing D3 503 behavior) and SHALL
  NOT fall back to a demo learner id to “make the run work.”

## 4. Data model / contracts

| Concept | Source today | Target |
|---------|--------------|--------|
| `learnerId` (engine key) | literal `"Garvit"` | WorkOS `user.id` / `IdentityClaim.sub` when authenticated; `DEV_LEARNER_ID` under bypass |
| `displayName` (greeting) | literal `"Garvit"` | WorkOS profile field(s) per Q-C2; bypass keeps `"Garvit"` |
| Demo mastery / accuracy | always `seedDevCorpus()` in non-prod | only under bypass / explicit e2e seed override; authenticated path = skills+bank only |
| `IdentityClaim` | `sub, org_id, roles, email` | may gain optional `firstName` / `displayName` **or** RSC may pass display name via a learn-identity context without widening the claim — decide in plan after Q-C2 |

No trust-kernel (`trust/models.py`) change expected → no re-signing. No new
horizontal service. Frontend Ring only (+ possible thin RSC prop bridge).

## 5. Invariants & security boundaries

| Invariant | How it holds |
|-----------|--------------|
| #1–#5 (Python layering) | Untouched — no orchestration/components/services/trust edits expected |
| Frontend Ring | Learner id for **display/engine keys** may be read client-side from a server-provided identity context; **authorization** remains server-side (D0 `withAuth`, BFF `getSession`) — STYLE_GUIDE_FRONTEND §16 |
| Secrets / live LLM in CI | Unchanged; FR-7 coach live turn stays out of `make check` |
| Ask-first | Crossing auth boundary into `/learn` identity consumption → **ADR or `decisions.md`** (why one shared seam; why demo seed gated) |

## 6. Edge cases

- WorkOS user with empty `firstName` and null email → defined fallback (Q-C2).
- `E2E_BYPASS_AUTH` set in production build → must remain impossible (existing double gate).
- Authenticated user + Playwright `__PREACT_E2E_SEED__` override → override still wins for corpus shape, but `learnerId` must still be the session subject (or document intentional exception).
- Soft navigation between `/learn` pages must not re-introduce a hardcoded Garvit constant.
- In-memory engine: refresh/reload loses in-tab progress (pre-existing); this increment does **not** invent durable storage unless Q-C3 expands scope.

## 7. Non-functional requirements

- Determinism: learn-e2e under bypass stays L1-stable (Garvit corpus).
- No new runtime dependency.
- Greeting change is synchronous with first paint of dashboard (RSC-provided identity preferred over a client round-trip).
- Reversibility: authenticated path never opts into Garvit seed (Q-C5-A); demos use `E2E_BYPASS_AUTH=1` only.

## 8. Test plan

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | Unit: identity seam refuses implicit Garvit when session absent & bypass off | L1 | yes |
| FR-2 | Unit/layout: bypass → `DEV_LEARNER_ID` + seed path | L1 | yes |
| FR-3 | Unit: skill_state / misses filtered by `learnerId` (already true at repo layer); identity seam returns distinct ids | L1 | yes |
| FR-4 | Unit: pages/hooks receive session `sub` (mock Auth / identity context) | L1 | yes |
| FR-5 | Unit: `toGreetingVM` / dashboard load with WorkOS displayName | L1 | yes |
| FR-6 | Architecture or unit: no `LEARNER_ID = "Garvit"` left in `(coach)/learn/**` live pages (allow `_dev_seed` + bypass) | L1 | yes |
| FR-7 | Unit: authenticated seed path does not insert `DEV_SKILL_STATES` / accuracy sessions | L1 | yes |
| FR-8 | Unit or component: empty skill states → honest empty dashboard/progress VM | L1 | yes |
| FR-9 | Existing learn-e2e green under bypass (regression); `@t3` greeting≠Garvit + no demo mastery slate | L2 e2e | no (on-demand) |
| FR-10 | Unit/integration: coach run identity carries WorkOS `sub` + `subject-coach-english` (no Garvit) | L1 | yes |
| FR-11 | Existing D3 reject path still fail-closed; no demo-learner fallback on verify fail | L1 | yes |

Failure-path tests (FR-1, FR-2, FR-7) before happy-path (FR-4, FR-5).

## 9. Definition of Done

- [ ] Clarify Q-C1…Q-C5 closed; plan + tasks approved; CRITICAL=0 analyze.
- [ ] All in-scope FRs implemented; each has a test seen to fail first.
- [ ] No live-page `const LEARNER_ID = "Garvit"` under `(coach)/learn` (bypass uses shared seam → `DEV_LEARNER_ID`).
- [ ] Authenticated local manual check: greeting ≠ `"Garvit"`; progress not demo 28% punctuation focus.
- [ ] `pnpm` frontend unit tests for touched files green; learn-e2e under bypass still green (pasted output).
- [ ] ADR or `decisions.md` entry for auth-boundary identity seam + seed gating.
- [ ] Actual command output pasted for verification claims.

---

## Clarify queue (ask one at a time)

| ID | Topic | Options (summary) | Recommended |
|----|-------|-------------------|-------------|
| Q-C1 | Agent registry / AgentFacts learner↔coach binding | A in-scope this PR · B defer (identity+slate only) | **B** |
| Q-C2 | Display-name source | A `firstName` (+email fallback) via RSC · B email local-part from `IdentityClaim` · C extend `IdentityClaim` | **A** |
| Q-C3 | Persistence of progress | A in-memory fresh each load (current substrate) · B durable per-user store this increment | **A** |
| Q-C4 | Authenticated Playwright assertion | A add `@t3` greeting≠Garvit · B manual + unit only this increment | **A** |
| Q-C5 | Local demo without WorkOS | A keep bypass/Garvit seed · B also `SEED_GARVIT=1` for signed-in demos | **A** |
