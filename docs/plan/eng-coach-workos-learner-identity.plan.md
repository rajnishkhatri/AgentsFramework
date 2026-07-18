---
type: plan
title: "Eng Coach WorkOS learner identity + fresh progress slate — implementation plan"
description: >-
  Shared learn-identity RSC bridge (user.id + firstName fallbacks), replace
  seven Garvit LEARNER_ID constants, gate seedDevCorpus mastery/accuracy to
  bypass-only, keep taxonomy+bank for authenticated fresh slate, assert
  coach/AgentFacts path uses session sub (existing D3), add @t3 greeting≠Garvit.
  Clarify: Q-C1=A Q-C2=A Q-C3=A Q-C4=A Q-C5=A. ADR/decisions.md for auth seam.
status: "Stage 6 DONE 2026-07-14 — unit evidence green — await @t3 live + Stage 7/9"
authored: 2026-07-14
---

# Plan — Eng Coach WorkOS learner identity + fresh progress slate

**Status:** Stage 6 DONE 2026-07-14 — unit evidence green — await `@t3` live + Stage 7/9

**Spec:** [eng-coach-workos-learner-identity.spec.md](eng-coach-workos-learner-identity.spec.md)
**Tasks:** [eng-coach-workos-learner-identity.tasks.md](eng-coach-workos-learner-identity.tasks.md)
**Constitution:** root `AGENTS.md` + `frontend/AGENTS.md` + STYLE_GUIDE_FRONTEND §16
**Locked clarify:** Q-C1=A (registry binding in scope) · Q-C2=A (RSC firstName bridge) · Q-C3=A (in-memory) · Q-C4=A (@t3) · Q-C5=A (no SEED_GARVIT)

---

## 1. Architecture

```
  (coach)/layout.tsx  [RSC]
       │  withAuth({ ensureSignedIn: true })  OR  E2E_BYPASS_AUTH
       │  resolveLearnIdentity():
       │    authed → { learnerId: user.id, displayName: firstName|emailLocal|"Learner", seedMode: "fresh" }
       │    bypass → { learnerId: DEV_LEARNER_ID, displayName: "Garvit", seedMode: "demo" }
       ▼
  <LearnIdentityProvider value={…}>   [client, thin context]
       ▼
  learn/layout.tsx → <EngineProvider seedMode=…>  [reads identity; builds bag once]
       │
       ├─ seedMode=demo  → seedDevCorpus (skills+mastery+accuracy) + bank
       └─ seedMode=fresh → seed skills taxonomy ONLY + bank (+ lessons/hints)
                           NO DEV_SKILL_STATES / NO accuracy sessions
       ▼
  /learn/* pages → useLearnIdentity() → learnerId + displayName
       (delete every const LEARNER_ID = "Garvit")
       ▼
  Coach ask / engine writes keyed by session learnerId
       ▼
  BFF getSession().sub + middleware _coach_run_identity(claims.subject)
       + D3 registry.verify(subject-coach-english)   ← FR-10/11 (already on main;
         this plan wires FE learnerId to the same subject and adds regression tests)
```

**A1 simplest machinery:**
- One RSC resolver + one client context (`LearnIdentityProvider` / `useLearnIdentity`)
- Split seed helper: `seedDevTaxonomy` vs full `seedDevCorpus` (demo)
- No new port, no `IdentityClaim` widening, no durable DB, no new npm/py dependency

**G1 — rejected alternatives:**
| Idea | Why rejected |
|------|----------------|
| Widen `IdentityClaim` with `firstName` | Q-C2-A; chat already uses RSC `user`; claim stays JWT-narrow |
| Per-page `withAuth` + pass props | Seven sites drift; F5 called this out — one seam |
| `SEED_GARVIT=1` for signed-in demos | Q-C5-A |
| Durable IndexedDB/SQLite this PR | Q-C3-A |
| New AgentFacts registry service | Card + verify already exist (D3); bind by aligning FE `learnerId` to JWT `sub` |

**Ask-first / intent debt:** auth-boundary consumption into `/learn` → append short `docs/adr/decisions.md` entry (why RSC context + seedMode gate; not a full ADR unless review asks). No `trust/models.py` change → no re-signing.

---

## 2. File-level touchpoints

