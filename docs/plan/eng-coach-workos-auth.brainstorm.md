---
type: brainstorm
title: "Eng Coach behind WorkOS auth via the AgentFacts registry — SDD Stage-1 brainstorm"
description: Premise audit + candidate directions for "put Eng Coach behind WorkOS auth, give auth capability through the governanceTriangle agent registry". Central finding — the stated framing is REFUTED: the coach is already authenticated AND already resolves identity through the AgentFacts registry; the one real gap is that the `(coach)` route-group PAGES render to an unauthenticated browser (the APIs already 401).
status: "Stage-1 CLOSED (2026-07-13) — gate: Q1=D0 scoped RSC guard, Q2=identity-binding-is-enough (D2 dropped), Q3=D3 bundled with D0. Deliverable = D0+D3 bundle. NEXT = sdd-spec."
authored: 2026-07-13
branch: feat/preact-parity-epic-F
---

# Brainstorm — Eng Coach behind WorkOS auth via the AgentFacts registry

**Stage 1 (SDD).** Problem as posed: "put the Eng Coach app behind WorkOS
authentication; enable / give auth capability to Eng Coach through the
`governanaceTriangle` agent registry (AgentFacts)."
**Tree:** `feat/preact-parity-epic-F`.

The request reads as greenfield ("enable auth", "give auth capability"), but the
coach is already authenticated at three of four layers and already resolves
identity through the AgentFacts registry. Continuing on the "add auth from
scratch" framing would build duplicate machinery. The premise audit below drives
a re-posed framing.

## Premise audit

Every load-bearing premise checked against the working tree before ideation.

| # | Premise (as stated / implied) | Status | Evidence |
|---|---|---|---|
| P1 | Eng Coach has **no** WorkOS auth today | **REFUTED** | Coach SSE route 401s when unauthenticated — [`frontend/app/api/coach/run/stream/route.ts:37`](../../frontend/app/api/coach/run/stream/route.ts); session-marker route 401s — [`frontend/app/api/coach/session-marker/route.ts:32`](../../frontend/app/api/coach/session-marker/route.ts). |
| P2 | The middleware doesn't verify identity for coach runs | **REFUTED** | `/run/stream` verifies the WorkOS JWT and 401s on failure — [`middleware/app_prod.py:602`](../../middleware/app_prod.py); coach path resolves a signed identity — [`middleware/app_prod.py:628`](../../middleware/app_prod.py). |
| P3 | "Auth capability through the agent registry (AgentFacts)" must be **built** | **REFUTED** | Already wired: `_coach_run_identity()` seeds/reads the signed coach card from `AgentFactsRegistry` and scopes `owner` to the verified learner — [`middleware/app_prod.py:586`](../../middleware/app_prod.py). |
| P4 | The AgentFacts registry is the tutorial's `backend.explainability.agent_facts` | **REFUTED** | No `backend/` dir exists. Real impl: [`services/governance/agent_facts_registry.py`](../../services/governance/agent_facts_registry.py) + GCS variant. `governanaceTriangle/` is a tutorial narrative, not the wiring. |
| P5 | The coach **page** (`/learn/coach`) is protected | **REFUTED (the real gap)** | The `(coach)` route group is a `'use client'` shell with **no `withAuth()` and no redirect** — [`frontend/app/(coach)/learn/layout.tsx`](../../frontend/app/%28coach%29/learn/layout.tsx). Contrast the chat landing, which gates on `withAuth()` and shows a sign-in wall — [`frontend/app/page.tsx:44`](../../frontend/app/page.tsx). |
| P6 | Identity resolution = an **authorization decision** | **REFUTED** | `_resolve_identity` / `_coach_run_identity` **auto-provision** unknown subjects (`register(...)`, never reject) — [`middleware/app_prod.py:357`](../../middleware/app_prod.py). There is authN + identity binding, but **no capability/policy check** gates a coach run; the registry's `Policy` / `requires_approval` machinery is unused on this path. |

