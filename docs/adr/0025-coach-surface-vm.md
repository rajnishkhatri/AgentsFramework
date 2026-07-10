---
type: decision-record
title: 'ADR-0025: Coach surface VM — T1 chrome view-model for shared CoachChrome'
status: accepted
created: 2026-07-09
updated: 2026-07-09
owner: Rajnish Khatri
related: preact-parity-B1-coach-chrome.spec.md, preact-parity-epic-B.brainstorm.md, 0012-subject-coach-context-contract-hint-ladder.md
tags: [decision-record]
---

# ADR-0025: Coach surface VM — T1 chrome view-model for shared CoachChrome

**Status:** Accepted — 2026-07-09 (ratified at B1 tasks→implement human gate).
**Related:** [B1 spec](../plan/preact-parity-B1-coach-chrome.spec.md), [Epic B brainstorm](../plan/preact-parity-epic-B.brainstorm.md), [ADR-0012](0012-subject-coach-context-contract-hint-ladder.md).
**Audience:** Anyone changing coach chrome, mode display, or history trust-line assembly.

---

## Context

Epic B Sprint B1 must turn `/learn/coach` and iPad `CoachPanel` into the prototype's
coaching **workspace chrome** (rail, current-item, history trust line, mode labels,
quick-reply chips) without rebuilding the already-shipped stream stack
(`useCoach` / `coach_thread_store` / `/api/coach/run/stream`).

Today there is only a **bubble** translator (`coach_message_vm.ts`). Chrome has no VM;
putting engine reads or mode-mapping logic in React leaves would violate F-R1. A loose
props bag would work for one screen but recreates dual-surface drift (standalone vs
panel) that D6 exists to close. G1 / ⚠️ Ask first: a new T1 abstraction needs an ADR.

Separately: ADR-0012 already owns **authoritative** mode on the run path. B1's three
prototype labels are **display-only** (D5a) — they must not become a client override.

---

## Decision

Ship a pure T1 translator **`coach_surface_vm.ts`** that maps host-assembled inputs
(derived `CoachMode`, optional pinned item, optional skill-scoped misses count, static
chip seeds) → **`CoachSurfaceVM`**. Presentational **`CoachChrome`** renders that VM
and is composed by both `coach/page.tsx` and `CoachPanel`. Engine I/O stays in a page/
panel hook (Dashboard `loadDashboard` precedent). Mode labels never write to the run
body or marker store. `coach_context` / `misses_aggregate` on the wire remain **B3**.

---

## Options considered & rejected

| Option | What | Why it lost |
|---|---|---|
| **A. Props bag only** | Pass rail/history/mode fields as ad-hoc props into `CoachView` | No single testable map; dual surfaces drift; weak F-R1 boundary |
| **B. Extend `coach_message_vm`** | Fold chrome into bubble VM | Wrong seam — bubbles are stream projection; chrome is host context |
| **C. Surface VM + CoachChrome** *(chosen)* | New T1 VM + shared leaf | Matches Dashboard pattern; D6 shared chrome; G1 earned once |
| **D. Put chrome fields on `coach_context` wire now** | Zod/schema for rail | Protocol exists in ADR-0012/spec but client still messages-only; B3 owns payload — chrome must not invent a second contract |

---

## Rationale

The Dashboard already proves the pattern: ports in a hook → pure translators → dumb
view. Coach chrome is the same shape with a second consumer (panel), so a shared VM
earns its place on the **second consumer** rule. Keeping display mode off the wire
preserves ADR-0012's advisory-mode invariant while still closing C-5 visually.

---

## Consequences

**Commits us to:**
- `frontend/lib/translators/coach_surface_vm.ts` (+ L1 tests) and
  `frontend/components/coach/CoachChrome.tsx` as the shared chrome leaf.
- B0 `decisions.md` entries for D5a + C-4 honesty (co-land with B1).
- Skill-scoped history via `AttemptRepo.misses` + `QuestionRepo.get` join (Attempt has
  no `skill_id`) — honest absent when no pin / load failure; no fabricated windows.
- ADR index + log entries; ratchet satisfied when this file lands with the B1 PR.

**Does not commit us to:**
- Client `coach_context` assembly (B3), Feedback→Coach navigation (B2), third derived
  mode (D5b), or a new Zod `CoachContext` entity in `lib/wire/`.

**Accepted risks:**
- Skill join is N `get`s for unique miss `question_id`s — fine for B1 volumes; revisit
  if a batch read appears.
- Standalone pin stays absent until B2 — chrome shows honest empty C-3 by design.