| # | File | Change | FR |
|---|------|--------|-----|
| 1 | `frontend/lib/learn/resolve_learn_identity.ts` **[NEW]** (+ unit test) | Pure: `(user \| null, bypass) → LearnIdentity`. DisplayName: firstName → email local-part → `"Learner"`. Bypass → Garvit/`demo`. Authed without user → must not invent Garvit (throw or unreachable after D0). | FR-1,2,4,5 |
| 2 | `frontend/components/learn/LearnIdentityProvider.tsx` **[NEW]** (+ test) | Client context + `useLearnIdentity()`. | FR-6 |
| 3 | `frontend/app/(coach)/layout.tsx` | Capture `withAuth` user (or bypass); wrap children in `LearnIdentityProvider`. | FR-4,5,6 |
| 4 | `frontend/lib/adapters/engine/_dev_seed.ts` | Export `seedDevTaxonomy(db)` (skills only). Keep `seedDevCorpus` = taxonomy + mastery + accuracy for bypass/tests. | FR-7,8 |
| 5 | `frontend/lib/composition_engine_browser.ts` | Accept seed mode (param or module latch set before first `browserEngineAdapters()` call). `fresh` → taxonomy+bank; `demo` → full corpus+bank; prod unchanged empty. Reset singleton in tests if needed. | FR-7,2 |
| 6 | `frontend/app/engine-provider.tsx` | Read `useLearnIdentity().seedMode` (or prop from layout) when constructing default bag. | FR-7 |
| 7 | `frontend/app/(coach)/learn/{page,skill,quiz,coach,summary,progress}/page.tsx` | Replace `LEARNER_ID` / `LEARNER_DISPLAY_NAME` with `useLearnIdentity()`. | FR-4,5,6 |
| 8 | `frontend/components/coach/use_coach.ts` + `CoachPanel.tsx` | Remove hardcoded `LEARNER_ID`; use identity seam / opts required from parent. | FR-4,6,10 |
| 9 | Coach path regression | Unit/BFF test: authenticated coach context / marker uses session `sub`, never `"Garvit"`; D3 verify-fail still 503 with no demo-learner fallback (existing tests + one explicit “no Garvit” assert). | FR-10,11 |
| 10 | `frontend/e2e/full-stack/coach-workos-local.spec.ts` | Add FR-5/FR-8 @t3: greeting text does not contain `"Garvit"`; today-focus / mastery not demo 28% punctuation slate (honest empty or non-Garvit). Skip rules unchanged. | FR-9 |
| 11 | `docs/adr/decisions.md` | 2–4 lines: learn-identity RSC bridge + seedMode gate; registry binding = align FE learnerId to JWT sub + existing D3. | — |
| 12 | Spec/plan/tasks status hygiene | After implement. | — |

**Explicit non-touchpoints:**
- `frontend/e2e/learn/**` oracles under bypass (FR-9)
- `IdentityClaim` / `workos_authkit_adapter` session shape
- Durable EngineDb / Neon progress
- New AgentFacts registration API (reuse `register_subject_coach` / D3)

**learn-e2e coupling:** bypass still `seedMode=demo` + `DEV_LEARNER_ID` so existing Garvit assertions keep working without rewriting the suite.

---

## 3. Spec design → seams

| FR | Seam |
|----|------|
| FR-1 | `resolve_learn_identity` refuses Garvit when `!bypass && !user` |
| FR-2 | bypass → demo identity + `seedDevCorpus` |
| FR-3 | distinct `learnerId`s; engine repos already filter by id — smoke unit with two ids |
| FR-4/5/6 | Provider + page rewires |
| FR-7/8 | `seedDevTaxonomy` path + empty dashboard/progress VM |
| FR-9 | @t3 + untouched learn-e2e |
| FR-10/11 | FE learnerId = `user.id`; middleware owner = JWT subject; verify fail-closed unchanged |

---

## 4. Constitution check

| Invariant | Status |
|-----------|--------|
| Python #1–#8 | Untouched (optional pytest assert only if we touch middleware — prefer not) |
| Frontend authZ server-side | D0 + BFF `getSession` unchanged; client identity is for engine keys / display only |
| No new dependency | Yes |
| Ask-first | `decisions.md` (not full ADR unless ratchet requires) |
| G8 | Renaming/removing `LEARNER_ID` locals is fine; do not delete learn-e2e `test_*` without waiver |

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| Engine singleton seeded before identity mounts | Provider sets seed latch **synchronously** before `browserEngineAdapters()`; unit-test order; or pass `bag` from a child that builds once with known mode |
| Empty slate breaks quiz (`no reviewed question`) | Fresh path still seeds governed bank + skills; quiz openItem uses bank — verify with unit/smoke |
| learn-e2e expects Garvit greeting | Bypass keeps demo mode |
| FR-10 over-scoped as “new registry” | Plan scopes to subject alignment + regression; document in decisions.md |
| Soft nav remount reseeds empty | Singleton preserves in-tab progress (Q-C3-A ephemeral across full reload only) |

---

## 6. Migration / rollout

1. Land identity seam + seed split behind same PR (atomic — partial land = mixed Garvit/user ids).
2. Manual: WorkOS sign-in → greeting uses firstName; dashboard not 28% punc focus.
3. Bypass: `E2E_BYPASS_AUTH=1` → Garvit demo unchanged.
4. Run `pnpm test` (touched) + `test:e2e:coach-workos` + sample learn-e2e under bypass.
5. No feature flag beyond existing bypass.

---

## 7. Definition of Done (plan-level)

- [ ] Spec FRs 1–11 mapped to tasks with red/green tests
- [ ] No live-page `const LEARNER_ID = "Garvit"` under `(coach)/learn`
- [ ] Authenticated seed ≠ `DEV_SKILL_STATES` / accuracy sessions
- [ ] @t3 greeting ≠ Garvit pasted
- [ ] `decisions.md` entry present
- [ ] Stage 4 analyze CRITICAL=0 before implement

---

**Next gate:** human **approve** this plan → Stage 3 tasks checklist.