### Re-posed framing

The honest problem is **not** "put Eng Coach behind WorkOS auth." It is:

> **(a)** Close the one real hole — the coach *pages* render to unauthenticated
> browsers (the API is safe, but first-paint/UX is not gated), and **(b)** decide
> whether "auth capability through the agent registry" should graduate from
> *identity binding* (built) to an actual *authorization decision*
> (capability/policy check — not built).

(a) is an operational gap-closer; (b) is a new capability. Two goals on a shared
substrate — the split is the real decision at the gate.

## Directions

### D0 — Blocking gap-closer: gate the `(coach)` route group at the server (do-regardless)

The system is **live with a known open defect** (P5): `/learn/coach` and siblings
paint for an unauthenticated user. A present risk outranks every future
capability, so this leads.

- **Follows existing pattern:** the `withAuth()` gate already in
  [`frontend/app/page.tsx:44`](../../frontend/app/page.tsx). The `(coach)` shell
  is `'use client'` (reads `useSurface`/`usePathname`), so the fix is a thin RSC
  parent layout that calls `withAuth({ ensureSignedIn: true })` and renders the
  client shell as `children` (Rule B2).
- **What breaks if chosen:** nothing functional — the API already 401s, so this
  fixes first-paint/UX leak and any client-only data. Low blast radius.
- **Invariant stressed:** B1/B2 (RSC-vs-client boundary), F-R4 (route handlers vs
  guards).
- **ADR:** none (bug fix, follows precedent).

### D1 — Middleware `unauthenticatedPaths` allowlist (high-probability, config-level)

Configure AuthKit centrally so `authkit(req)` *enforces* (redirects) rather than
only attaching headers.

- **Follows pattern:** [`frontend/middleware.ts:103`](../../frontend/middleware.ts)
  already calls `authkit(req)` (header-only today). AuthKit supports a
  `middlewareAuth` / `unauthenticatedPaths` config to redirect unauth users.
- **Tradeoff vs D0:** one config site protects all routes uniformly — but it's a
  global behavior change that must not break the public sign-in page, the Tauri
  desktop deep-link flow ([`frontend/lib/adapters/auth/workos_desktop_auth.ts`](../../frontend/lib/adapters/auth/workos_desktop_auth.ts)),
  or the iOS Capacitor path. Higher blast radius than D0's scoped guard.
- **What breaks if chosen:** desktop/iOS flows and the `/api/auth/*` callback must
  be allowlisted or sign-in dead-locks.
- **Invariant stressed:** F1 (composition-root-only env), CSP `connect-src`.
- **ADR:** borderline — a global auth-enforcement switch is arguably ⚠️ Ask-first.

### D2 — Graduate to a real authorization decision: capability-gate the coach run (exploratory)

Takes "give auth capability … **through the agent registry**" literally: use the
AgentFacts `Capability`/`Policy` machinery to *authorize*, not just *identify*.

- **New abstraction:** an `AuthorizationService.authorize(identity, "coach.run")`
  check at [`middleware/app_prod.py:628`](../../middleware/app_prod.py) before
  dispatching the coach graph. `FRONTEND_ARCHITECTURE` §Data-Flow already *names*
  this step ("`AuthorizationService.authorize(identity, action)`") — specced, not
  implemented.
- **Tradeoff:** real new surface (service + policy semantics + deny path). Today
  every authenticated user is auto-provisioned and allowed. A capability gate only
  earns its place if there is a population to *deny* (entitlement tiers,
  org-scoped access). **If every signed-in user should get the coach, D2 is
  over-engineering** — identity binding is sufficient.
- **Invariant stressed:** ⚠️ Ask-first (new horizontal service), trust-kernel
  `Policy` semantics, G3 security-boundary gate.
- **`gated-on-decision`:** needs a product answer — *is there anyone to deny?* If
  no, drop D2.

### D3 — Under-used signal: verify-before-execute + audit the identity resolution (exploratory, additive)

