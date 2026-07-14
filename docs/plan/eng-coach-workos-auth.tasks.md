---
type: tasks
title: "Eng Coach WorkOS auth: D0 page-guard + D3 verify-before-execute & audit — task list"
description: Red-first atomic tasks in two independent tracks — D3 backend (G1..G6: unverified-card 503 red → verify-gate green → audit line → __main__ mirror → decisions.md) and D0 frontend (G7..G10: guard unit test → new server layout → e2e redirect + native check → arch/a11y) → G11 full gate. Measurability checklist confirms all 7 FRs machine-checkable.
status: "Stage 9/10 converge 2026-07-14 — CONVERGED — await human Stage 10 sign-off"
authored: 2026-07-13
---

# Tasks — Eng Coach WorkOS auth: D0 page-guard + D3 verify-before-execute & audit

**Status:** Stage 9/10 converge 2026-07-14 — **CONVERGED** (no new Phase N tasks) — await human sign-off
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
- FR-6 → audit log record contains subject+agent_id+verified+thread_id on accept **and** reject; contains no token/content. ✅ (wording replan 2026-07-13)
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
  `verified`, `thread_id`; assert it contains no bearer token and no learner content.
  Implement the `logger.info("coach_identity_verified subject=%s agent_id=%s verified=%s
  thread=%s", …)` at the seam. **Pass/fail:** test red → green.
  *(Stage-5 replan: correlator is `thread=`, not `trace=`; reject-path audit is P1-4.)*

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

- **G9 — Red→Green: e2e redirect (FR-1) + native-flow structural check (Q-C2).**
  Playwright spec: unauthenticated request to `/learn` and `/learn/coach` redirects to
  the WorkOS sign-in and renders no coach content. Plus the native check: confirm
  `/api/auth/*` stays outside `(coach)` so deep-link completion is not blocked by the
  page guard. Live Tauri/iOS smoke deferred (Stage-5 replan).
  **Pass/fail:** e2e redirect asserted green; structural auth-route check green.

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

---

## Phase 1 — Convergence (Stage 9 · 2026-07-13)

`max_iterations`: 2 · iteration 1 of 2.

| ID | Gap | gap-type | source-ref | Task | Pass/fail |
|----|-----|----------|------------|------|-----------|
| P1-1 | G8 rename waivers missing for TAP-4 renames | `partial` → **done** | `tests/architecture/test_no_test_weakening.py` | `# G8-OK:` waivers naming both removed tests. **Pass/fail:** `pytest tests/architecture/test_no_test_weakening.py -q` → **1 passed** (2026-07-14). |
| P1-2 | FR-3 structural unit test opens non-existent `progress/page.tsx` | `partial` → **done** | `frontend/app/(coach)/layout.test.tsx` | Discover-existing via recursive `fs.readdir` of `**/page.tsx` (spec §6). **Pass/fail:** `pnpm exec vitest run app/(coach)/layout.test.tsx` → **3/3** (2026-07-14). |
| P1-3 | FR-6 audit correlator labeled `trace=` | `partial` → **done** | `middleware/app_prod.py` + `__main__.py` | Format string `thread=%s`; accept test asserts `thread=` and no `trace=` on the audit line. **Pass/fail:** FR-6 accept green (2026-07-14). |
| P1-4 | FR-6 reject path silent | `partial` → **done** | reject path + FR-6 | Hoisted single `logger.info(..., verified=<bool>, thread=...)` before accept dispatch / reject 503; reject tests assert `verified=False`. **Pass/fail:** prod + `__main__` reject tests green (2026-07-14). |

### Deferred (human gate — not in-iteration unless approved)

