---
type: tasks
title: "Eng Coach WorkOS auth: D0 page-guard + D3 verify-before-execute & audit — task list"
description: Red-first atomic tasks in two independent tracks — D3 backend (G1..G6: unverified-card 503 red → verify-gate green → audit line → __main__ mirror → decisions.md) and D0 frontend (G7..G10: guard unit test → new server layout → e2e redirect + native check → arch/a11y) → G11 full gate. Measurability checklist confirms all 7 FRs machine-checkable.
status: "Implemented 2026-07-13 — Stage 6 G1–G10 green; G11 make check + arch green; pnpm test has 2 pre-existing unrelated fails (AppNav/D2 labels) — next: code-review"
authored: 2026-07-13
---

# Tasks — Eng Coach WorkOS auth: D0 page-guard + D3 verify-before-execute & audit

**Status:** Draft — 2026-07-13
**Spec:** [eng-coach-workos-auth.spec.md](eng-coach-workos-auth.spec.md) · **Plan:** [eng-coach-workos-auth.plan.md](eng-coach-workos-auth.plan.md)

Red-first (write the test, watch it fail, then implement). Two independent tracks
(D3 backend, D0 frontend) — no ordering dependency between them; `[∥]` = parallelizable.

---

## Measurability checklist ("unit tests for English")

Every FR collapses to one machine-checkable claim — all measurable, none flagged back:

- FR-1 → redirect status/location on unauth request (Playwright) + `withAuth` called with `{ensureSignedIn:true}` (Vitest mock). ✅
- FR-2 → authed render returns children shell. ✅
- FR-3 → exactly one guard at group root (structural: guard absent from the 7 pages). ✅
- FR-4 → `verify()==False` ⇒ HTTP 503, runtime NOT invoked. ✅
- FR-5 → `verify()==True` ⇒ runtime invoked, owner==subject. ✅
- FR-6 → audit log record contains subject+agent_id+verified+trace_id, contains no token/content. ✅
- FR-7 → chat request: `verify` not called, audit line absent, response unchanged. ✅

---

## Track D3 — middleware verify-before-execute + audit (backend-only, ship first)

- **[∥] G1 — Red: unverified card 503 (FR-4, failure first).**
  In `tests/middleware/test_coach_shadow_wiring.py`, add `test_coach_run_unverified_card_is_rejected`:
  wire a registry whose `verify(SUBJECT_COACH_AGENT_ID)` returns `False`; a coach
  `/run/stream` request asserts `status_code == 503` and the coach runtime's `.run`
  was **never** awaited. **Pass/fail:** test fails now (no gate) → passes after G3.

- **G2 — Red: verified card dispatches + chat path untouched (FR-5, FR-7).**
  Add `test_coach_run_verified_card_dispatches` (`verify→True` ⇒ runtime invoked,
  identity.owner==subject) and extend `test_plain_chat_never_uses_coach_runtime` to
  assert `verify` is **not** called and no audit line on the chat path.
  **Pass/fail:** both fail/incomplete now → pass after G3.

- **G3 — Green: implement the verify-gate in `app_prod.py` (FR-4, FR-5).**
  In the coach branch of `/run/stream` (`app_prod.py`), after
  `identity = _coach_run_identity(claims.subject)` (which seeds the card), add:
  `if not agent_facts_registry.verify(SUBJECT_COACH_AGENT_ID): raise HTTPException(503,
  "coach identity unverified")`. Order = seed **then** verify (R3). Chat `else` untouched.
  **Pass/fail:** G1+G2 green.

- **G4 — Red→Green: audit log line, no PII (FR-6).**
  Test `test_coach_identity_resolution_emits_audit_line_no_pii` (caplog): on a verified
  coach run, a `logger.info` record exists containing `subject`, `agent_id`,
  `verified`, `trace_id`; assert it contains no bearer token and no learner content.
  Implement the `logger.info("coach_identity_verified subject=%s agent_id=%s verified=%s
  trace=%s", …)` at the seam. **Pass/fail:** test red → green.

- **G5 — Mirror the gate into `__main__.py` (drift guard, FR-4-7 / R2).**
  Apply the identical verify-gate + audit line to the mirrored coach seam in
  `middleware/__main__.py`. Add `test_coach_run_unverified_card_is_rejected` against the
  `build_dev_app` surface (or parametrize G1 over both apps). **Pass/fail:** dev-app
  test 503s on unverified card, same as prod.

- **G6 — decisions.md note (T7).**
  Append the 2–4 line entry: verify targets the coach **card's** `agent_id`
  (`SUBJECT_COACH_AGENT_ID`), not the learner subject. **Pass/fail:** entry present.

## Track D0 — frontend (coach) page guard (ship after D3 or in parallel)

- **[∥] G7 — Red: guard unit test (FR-1, FR-2, FR-3).**
  New `frontend/app/(coach)/layout.test.tsx`: mock `@workos-inc/authkit-nextjs`
  `withAuth`. Assert (a) the layout awaits `withAuth({ ensureSignedIn: true })`,
  (b) renders `children` for an authed user. **Pass/fail:** fails now (no file) → G8.

- **G8 — Green: new server layout (FR-1, FR-2, FR-3).**
  Create `frontend/app/(coach)/layout.tsx` (server RSC): `export const
  dynamic = "force-dynamic"`; `export default async function CoachGroupLayout({children})
  { await withAuth({ ensureSignedIn: true }); return <>{children}</>; }`. Does NOT touch
  `learn/layout.tsx`. **Pass/fail:** G7 green; `pnpm tsc` clean.

- **G9 — Red→Green: e2e redirect (FR-1) + native-flow check (Q-C2).**
  Playwright spec: unauthenticated request to `/learn` and `/learn/coach` redirects to
  the WorkOS sign-in and renders no coach content. Plus the native check: confirm Tauri
  desktop + iOS Capacitor deep-link sign-in still completes with the guard active.
  **Pass/fail:** e2e redirect asserted green; native sign-in verified (or guard scoped
  by native UA if it regresses — then re-run).

- **G10 — architecture + a11y guard (F-R2 / §20).**
  Run `frontend/tests/architecture/` — confirm no SDK leak past the RSC boundary and the
  new layout doesn't violate layering. **Pass/fail:** arch suite green.

## Closeout (both tracks)

- **G11 — Full gate.** `make check` + `pytest tests/architecture/ -q` + `pnpm test` +
  targeted `pnpm test:e2e` for the coach redirect. **Pass/fail:** all green; paste
  actual output (DoD requires unsummarized output).

---

## Dependency graph

```
D3:  G1 ∥ G2  →  G3  →  G4  →  G5  →  G6 ┐
D0:  G7  →  G8  →  G9  →  G10             ├→  G11 (full gate)
                                          ┘
```
G1/G2 and G7 are the red-first entry points (parallelizable). G3 unblocks G4/G5.
Tracks D3 and D0 are fully independent until G11.