The registry has an audit-trail + signature-verification surface that this path
never exercises. The coach run resolves a signed card but never calls `verify()`
before execution (AgentFacts "verify-before-execute" best practice).

- **Direction:** add a `registry.verify(subject)` gate + emit the coach run's
  identity resolution into Langfuse via the existing `telemetry_bridge` /
  `trace_id` path, so "who ran the coach, under which signed card" is auditable.
- **Tradeoff:** cheap and additive (no deny path); governance-completeness, not an
  access fix. Pairs naturally with D0. The coach card is repo-seeded and signed,
  so `verify()` failure means tampering → recommend **fail-closed (503)** to match
  the existing `body.agent_id` fail-closed idiom at
  [`middleware/app_prod.py:622`](../../middleware/app_prod.py).
- **Invariant stressed:** O2 (no PII in logs — subject is an id, safe), F-R7
  (trace propagation).
- **ADR:** none.

### D4 — Class-level: one shared server-side auth guard for all client-shell route groups (exploratory)

Recognize the **class**: any future `'use client'` route-group shell (coach today,
a second learning app tomorrow) re-introduces the same "page paints unauth"
defect.

- **Direction:** a shared `requireSignedIn()` server helper + an **architecture
  test** that fails any route-group root layout lacking a server-side auth guard
  (mirrors `tests/architecture/` discipline).
- **Tradeoff:** more up-front than D0 for one consumer; earns its place only if a
  second protected client-shell app is real. Today there is one (coach) — so this
  is D0 + a test, deferred until the second appears.
- **Invariant stressed:** the architecture-test convention; F-R1.
- **ADR:** the new-abstraction gate G1 if the shared helper lands before the
  second consumer.

## Dependency structure & the real decision

- **D0 is do-regardless** — closes a live defect, blocks nothing. The only *risk*
  on the board.
- **D1 is an alternative *mechanism* for D0** (central config vs scoped guard) —
  pick one, not both. D1 has wider blast radius (desktop/iOS flows).
- **D3 is independent and additive** — governance completeness; rides alongside D0.
- **D2 is the only true new capability**, gated on a product answer: is there any
  signed-in user to *deny*? If no, D2 is over-engineering and the "give auth
  capability" ask is already satisfied by the identity binding that exists.
- **D4 is D0 generalized** — defer until a second client-shell app exists.

The conflated axis in the original request — *authentication* (who are you) vs
*authorization* (are you allowed) — is the split that matters. AuthN +
identity-via-registry is **built**; the gaps are the **page guard** (operational,
D0/D1) and optionally an **authZ decision** (capability, D2).

## Human gate — decisions (2026-07-13)

| Q | Decision | Consequence |
|---|---|---|
| **Q1 — page guard mechanism** | **D0 scoped RSC guard** | Parent server layout above the `(coach)` client shell calls `withAuth({ ensureSignedIn: true })`. Coach-only, low blast radius, follows the chat-landing precedent. D1 rejected (wider blast radius on desktop/iOS). |
| **Q2 — authZ scope** | **Identity binding is enough** | Every signed-in user gets the coach; no deny path. **D2 dropped** — the "give auth capability" ask is already satisfied by the built identity-via-registry binding. |
| **Q3 — audit wiring** | **D3 bundled with D0** | `registry.verify()` before coach execution (fail-closed 503) + emit identity resolution to the audit/Langfuse trail. Additive, no deny path. |

**Net deliverable = D0 + D3 bundle** (close the page-guard hole + verify-before-execute & audit).
No new abstraction, no ADR trigger for D0 (bug fix following precedent); D3's
verify-gate is additive on an existing registry surface. **D4 deferred** (single
consumer). Open shape questions for the spec: (1) D0 = parent-layout form vs shared
helper (spec the parent-layout form), (2) D3 verify-failure policy (recommend
fail-closed 503).

**NEXT → sdd-spec** with the D0+D3 bundle.
