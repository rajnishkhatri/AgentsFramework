---
type: spec
title: "Eng Coach WorkOS auth: page-guard (D0) + verify-before-execute & audit (D3)"
description: EARS spec for the D0+D3 bundle — a server-side RSC withAuth guard on the (coach) route group so /learn/* pages no longer paint unauth (FR-1..3), plus a per-run coach-card verify-before-execute gate (fail-closed 503) with a no-PII audit line at the middleware coach seam (FR-4..7). Clarify pass CLOSED (Q-C1 group-root server layout / Q-C2 web-guard + native check / Q-C3 per-run verify). No new dependency, no ADR trigger.
status: "Stage 6 implement 2026-07-14 — Phase 1 P1-1..P1-4 green — next: sdd-converge"
authored: 2026-07-13
---

# Spec — Eng Coach WorkOS auth: page-guard (D0) + verify-before-execute & audit (D3)

**Status:** Stage 6 implement 2026-07-14 — D0+D3 shipped; Phase 1 residual gaps closed — next: sdd-converge
**Owner:** Rajnish Khatri
**Related:** [eng-coach-workos-auth.brainstorm.md](eng-coach-workos-auth.brainstorm.md) (SDD Stage-1, gate CLOSED: D0 scoped RSC guard + D3 bundled; D1/D2/D4 rejected/deferred)

**Clarify decisions (2026-07-13):**
- **Q-C1 — D0 guard site:** new **server** layout at `frontend/app/(coach)/layout.tsx`
  calling `withAuth({ ensureSignedIn: true })`, rendering the existing client
  `learn/layout.tsx` shell as `children` (Rule B2). One guard covers all pages under
  `(coach)` + future siblings. (Rejected: per-page guards, splitting the working client shell.)
- **Q-C2 — native flows:** ship the web guard; DoD is a **structural** check that
  `/api/auth/*` stays outside `(coach)` so deep-link completion is not blocked by the
  page guard. Live Tauri/iOS WebView smoke is deferred (tech debt), not merge-blocking.
  If a live native pass later dead-locks, scope the guard to exclude the native UA path.
- **Q-C3 — verify cadence:** verify the coach card **per coach run**
  (`registry.verify(SUBJECT_COACH_AGENT_ID)` on every coach request, after lazy-seed) —
  catches a card suspended/tampered mid-session; one HMAC check per run, coach path only.

**Stage-5 replan dispositions (2026-07-13) — approved; implemented 2026-07-14:**
- **P1-3:** FR-6 correlator = run `thread_id` (field name `thread=`), not domain
  `trace_id` — audit fires pre-stream; domain trace arrives later.
- **P1-4:** FR-6 keeps "verification result" on **both** accept and reject paths
  (`verified=True` / `verified=False`); reject does not stay silent.
- **E2E_BYPASS_AUTH:** explicit edge case (mirrors `app/page.tsx`); non-production only.

---

## 1. Goal

Close the one real auth gap in the Eng Coach: the `(coach)` route-group **pages**
(`/learn`, `/learn/coach`, `/learn/quiz`, …) currently render to an
**unauthenticated browser** because the group's only layout is a `'use client'`
shell with no server-side auth guard (the APIs already 401, but the UI paints).
**D0** adds a server-side `withAuth({ ensureSignedIn: true })` guard above that
shell. **D3** hardens the coach run seam: verify the signed coach card before
dispatching a coach run (fail-closed 503), and emit the identity resolution to
the audit trail. For learners using the coach; no behavior change for authenticated
users.

## 2. Context

Stage-1 premise audit ([brainstorm](eng-coach-workos-auth.brainstorm.md)) **refuted**
the "add auth from scratch" framing: the coach is already authenticated at the BFF
(routes 401) and the middleware (JWT verified, identity bound via the AgentFacts
registry). Two residual gaps remained:

- **D0 (page guard):** `frontend/app/(coach)/learn/layout.tsx:7` is `'use client'`
  (reads `useSurface`/`usePathname`) with no `withAuth()`. Seven pages under it paint
  pre-auth. The chat landing already gates correctly at `frontend/app/page.tsx:44`
  (`const { user } = await withAuth()`), giving the precedent D0 follows. AuthKit
  `2.17.0` supports `withAuth({ ensureSignedIn: true })` (redirects unauth → sign-in).
- **D3 (verify-before-execute + audit):** `_coach_run_identity` at
  `middleware/app_prod.py:586-599` seeds/reads the signed coach card from the
  AgentFactsRegistry but **never calls `registry.verify()`** before the coach graph
  runs — the AgentFacts "verify-before-execute" best practice is unused on this path.
  `verify(agent_id) -> bool` exists on both the in-memory and GCS registry variants
  (`agent_facts_registry.py:69`, `agent_facts_gcs_registry.py:80`) and returns
  `False` (never raises) on missing / non-ACTIVE / tampered / unsigned cards.

D2 (a real authZ *decision* / capability gate) was **dropped** — every signed-in
learner gets the coach; identity binding suffices. The "decouple coach into its own
app" idea was considered and **squashed** (keep coach in `app_prod.py`;
extract-before-split only if a real trigger fires).

## 3. Functional requirements (EARS)

**D0 — page guard (failure paths first)**

- **FR-1.** IF an **unauthenticated** browser requests any `(coach)` route-group page
  (`/learn` and every descendant) THEN THE SYSTEM SHALL redirect to the WorkOS
  sign-in flow and SHALL NOT render the coach shell or any learner content.
- **FR-2.** WHEN an **authenticated** user requests a `(coach)` page THE SYSTEM SHALL
  render the existing coach client shell unchanged (no visual/behavioral regression).
- **FR-3.** THE SYSTEM SHALL enforce FR-1 via a **single** server-side guard at the
  `(coach)` route-group root, so a newly added page under the group is protected
  without its own guard.

**D3 — verify-before-execute + audit (failure paths first)**

- **FR-4.** IF a coach run is requested (`body.agent_id == SUBJECT_COACH_AGENT_ID`)
  AND `registry.verify(SUBJECT_COACH_AGENT_ID)` returns `False` (missing / non-ACTIVE
  / tampered / unsigned signed card) THEN THE SYSTEM SHALL respond **503**
  ("coach identity unverified") and SHALL NOT dispatch the coach runtime.
- **FR-5.** WHEN a coach run passes card verification THE SYSTEM SHALL dispatch the
  coach runtime exactly as today (owner-scoped to the verified subject).
- **FR-6.** WHEN the coach run identity verification completes (accept **or**
  reject) THE SYSTEM SHALL emit a structured audit log line recording the
  `subject`, the coach `agent_id`, the verification result (`verified=True` or
  `verified=False`), and the run `thread_id` (field name `thread=`), WITHOUT
  logging any PII (no token, no learner content) — per O2. Domain `trace_id` is
  not required: the audit fires pre-stream, before a domain trace exists.
- **FR-7.** THE SYSTEM SHALL leave the plain-chat path
  (`agent_id != SUBJECT_COACH_AGENT_ID`) byte-identical — no verify-gate, no new
  audit line, no latency added.

## 4. Data model / contracts

No new types, no wire-schema change, no trust-kernel type change (⇒ no re-signing,
no ADR trigger). D3 consumes the **existing** `AgentFactsRegistry.verify(agent_id)
-> bool`. D0 consumes the existing `@workos-inc/authkit-nextjs` `withAuth` options
object (`{ ensureSignedIn: true }`). The audit line is a `logger.info` structured
record, not a new schema.

## 5. Invariants & security boundaries

- **F-R1 / B1 / B2 (RSC vs client boundary):** D0 introduces a **new server**
  `layout.tsx` at `frontend/app/(coach)/layout.tsx` that performs the `withAuth`
  guard, then renders the existing `'use client'` `learn/layout.tsx` shell as
  `children` (Server-passes-Client pattern, Rule B2). No `'use client'` moves; no
  domain logic in a component.
- **F-R4 (route handlers/guards, not business logic):** the guard is a thin
  `await withAuth({ ensureSignedIn: true })` — no conditionals beyond the SDK call.
- **A1 / F-R2 (SDK isolation):** `withAuth` from `@workos-inc/authkit-nextjs` is a
  WorkOS SDK import. It is already imported in `app/page.tsx` (a page/RSC boundary,
  not `lib/`), so D0 follows the established repo placement for the auth-guard call
  at the RSC page/layout level. *(Clarify Q-C1 confirms this placement is accepted.)*
- **Fail-closed idiom (middleware):** FR-4's 503 matches the existing coach
  fail-closed at `app_prod.py:632-635` (`coach_runtime is None → 503`). `verify()`
  returns `bool` (never raises), so the gate is a plain `if not …: raise
  HTTPException(503)` — no try/except needed.
- **O2 (no PII in logs):** FR-6 logs `subject` (an id), `agent_id`, a boolean, and
  `thread_id` only.
- **Prod-surface drift guard:** `middleware/__main__.py` mirrors the coach dispatch
  (documented drift hazard). FR-4's verify-gate MUST be added to **both**
  `app_prod.py` and `__main__.py` coach seams, or the dev surface diverges.

No Architecture Invariant (#1–#8) is crossed; no new dependency; no new service, node,
or abstraction ⇒ **no ADR trigger**.

## 6. Edge cases

- **Coach card missing at first request** — `_coach_run_identity` lazily seeds the card
  via `register_subject_coach` *before* it would be verified; verify must run **after**
  seeding (seed then verify), else the first-ever coach request 503s spuriously.
- **`ensureSignedIn` vs Tauri desktop / iOS Capacitor deep-link auth** — those flows
  authenticate out-of-band; the redirect target must not dead-lock the shell inside
  the native WebView. Q-C2 DoD = structural (`/api/auth/*` outside `(coach)`);
  live device smoke deferred. Scope-out the native UA path only if a later live
  pass breaks.
- **`E2E_BYPASS_AUTH`** — WHEN `NODE_ENV !== "production"` AND `E2E_BYPASS_AUTH=1`
  THE SYSTEM MAY skip `withAuth` in `(coach)/layout.tsx` so seeded learn-e2e can
  run without a WorkOS session. Production builds MUST NOT take this branch
  (mirrors `app/page.tsx`).
- **`/learn` group root has no page today** — only `/learn` and descendants exist; the
  guard at `(coach)/layout.tsx` wraps the whole group including any future sibling.
  FR-3 structural tests MUST enumerate pages that exist on the branch (not a fixed
  "7 pages" list that may include routes not yet landed).
- **Verify returns False mid-session (card tampered / suspended after seed)** — each
  coach run re-verifies, so a suspended card 503s the next run (not just startup).
- **Static assets / `_next` under the matcher** — the guard is a layout, not middleware,
  so it only runs for page requests in the group; no asset-path exclusion needed.

## 7. Non-functional requirements

- **D0:** `withAuth()` already runs per-request via the AuthKit session cookie; the
  new layout adds one server call already made on the chat path — negligible latency,
  no new network hop.
- **D3 verify:** the GCS registry `verify()` reads + HMAC-checks one card; on the
  coach path only (chat unaffected, FR-7). Q-C3 CLOSED: **per-run** verify (one HMAC
  check per coach request; catches mid-session suspend/tamper; no caching complexity).
- **Determinism:** all criteria are L1-deterministic (redirect vs render; 503 vs
  dispatch; log line present). No live-LLM path added; nothing new on the CI hot path.
- **Reversibility:** D0 is one new file (deletable); D3 is an additive guard + log
  line (removable). No migration, no data change.

## 8. Test plan

Failure-path tests first. Frontend = Vitest/RTL + Playwright; middleware = pytest.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `frontend/e2e/…::coach pages redirect unauth → sign-in` (Playwright, no session) | L4 | e2e tier |
| FR-1 | `frontend/app/(coach)/layout.test.tsx::guard calls withAuth ensureSignedIn` (mock `withAuth`) | L1 | yes |
| FR-2 | `…layout.test.tsx::authed user renders children shell` | L1 | yes |
| FR-3 | `…layout.test.tsx::single group-root guard wraps all pages` (structural) | L1 | yes |
| FR-4 | `tests/middleware/test_coach_shadow_wiring.py::test_coach_run_unverified_card_is_rejected` (verify→False) | L1 | yes |
| FR-5 | `…::test_coach_run_verified_card_dispatches` (verify→True) | L1 | yes |
| FR-6 | `…::test_coach_identity_resolution_emits_audit_line_no_pii` (accept path: `thread=` + `verified=True`, no PII) | L1 | yes |
| FR-6 | `…::test_coach_run_unverified_card_is_rejected` (reject path: `verified=False` audit, no run) | L1 | yes |
| FR-7 | `…::test_plain_chat_no_verify_no_audit_line` (extend existing `test_plain_chat_never_uses_coach_runtime`) | L1 | yes |

Existing `tests/middleware/test_coach_shadow_wiring.py` already has the mock-JWT
harness + the 503-fail-closed precedent (`test_coach_request_with_missing_coach_runtime_is_rejected`)
— FR-4/5/6/7 extend it. `__main__.py` mirror gets the parallel verify-gate test.

## 9. Definition of Done

- [x] FR-1…FR-7 implemented; each has a test seen to fail first.
- [x] `make check` green (lint + format-check + pyright + test); frontend auth-scoped vitest green (full `pnpm test` has 2 pre-existing unrelated fails).
- [x] `tests/architecture/` green (F-R layering unbroken; no SDK leak past the RSC boundary).
- [x] Verify-gate present in **both** `app_prod.py` and `__main__.py` coach seams (drift guard).
- [x] `docs/adr/decisions.md` entry for the "verify the coach card's agent_id, not the
      learner subject" choice (small non-obvious decision; no full ADR).
- [x] Actual command output pasted (not summarized) for the verification claims.
