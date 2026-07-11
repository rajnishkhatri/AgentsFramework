---
type: tasks
title: 'Epic A/B continuity fixes — atomic task checklist (FLAG-1/4/6 + Reveal)'
status: Done — validated 2026-07-10
authored: 2026-07-10
implements: docs/plan/epic-ab-continuity-fixes.spec.md
plan: docs/plan/epic-ab-continuity-fixes.plan.md
---

# Tasks — Epic A/B continuity fixes

**Status:** Done — validated 2026-07-10 (manual + `pnpm test:e2e:continuity` 4/4;
FLAG-6 value honesty open; FLAG-5 → Epic C0)
**Owner:** Rajnish Khatri
**Derives:** [`epic-ab-continuity-fixes.plan.md`](epic-ab-continuity-fixes.plan.md) (P1–P9) ←
[`epic-ab-continuity-fixes.spec.md`](epic-ab-continuity-fixes.spec.md) (Validated)
**Out of scope:** FLAG-5 Wrap-up (Epic C0), A0, opener skill-name copy.

Every task is **red-first**. Paste actual command output at each verify checkpoint.
`pnpm test` (frontend) green at group boundaries; `make check` before DoD.

---

## Group A — Continuity substrate (P1, P2) · FR-1, FR-2

- [x] **A1 (RED) — active pointer miss is null.**
- [x] **A2 (RED) — set/read round-trip + score fields.**
- [x] **A3 (GREEN) — implement `ActiveQuizPointer` + set/read/clear.**
- [x] **A4 (RED) — `resume_item` restores answering + score.**
- [x] **A5 (GREEN) — add `resume_item` action to reducer.**

## Group B — Resume path (P3, P4) · FR-3, FR-4

- [x] **B1 (RED) — stale session id → null + clear pointer.**
- [x] **B2 (GREEN) — `resumeQuizSession` (or equivalent) loads session + item.**
- [x] **B3 (RED→GREEN) — Quiz page mount: resume-or-open.**
- [x] **B4 (verify)** — frontend unit tests for store/reducer/resume green.

## Group C — FLAG-1 miss refresh (P5, P6) · FR-5, FR-6

- [x] **C1 (RED→GREEN) — coach page miss effect deps include `pin?.questionId`.**
- [x] **C2 (RED→GREEN) — CoachPanel same deps fix.**

## Group D — FLAG-6 + Reveal polish (P7, P8) · FR-7, FR-8

- [x] **D1 (RED→GREEN) — Summary tile label `"Mastery change"`.**
- [x] **D2 (RED→GREEN) — enabled Reveal uses `text-fg` (not muted-only).**

## Group E — E2E flip + gate (P9) · DoD

- [x] **E1 — remove `test.fail` from FLAG-1 and FLAG-4 only**
- [x] **E2 (verify)** — FLAG-1 + FLAG-4 e2e green; FLAG-5 still inverted.
- [x] **E3 (verify)** — `make check` + architecture green.

---

## Dependency / parallelization

```
A1–A5 ──► B1–B3 ──► E1–E2
              │
C1–C2 ────────┼──► E1–E2  (C parallel with B after A)
D1–D2 ────────┘
E3 last
```
