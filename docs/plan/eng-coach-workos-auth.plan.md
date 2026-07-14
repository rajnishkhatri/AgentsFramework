---
type: plan
title: "Eng Coach WorkOS auth: D0 page-guard + D3 verify-before-execute & audit — implementation plan"
description: Architecture + 7 file-level touchpoints (T1 new (coach)/layout.tsx server guard + tests; T4/T5 mirrored verify-gate in app_prod.py & __main__.py; T6 pytest extension; T7 decisions.md). Two independent vertical slices (D0 frontend, D3 middleware), no shared new code; no ADR trigger; risks R1 native-flow / R2 __main__ drift / R3 first-request 503.
status: "Draft 2026-07-13"
authored: 2026-07-13
---

# Plan — Eng Coach WorkOS auth: D0 page-guard + D3 verify-before-execute & audit

**Status:** Draft — 2026-07-13
**Spec:** [eng-coach-workos-auth.spec.md](eng-coach-workos-auth.spec.md) (FR-1…FR-7)
**Constitution:** root `AGENTS.md` (8 invariants) + `frontend/AGENTS.md` (F/W/P/A/T/X/C/B/U/S rules)

---

## 1. Architecture

Two independent vertical slices on one substrate; no shared new code between them.

**D0 (frontend, browser+BFF ring):** a new **RSC layout** at the `(coach)` route-group
root guards every page under it. It is a composition-adapter-style boundary (Rule B2:
Server passes Client as `children`): the server layout awaits `withAuth({ ensureSignedIn:
true })` (WorkOS SDK, already used at `app/page.tsx:44`) and renders the existing
`'use client'` `learn/layout.tsx` shell as `children`. No `'use client'` moves; the shell
is untouched. SDK import sits at the RSC page/layout boundary (same placement as
`page.tsx`), not in `lib/` — consistent with existing repo practice.

**D3 (middleware, credentialed ring):** an additive **verify-gate** in the coach branch
of `/run/stream`. Today: `agent_id == SUBJECT_COACH_AGENT_ID` → seed/read card via
`_coach_run_identity` → dispatch. New: after lazy-seed, call
`registry.verify(SUBJECT_COACH_AGENT_ID)`; `False` → `HTTPException(503)` (fail-closed,
matching the `coach_runtime is None → 503` idiom two lines up); `True` → dispatch + emit
a structured audit `logger.info`. The plain-chat `else` branch is untouched (FR-7). The
same gate is mirrored into `middleware/__main__.py` (drift guard).

```
D0:  browser → (coach)/layout.tsx [NEW server RSC]
                 └─ await withAuth({ ensureSignedIn:true })   ── unauth → redirect (FR-1)
                 └─ <learn/layout.tsx (existing client shell)>{children}</>  (FR-2/FR-3)

D3:  /run/stream  (app_prod.py + __main__.py)
       if agent_id == SUBJECT_COACH_AGENT_ID:
          if coach_runtime is None: 503                     (existing)
          identity = _coach_run_identity(subject)           (seeds card)
          if not registry.verify(SUBJECT_COACH_AGENT_ID): 503   ── NEW (FR-4)
          logger.info(audit: subject, agent_id, verified, trace_id)  ── NEW (FR-6)
          → dispatch                                        (FR-5)
       else: … unchanged …                                  (FR-7)
```

## 2. File-level touchpoints

| # | File | Change | FR | Layer / rule |
|---|------|--------|-----|--------------|
| T1 | `frontend/app/(coach)/layout.tsx` **[NEW]** | RSC layout: `export const dynamic="force-dynamic"`; `await withAuth({ ensureSignedIn:true })`; return `{children}`. | FR-1,2,3 | B1/B2, F-R4 |
| T2 | `frontend/app/(coach)/layout.test.tsx` **[NEW]** | Vitest: mock `withAuth`; assert (a) called with `{ensureSignedIn:true}`, (b) renders children when authed. | FR-1,2,3 | §20 L1 |
| T3 | `frontend/e2e/learn/*.spec.ts` (new or extend) | Playwright: no-session request to `/learn` + `/learn/coach` → redirected to sign-in, coach content absent. | FR-1 | §20 L4 |
| T4 | `middleware/app_prod.py` (coach branch of `/run/stream`, ~L628-636 + `_coach_run_identity` L586) | Add `registry.verify(SUBJECT_COACH_AGENT_ID)` gate (503 on False) after seed; add audit `logger.info`. | FR-4,5,6,7 | fail-closed idiom, O2 |
| T5 | `middleware/__main__.py` (mirrored coach seam ~L557-575) | Same verify-gate + audit line (drift guard — MUST match T4). | FR-4,5,6,7 | prod-surface drift |
| T6 | `tests/middleware/test_coach_shadow_wiring.py` (extend) | pytest: unverified card → 503 (FR-4, failure first); verified → dispatch (FR-5); audit line + no-PII (FR-6); chat path no verify/no audit (FR-7). | FR-4-7 | §20 L1 |
| T7 | `docs/adr/decisions.md` (append) | 2–4 line note: "D3 verifies the coach **card's** agent_id (`SUBJECT_COACH_AGENT_ID`), not the learner subject — the signed artifact is the card; the subject is auto-provisioned and not integrity-relevant." | — | decisions.md |

**Native-flow check (Q-C2):** part of T3 — a manual/Playwright pass confirming the Tauri
+ iOS deep-link sign-in still completes with `ensureSignedIn` active. Not a code
touchpoint unless it breaks (then: scope the guard by native UA in T1).

## 3. Migration / rollout

No data migration, no schema change, no dependency add. D0 is one new file + tests;
D3 is an additive guard + log line in two files + tests. Both independently revertible.
Ship order: D3 first (backend-only, no UX surface), then D0 (needs the frontend e2e +
native check). Or parallel — they share no code.

## 4. Constitution check (⚠️ Ask-first triggers?)

- New dependency? **No** — `@workos-inc/authkit-nextjs` and `AgentFactsRegistry.verify`
  both already present.
- Trust-kernel type change / re-signing? **No** — D3 *reads* the signed card via the
  existing `verify()`; it changes no `trust/models.py` type.
- New graph node / horizontal service / abstraction? **No** — D0 is a layout; D3 is an
  inline guard on an existing endpoint.
- **⇒ No ADR trigger.** One `decisions.md` line for the verify-target choice (T7).

## 5. Risks

- **R1 — `ensureSignedIn` breaks native sign-in** (Q-C2). Mitigation: T3 native check
  before merge; fallback = scope guard by native UA.
- **R2 — T4/T5 drift** (the standing hazard). Mitigation: identical gate + a T6 test
  asserting the `__main__.py` seam 503s on unverified card, same as `app_prod.py`.
- **R3 — first-request spurious 503** if verify runs before lazy-seed. Mitigation:
  order is seed (`_coach_run_identity`) **then** verify — encoded in T4 and its test.

---

## 6. Convergence deferrals (Stage 9 · 2026-07-13)

Logged here until `docs/adr/tech-debt-tracker.md` exists (runbook § Stage 9).

- **Q-C2 live native smoke** — deferred pending human accept of the structural `/api/auth/*` check vs a device/WebView pass (plan risk R1).
- **`E2E_BYPASS_AUTH` in `(coach)/layout.tsx`** — `unrequested` vs spec; mirrors `app/page.tsx`. Spec it on replan if reviewers want it explicit.
- **CI architecture job shallow checkout** — G8 can skip when merge-base is unavailable; local full-history run is the honest G8 signal for this PR (P1-1). Out of this change's code scope.