| Item | gap-type | Notes |
|------|----------|-------|
| Q-C2 live Tauri/iOS deep-link sign-in | `partial` | **Replan DROP from DoD** — structural `/api/auth/*` check accepted; live native smoke → tech-debt deferral (R1). |
| `E2E_BYPASS_AUTH` escape hatch in `(coach)/layout.tsx` | `unrequested` → **specced** | **Replan ADD** — explicit edge case in spec §6; mirrors `app/page.tsx`. No new code task. |
| CI architecture job shallow checkout | `partial` | Out of code scope; local full-history G8 remains the honest signal (P1-1). |

**Converge verdict (iteration 1 code):** Phase 1 tasks **done** — re-entered **sdd-converge** 2026-07-14.

---

## Stage 5 replan — Phase 1 sprint board (2026-07-13)

**Trigger:** Stage-9 converge gaps that need scope decisions (P1-3/P1-4) + deferred
items (Q-C2, `E2E_BYPASS_AUTH`), before more code.

### Disposition table

| ID | Disposition | Reason |
|----|-------------|--------|
| P1-1 | **STAY** — implement → **done 2026-07-14** | No scope change; G8 rename waivers only. Blocking for honest local arch gate. |
| P1-2 | **STAY** — implement → **done 2026-07-14** | Discover-existing via `fs.readdir` (not hardcoded drop). |
| P1-3 | **SCOPE CHANGE → stay as implement** → **done 2026-07-14** | Spec FR-6 now requires `thread_id` / `thread=`. Rejected: inventing a domain `trace_id` at the seam. |
| P1-4 | **SCOPE CLARIFY → stay as implement** → **done 2026-07-14** | Spec FR-6 both-paths; hoisted single audit line. Rejected: success-only. |
| Q-C2 live native | **DROP from DoD** | Structural check is merge DoD; live Tauri/iOS smoke deferred as tech debt (plan R1). |
| `E2E_BYPASS_AUTH` | **ADD to spec** (no code task) | Was `unrequested`; now an explicit §6 edge case. Layout already correct. |

### Implement order (after human approve)

```
P1-1 (G8 waivers) → P1-2 (layout FR-3 pages) → P1-3 (rename trace→thread) → P1-4 (reject verified=False audit) → re-enter sdd-converge
```

**Landed 2026-07-14** in that order (P1-2 = `fs.readdir`; P1-4 = hoisted audit, not duplicated).

Gate evidence pasted (Phase 1 closeout):
- `pytest tests/middleware/test_coach_shadow_wiring.py -q` → **23 passed**
- `pytest tests/architecture/ -q` → **199 passed, 2 skipped**
- `pnpm exec vitest run 'app/(coach)/layout.test.tsx'` → **3 passed**
- `pytest tests/architecture/test_no_test_weakening.py -q` → **1 passed**

**Routing:** **sdd-converge** (Stage 9) — Phase 1 residual closed → re-converge below.

---

## Phase 2 — Convergence (Stage 9 · 2026-07-14 re-entry)

`max_iterations`: 2 · **iteration 2 of 2** (ceiling — after P2, next fail forces human review).

### EARS re-check (tree + tests, 2026-07-14)

| FR | Verdict | Evidence |
|----|---------|----------|
| FR-1 | met | `(coach)/layout.tsx` `withAuth({ ensureSignedIn: true })`; `frontend/e2e/coach-auth-guard.spec.ts`; Vitest guard call |
| FR-2 | met | layout returns `children`; Vitest authed render |
| FR-3 | met | single group-root guard; `collectPageTsx` / no per-page `withAuth` |
| FR-4 | met | `verify→False` ⇒ 503; prod + `__main__` reject tests |
| FR-5 | met | `test_coach_run_verified_card_dispatches` |
| FR-6 | met | hoisted audit `thread=` + `verified=True/False` on accept+reject |
| FR-7 | met | `test_plain_chat_never_uses_coach_runtime` |

Re-paste (this re-entry):
```
$ pytest tests/middleware/test_coach_shadow_wiring.py tests/architecture/test_no_test_weakening.py -q
........................                                                 [100%]
24 passed in 1.61s

$ cd frontend && pnpm exec vitest run 'app/(coach)/layout.test.tsx'
 Test Files  1 passed (1)
      Tests  3 passed (3)

$ pytest tests/architecture/ -q
197 passed, 4 skipped in 10.90s
```

### New gaps

| ID | Gap | gap-type | source-ref | Task | Pass/fail |
|----|-----|----------|------------|------|-----------|
| P2-1 | `docs/plan/eng-coach-workos-auth.tasks.md` missing trailing newline; CI `end-of-file-fixer` red on PR #160 merge | `partial` → **done** | GitHub Actions `ruff + gitleaks + hygiene` run 29347115503; local `ends_with_newline False` | Ensure file ends with `\n`; `pre-commit run end-of-file-fixer --files …` → **Passed** (2026-07-14). |

### Out of change scope (not Phase 2)

| Item | gap-type | Notes |
|------|----------|-------|
| `docs/plan/preact-parity-e2e-validation-report-2026-07-13.md` trailing whitespace | n/a (foreign) | Failed same CI job via `--all-files` / merge-base with #161; **not** introduced by WorkOS auth. Logged under plan §6 deferrals. |
| Q-C2 live Tauri/iOS smoke | deferred | Unchanged — structural DoD stands. |
| CI architecture shallow checkout / G8 | deferred | Unchanged. |

### Blast-radius (Stage 10 §6)

Nothing this change added is now deletable: D0 layout, D3 verify+audit, E2E_BYPASS (specced), and FR tests are all load-bearing. Worktree-only `frontend/node_modules` symlink (review harness) was never committed.

### Converge verdict (iteration 2)

**NOT converged** at classification time — P2-1 was the remaining in-scope `partial`.

**P2-1 landed (2026-07-14):** trailing `\n` restored; end-of-file-fixer green on this path.

**Routing:** re-enter **sdd-converge** (iteration ceiling: if still red after this, **forced human review**).

PR #160 already **MERGED** (`072f93c`); P2-1 ships as a follow-up commit/PR for Stage 10 hygiene.

---

## Post-P2 re-converge (Stage 9/10 · 2026-07-14)

`max_iterations`: 2 · post-iteration-2 check (within ceiling).

### Gap scan

| Candidate | Class | Disposition |
|-----------|-------|-------------|
| FR-1..FR-7 | — | **met** (seams + tests) |
| P1-1..P1-4 | — | **done** |
| P2-1 EOF newline | `partial` | **done** — `EOF_nl True`; end-of-file-fixer **Passed** |
| preact-parity trailing WS on `main` | foreign | deferred (plan §6) — not WorkOS Phase N |
| G8 `test_no_test_weakening` skip | env | "no tests/**.py changes in this range" — expected for docs-only delta; prior P1-1 waiver remains |

**No new Phase 3 tasks.** No `missing` / `partial` / `contradicts` / `unrequested` in-scope gaps.

### Evidence (pasted)

```
$ python3 … EOF_nl True (tasks/spec/plan)
$ pre-commit run end-of-file-fixer --files docs/plan/eng-coach-workos-auth.*.md
fix end of files.........................................................Passed
$ pre-commit run trailing-whitespace --files …
trim trailing whitespace.................................................Passed

$ pytest tests/middleware/test_coach_shadow_wiring.py tests/architecture/test_no_test_weakening.py -q
23 passed, 1 skipped in 1.35s

$ pnpm exec vitest run 'app/(coach)/layout.test.tsx'
3 passed (3)

$ pytest tests/architecture/ -q
197 passed, 4 skipped in 10.26s
```

### Blast-radius

Nothing this change added is deletable (layout, verify+audit, E2E_BYPASS, FR tests all load-bearing).

### Converge verdict

**CONVERGED.** Route → **Stage 10 human sign-off** (checklist below). Commit/PR the uncommitted P2-1 + converge docs when ready — do not treat merge of #160 alone as signed.
